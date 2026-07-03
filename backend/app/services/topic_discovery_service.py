"""Automated topic discovery — mines real demand signals into the content queue.

Sources, in priority order:

1. ``citation_gap``  — queries from the latest citation audit where AI engines
   skip the brand or cite a competitor (the strongest "will get us cited" signal).
2. ``search_demand`` — Google Search Console queries with real impressions where
   the site ranks weak or demand is rising (what users actually search right now).
3. ``coverage``      — query-bank × brand-market combinations with no content yet
   (works before GSC / the citation tracker are connected).

Every candidate is deduped against existing queue items, drafts, and published
pieces, then capped and inserted as ``ContentQueue`` rows with source metadata.
The weekly content worker generates drafts from the queue as usual — the human
approval gate before publishing is unchanged.
"""

import logging
import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece, ContentQueue
from app.services.gsc_service import GSCService
from app.utils.query_bank import get_all_queries, interpolate_query
from app.utils.query_fanout import CATEGORY_CONTENT_TYPE

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "a", "an", "in", "for", "of", "to", "and", "or", "is", "are",
    "what", "how", "much", "do", "does", "my", "your", "near", "me", "with",
}

# Generic words that never identify a brand on their own.
_GENERIC_BRAND_WORDS = {
    "elevator", "elevators", "escalator", "escalators", "service", "services",
    "company", "corp", "solutions", "inc", "llc",
}

_VERTICAL_HINTS = (
    "hospital", "hotel", "apartment", "office", "school", "university",
    "senior living", "healthcare", "retail", "multifamily", "warehouse",
    "condo", "residential building", "commercial building",
)

_QUESTION_STARTERS = ("how", "what", "why", "when", "who", "which", "can", "should", "is", "are", "do", "does")


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (query or "").lower())).strip()


def query_tokens(query: str) -> set[str]:
    return {t for t in normalize_query(query).split() if len(t) > 2 and t not in _STOPWORDS}


