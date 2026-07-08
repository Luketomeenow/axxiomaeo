"""Live-computed content recommendations from AI-citation gap signals.

A recommendation is not a stored entity — it is derived on every request from
un-actioned citation gaps (queries where AI answer engines skip the brand or
cite a competitor). Approving one enqueues + generates content, so on the next
request it naturally falls off the list (it is now in the dedup corpus). Only
dismissals are persisted, in ``recommendation_actions``, so a dismissed rec
stays hidden for a cooldown window before it can resurface.

This service invents no new signal — it ranks and explains data already
produced by the citation tracker (via ``ReportService.get_gap_queries``) and
reuses the topic-discovery dedup + title/content-type helpers so an approved
recommendation and a daily-discovered topic behave identically downstream.
"""

import logging
from datetime import datetime, timedelta

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import RecommendationAction
from app.models.brand import Brand
from app.services.report_service import ReportService
from app.services.topic_discovery_service import (
    TopicDiscoveryService,
    derive_title,
    infer_content_type,
    normalize_query,
    queries_similar,
)

logger = logging.getLogger(__name__)

# How long a dismissed recommendation stays suppressed before it can resurface.
# The underlying gap may still be unaddressed, so we don't hide it forever —
# but not so soon that a dismiss feels ignored.
DISMISS_COOLDOWN_DAYS = 30

# Pull a wide slice of gaps so every brand's rows are represented (the default
# get_gap_queries limit is a cross-brand dashboard top-N and would crowd out
# brands whose rows sort later).
GAP_FETCH_LIMIT = 500

PLATFORM_LABELS = {
    "chatgpt": "ChatGPT",
    "gemini": "Gemini",
    "perplexity": "Perplexity",
    "google_ai": "Google AI",
    "claude": "Claude",
}


def recommendation_key(brand_id: str, query: str) -> str:
    """Stable id for a (brand, query) recommendation — survives re-computation."""
    return f"{brand_id}:{slugify(normalize_query(query), max_length=120)}"


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reports = ReportService(db)
        self.discovery = TopicDiscoveryService(db)

    async def _brands(self) -> dict[str, Brand]:
        rows = (await self.db.execute(select(Brand))).scalars().all()
        return {b.id: b for b in rows}

    async def _dismissed_keys(self) -> set[str]:
        cutoff = datetime.utcnow() - timedelta(days=DISMISS_COOLDOWN_DAYS)
        rows = await self.db.execute(
            select(RecommendationAction.key).where(
                RecommendationAction.action == "dismissed",
                RecommendationAction.created_at >= cutoff,
            )
        )
        return {r[0] for r in rows.all()}

    async def list_recommendations(self, limit: int = 50) -> list[dict]:
        gaps = await self.reports.get_gap_queries(limit=GAP_FETCH_LIMIT)
        if not gaps:
            return []

        brands = await self._brands()
        existing = await self.discovery._existing_queries_by_brand()
        dismissed = await self._dismissed_keys()

        # One query is usually missing on several engines — each is its own
        # CitationRecord row. Fold them into a single recommendation per
        # (brand, normalized query) and remember how many engines missed it.
        grouped: dict[tuple[str, str], dict] = {}
        for gap in gaps:
            brand_id = gap.get("brand_id")
            query = (gap.get("query") or "").strip()
            if not brand_id or not query or brand_id not in brands:
                continue
            gkey = (brand_id, normalize_query(query))
            entry = grouped.get(gkey)
            if entry is None:
                entry = {
                    "brand_id": brand_id,
                    "query": query,
                    "platforms": set(),
                    "competitors": set(),
                    "visibility_pcts": [],
                    "content_type": gap.get("recommended_content_type"),
                    "source_citation_id": gap.get("id"),
                }
                grouped[gkey] = entry
            if gap.get("platform"):
                entry["platforms"].add(gap["platform"])
            comp = gap.get("competitor_cited")
            if comp and isinstance(comp, str):
                entry["competitors"].add(comp)
            if gap.get("visibility_pct") is not None:
                entry["visibility_pcts"].append(gap["visibility_pct"])

        recs: list[dict] = []
        for (brand_id, _norm), entry in grouped.items():
            key = recommendation_key(brand_id, entry["query"])
            if key in dismissed:
                continue
            # Drop anything already queued, drafted, or published — reuse the
            # exact dedup corpus + fuzzy match topic discovery uses, so an
            # approved rec disappears here just like a discovered topic does.
            if any(queries_similar(entry["query"], ex) for ex in existing.get(brand_id, [])):
                continue

            brand = brands[brand_id]
            competitors = sorted(entry["competitors"])
            competitor = bool(competitors)
            engines_missing = len(entry["platforms"]) or 1
            visibility = min(entry["visibility_pcts"]) if entry["visibility_pcts"] else 0.0
            # Explainable score: a cited competitor is the strongest "we're
            # losing this" signal (+3) over plain invisibility (+2), amplified
            # by how many engines miss the brand and how low current visibility
            # is. Higher visibility → less urgent → smaller multiplier.
            base = 3 if competitor else 2
            score = round(base * engines_missing * (100 - visibility) / 100, 2)
            content_type = entry["content_type"] or infer_content_type(entry["query"], brand.markets)

            recs.append(
                {
                    "key": key,
                    "brand_id": brand_id,
                    "brand_name": brand.name,
                    "query": entry["query"],
                    "title": derive_title(entry["query"]),
                    "content_type": content_type,
                    "priority": 1 if competitor else 3,
                    "score": score,
                    "competitor_cited": competitor,
                    "competitors": competitors,
                    "engines_missing": sorted(PLATFORM_LABELS.get(p, p) for p in entry["platforms"]),
                    "visibility_pct": round(visibility, 1),
                    "why": self._build_why(brand.name, entry["platforms"], competitors, visibility),
                    "source_detail": {
                        "platforms": sorted(entry["platforms"]),
                        "competitor_cited": competitor,
                        "competitors": competitors,
                        "visibility_pct": round(visibility, 1),
                        "engines_missing": engines_missing,
                    },
                    "source_citation_id": entry["source_citation_id"],
                }
            )

        recs.sort(key=lambda r: (-r["score"], r["priority"], r["brand_id"]))
        return recs[:limit]

    def _build_why(
        self, brand_name: str, platforms: set[str], competitors: list[str], visibility: float
    ) -> str:
        engines = sorted(PLATFORM_LABELS.get(p, p) for p in platforms)
        engines_str = ", ".join(engines) if engines else "AI answer engines"
        parts = [f"{brand_name} isn't cited on {engines_str} for this query"]
        if competitors:
            shown = competitors[:2]
            verb = "is" if len(shown) == 1 else "are"
            parts.append(f"{', '.join(shown)} {verb} cited there instead")
        if visibility:
            parts.append(f"current visibility ~{round(visibility)}%")
        return "; ".join(parts) + "."

    async def get_recommendation(self, key: str) -> dict | None:
        """Re-derive a single recommendation by key (used by approve/dismiss).

        Recomputes the list rather than trusting a client-supplied payload, so
        approve always acts on live evidence and a stale/spoofed key 404s.
        """
        for rec in await self.list_recommendations(limit=GAP_FETCH_LIMIT):
            if rec["key"] == key:
                return rec
        return None

    def record_action(
        self,
        key: str,
        action: str,
        user_id: str,
        brand_id: str | None = None,
        query: str | None = None,
    ) -> None:
        self.db.add(
            RecommendationAction(
                key=key,
                action=action,
                user_id=user_id,
                brand_id=brand_id,
                query=query,
            )
        )