def queries_similar(a: str, b: str, threshold: float = 0.75) -> bool:
    """Normalized-equal, or token-set Jaccard overlap above threshold."""
    na, nb = normalize_query(a), normalize_query(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = query_tokens(a), query_tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold


def brand_search_terms(brand_name: str, wp_url: str) -> list[str]:
    """Terms that mark a query as branded/navigational.

    Uses the full brand name plus name tokens that also appear in the domain,
    so geo words survive (``arizona`` is not in ``azelevatorsolutions.com``)
    while real brand tokens (``ameritex``, ``liftech``) are caught.
    """
    terms = [normalize_query(brand_name)]
    host = urlparse(wp_url or "").netloc.lower().replace("www.", "")
    for token in re.findall(r"[a-z0-9]+", (brand_name or "").lower()):
        if len(token) >= 4 and token not in _GENERIC_BRAND_WORDS and token in host:
            terms.append(token)
    return [t for t in terms if t]


def is_branded_query(query: str, brand_terms: list[str]) -> bool:
    q = f" {normalize_query(query)} "
    return any(f" {t} " in q or t.replace(" ", "") in q.replace(" ", "") for t in brand_terms if t)


def infer_content_type(query: str, markets: list[str] | None = None) -> str:
    q = f" {normalize_query(query)} "
    if " vs " in q or "versus" in q or "compare" in q or "comparison" in q:
        return "comparison"
    if any(hint in q for hint in _VERTICAL_HINTS):
        return "vertical_page"
    if "statistics" in q or "benchmark" in q or "average cost" in q or "cost breakdown" in q:
        return "data_stats"
    if "near me" in q:
        return "local_page"
    for market in markets or []:
        city = market.rsplit(" ", 1)[0].lower() if " " in market else market.lower()
        if city and city != "national" and f" {city} " in q:
            return "local_page"
    return "faq_hub"


def derive_title(query: str) -> str:
    text = re.sub(r"\s+", " ", (query or "").strip()).rstrip("?").strip()
    if not text:
        return ""
    words = [w if (w.isupper() and len(w) <= 3) else w[:1].upper() + w[1:] for w in text.split()]
    title = " ".join(words)
    if normalize_query(query).split()[:1] and normalize_query(query).split()[0] in _QUESTION_STARTERS:
        title += "?"
    return title


def split_market(market: str) -> tuple[str, str]:
    """'Houston TX' → ('Houston', 'TX'); 'National' → ('National', '')."""
    market = (market or "").strip()
    parts = market.rsplit(" ", 1)
    if len(parts) == 2 and len(parts[1]) == 2 and parts[1].isupper():
        return parts[0], parts[1]
    return market, ""


def select_gsc_candidates(
    current: list[dict],
    previous: list[dict],
    *,
    brand_terms: list[str],
    min_impressions: int = 20,
    max_candidates: int = 5,
) -> list[dict]:
    """Pick demand opportunities from two GSC query-report periods.

    A query qualifies when it has real impressions, is not branded, and is
    either rising vs the prior period or ranking too weak to earn clicks.
    Queries already winning (top-5 position with clicks) are skipped.
    """
    prev_by_query = {normalize_query(r.get("query", "")): r for r in previous}
    out: list[dict] = []
    for row in current:
        query = (row.get("query") or "").strip()
        impressions = int(row.get("impressions") or 0)
        clicks = int(row.get("clicks") or 0)
        position = float(row.get("position") or 0)
        if not query or impressions < min_impressions:
            continue
        if is_branded_query(query, brand_terms):
            continue
        if len(query_tokens(query)) < 2:  # single-token queries are too generic to target
            continue
        if position and position <= 5 and clicks > 0:
            continue
        prev_impressions = int((prev_by_query.get(normalize_query(query)) or {}).get("impressions") or 0)
        rising = prev_impressions == 0 or impressions >= prev_impressions * 1.5
        weak = position > 8 or clicks == 0
        if not (rising or weak):
            continue
        trigger = "rising_demand" if rising and not weak else ("weak_position" if weak and not rising else "rising_and_weak")
        out.append(
            {
                "query": query,
                "impressions": impressions,
                "prev_impressions": prev_impressions,
                "clicks": clicks,
                "position": round(position, 1),
                "trigger": trigger,
            }
        )
    out.sort(key=lambda r: -r["impressions"])
    return out[:max_candidates]


class TopicDiscoveryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.gsc = GSCService()

    async def discover(self, brand_ids: list[str] | None = None) -> dict:
        """Discover topics for all (or given) brands and enqueue them."""
        brands_q = select(Brand)
        if brand_ids:
            brands_q = brands_q.where(Brand.id.in_(brand_ids))
        brands = list((await self.db.execute(brands_q)).scalars().all())

        gaps_by_brand = await self._gap_rows_by_brand()
        existing = await self._existing_queries_by_brand()

        max_per_brand = max(1, self.settings.topic_discovery_max_per_brand)
        max_total = max(1, self.settings.topic_discovery_max_total)

        queued: list[dict] = []
        sources_active = {"citation_gap": bool(gaps_by_brand), "search_demand": False, "coverage": True}

        for brand in brands:
            if len(queued) >= max_total:
                break
            candidates = self._from_gaps(brand, gaps_by_brand.get(brand.id, []))
            gsc_candidates = await self._from_gsc(brand)
            if gsc_candidates:
                sources_active["search_demand"] = True
            candidates += gsc_candidates
            candidates += self._from_coverage(brand, existing.get(brand.id, []))

            picked: list[dict] = []
            known = list(existing.get(brand.id, []))
            for cand in candidates:
                if len(picked) >= max_per_brand or len(queued) + len(picked) >= max_total:
                    break
                if any(queries_similar(cand["target_query"], k) for k in known):
                    continue
                known.append(cand["target_query"])
                picked.append(cand)

            for cand in picked:
                item = ContentQueue(
                    brand_id=brand.id,
                    content_type=cand["content_type"],
                    target_query=cand["target_query"],
                    title=cand["title"],
                    priority=cand["priority"],
                    status="pending",
                    source=cand["source"],
                    source_detail=cand.get("source_detail"),
                    source_citation_id=cand.get("source_citation_id"),
                )
                self.db.add(item)
                queued.append(
                    {
                        "brand_id": brand.id,
                        "target_query": cand["target_query"],
                        "title": cand["title"],
                        "content_type": cand["content_type"],
                        "priority": cand["priority"],
                        "source": cand["source"],
                    }
                )
            existing[brand.id] = known

        await self.db.flush()
        return {"count": len(queued), "queued": queued, "sources_active": sources_active}

    async def _gap_rows_by_brand(self) -> dict[str, list[dict]]:
        from app.services.report_service import ReportService

        try:
            gaps = await ReportService(self.db).get_gap_queries()
        except Exception as e:  # citation data optional — discovery must not die on it
            logger.warning("Topic discovery: gap lookup failed: %s", e)
            return {}
        by_brand: dict[str, list[dict]] = {}
        for gap in gaps:
            by_brand.setdefault(gap["brand_id"], []).append(gap)
        for rows in by_brand.values():
            rows.sort(key=lambda g: (not g.get("competitor_cited"), -(g.get("visibility_pct") or 0)))
        return by_brand

    async def _existing_queries_by_brand(self) -> dict[str, list[str]]:
        """Everything already queued, drafted, or published — the dedup corpus."""
        existing: dict[str, list[str]] = {}

        def _add(brand_id: str, *texts: str | None) -> None:
            for text in texts:
                if text and text.strip():
                    existing.setdefault(brand_id, []).append(text.strip())

        for row in (await self.db.execute(select(ContentQueue.brand_id, ContentQueue.target_query, ContentQueue.title))).all():
            _add(row[0], row[1], row[2])
        for row in (await self.db.execute(select(ContentDraft.brand_id, ContentDraft.target_query, ContentDraft.title))).all():
            _add(row[0], row[1], row[2])
        for row in (await self.db.execute(select(ContentPiece.brand_id, ContentPiece.target_query, ContentPiece.title))).all():
            _add(row[0], row[1], row[2])
        return existing

    def _from_gaps(self, brand: Brand, gaps: list[dict]) -> list[dict]:
        candidates = []
        for gap in gaps:
            query = (gap.get("query") or "").strip()
            if not query:
                continue
            competitor_won = bool(gap.get("competitor_cited"))
            candidates.append(
                {
                    "target_query": query,
                    "title": derive_title(query),
                    "content_type": gap.get("recommended_content_type")
                    or infer_content_type(query, brand.markets),
                    "priority": 1 if competitor_won else 3,
                    "source": "citation_gap",
                    "source_detail": {
                        "platform": gap.get("platform"),
                        "competitor_cited": gap.get("competitor_cited"),
                        "visibility_pct": gap.get("visibility_pct"),
                    },
                    "source_citation_id": gap.get("id"),
                }
            )
        return candidates

    async def _from_gsc(self, brand: Brand) -> list[dict]:
        if not brand.gsc_site_url:
            return []
        current, previous = await self.gsc.get_query_rows_compare(brand.gsc_site_url)
        if not current:
            return []
        rows = select_gsc_candidates(
            current,
            previous,
            brand_terms=brand_search_terms(brand.name, brand.wp_url),
            min_impressions=self.settings.topic_discovery_min_impressions,
            max_candidates=max(1, self.settings.topic_discovery_max_per_brand) * 2,
        )
        return [
            {
                "target_query": row["query"],
                "title": derive_title(row["query"]),
                "content_type": infer_content_type(row["query"], brand.markets),
                "priority": 3,
                "source": "search_demand",
                "source_detail": {
                    "impressions": row["impressions"],
                    "prev_impressions": row["prev_impressions"],
                    "clicks": row["clicks"],
                    "position": row["position"],
                    "trigger": row["trigger"],
                },
            }
            for row in rows
        ]

    def _from_coverage(self, brand: Brand, existing: list[str]) -> list[dict]:
        """Fallback: markets without a local page, then uncovered bank queries."""
        candidates: list[dict] = []
        markets = [m for m in (brand.markets or []) if m and m.lower() != "national"]

        for market in markets:
            query = f"elevator service {market}"
            if any(queries_similar(query, k) for k in existing):
                continue
            candidates.append(
                {
                    "target_query": query,
                    "title": f"Elevator Service in {market}",
                    "content_type": "local_page",
                    "priority": 3,
                    "source": "coverage",
                    "source_detail": {"reason": "market_without_local_page", "market": market},
                }
            )

        city, state = split_market(markets[0]) if markets else ("", "")
        for bank_item in sorted(get_all_queries(), key=lambda i: i["priority_num"]):
            query = interpolate_query(bank_item["query"], city=city, state=state).strip()
            if "{" in query or not query:
                continue
            if any(queries_similar(query, k) for k in existing):
                continue
            candidates.append(
                {
                    "target_query": query,
                    "title": derive_title(query),
                    "content_type": CATEGORY_CONTENT_TYPE.get(bank_item["category"], "faq_hub"),
                    "priority": min(5, max(1, bank_item["priority_num"])),
                    "source": "coverage",
                    "source_detail": {"reason": "query_bank_uncovered", "category": bank_item["category"]},
                }
            )
        return candidates
