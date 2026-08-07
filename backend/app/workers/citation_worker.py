"""Bi-weekly citation audit — asks AI engines the queries we care about.

Query composition is demand-driven (v13): each brand's ~30 audit slots are
filled in trust order — custom brand queries, recently-published posts' target
queries ("did we win what we published for?"), real GSC demand, observed
customer questions from GHL, and finally the curated query bank round-robin
across its categories so every category keeps representation (the old
declaration-order truncation silently dropped 4 of the 6 bank categories).
Real-demand queries are audited verbatim; only bank queries get fan-out
variants. Every record carries ``query_source`` provenance, and
``cited_post_id`` links a citation of our own URL back to the ContentPiece.
"""

import logging
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.citation import CitationRecord
from app.models.content import ContentPiece
from app.models.observed_question import ObservedQuestion
from app.services.citation_service import CitationService
from app.services.geo_aeo_tracker_service import QueryAuditMeta
from app.services.gsc_service import GSCService
from app.services.notification_service import NotificationService, record_worker_error
from app.services.topic_discovery_service import (
    brand_search_terms,
    normalize_query,
    queries_similar,
    select_gsc_candidates,
)
from app.utils.query_bank import QUERY_BANK, interpolate_query
from app.utils.query_fanout import CATEGORY_FUNNEL_STAGE, expand_queries_with_fanout

logger = logging.getLogger(__name__)

# A GSC query must look elevator-related to spend audit budget on it — Search
# Console can surface stray queries (careers, unrelated blog hits) that would
# waste Bright Data calls. select_gsc_candidates already drops branded terms.
_RELEVANCE_HINTS = ("elevator", "escalator", "lift", "dumbwaiter", "modernization")


def _url_key(url: str) -> str:
    """Normalized host+path for URL equality: lowercase, no www, no trailing
    slash, query/fragment dropped."""
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower().replace("www.", "")
    if not host and "//" not in (url or ""):
        parsed = urlparse(f"//{url.strip()}")
        host = parsed.netloc.lower().replace("www.", "")
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}" if host else ""


def _bank_candidates_by_category(brand: Brand) -> dict[str, list[str]]:
    """Bank queries per category with the brand's market interpolation applied."""
    by_cat: dict[str, list[str]] = {}
    for category, data in QUERY_BANK.items():
        items: list[str] = []
        for q in data["queries"]:
            if "{city}" in q and brand.markets:
                for market in brand.markets[:3]:
                    parts = market.rsplit(" ", 1)
                    city = parts[0] if len(parts) > 1 else market
                    state = parts[1] if len(parts) > 1 else ""
                    items.append(interpolate_query(q, city, state))
            elif "{state}" in q and brand.markets:
                states: set[str] = set()
                for market in brand.markets[:5]:
                    parts = market.rsplit(" ", 1)
                    if len(parts) > 1:
                        states.add(parts[1])
                for state in sorted(states):
                    items.append(interpolate_query(q, "", state))
            elif "{state}" not in q and "{city}" not in q:
                items.append(q)
        by_cat[category] = items
    return by_cat


def _build_brand_queries(
    brand: Brand,
    *,
    published: list[str],
    gsc: list[str],
    observed: list[str],
    settings,
) -> tuple[list[str], dict[str, dict]]:
    """Compose the audit query set from demand sources + the bank.

    Pure/sync — callers fetch the pools. Slot order: custom (uncapped),
    published, gsc, ghl (each capped), then bank round-robin across categories
    filling the remaining budget (each bank seed brings one fan-out variant).
    """
    budget = max(1, settings.citation_audit_max_queries)
    accepted: list[dict] = []  # {query, category, source}

    def try_add(query: str | None, category: str, source: str) -> bool:
        text = (query or "").strip()
        if not text or len(accepted) >= budget:
            return False
        if any(queries_similar(text, a["query"]) for a in accepted):
            return False
        accepted.append({"query": text, "category": category, "source": source})
        return True

    for q in brand.target_queries or []:
        if isinstance(q, str):
            try_add(q, "custom", "custom")

    for cap, pool, category, source in (
        (settings.citation_audit_published_slots, published, "published", "published"),
        (settings.citation_audit_gsc_slots, gsc, "gsc", "gsc"),
        (settings.citation_audit_ghl_slots, observed, "observed", "ghl"),
    ):
        added = 0
        for q in pool:
            if added >= max(0, cap):
                break
            if try_add(q, category, source):
                added += 1

    # Bank fill: one query per category per pass, categories in priority
    # order, until the remaining budget is spoken for. The seed list stays
    # round-robin-ordered so fan-out truncation can't starve a category.
    remaining = budget - len(accepted)
    bank_seeds: list[dict] = []
    if remaining > 0:
        queues = _bank_candidates_by_category(brand)
        cat_order = sorted(QUERY_BANK, key=lambda c: QUERY_BANK[c]["priority_num"])
        # Each seed expands to itself + up to 1 variant, so seeds beyond
        # remaining can never survive expand_queries_with_fanout's cap.
        while len(bank_seeds) < remaining and any(queues.get(c) for c in cat_order):
            for category in cat_order:
                if len(bank_seeds) >= remaining:
                    break
                queue = queues.get(category) or []
                while queue:
                    candidate = queue.pop(0)
                    if any(
                        queries_similar(candidate, a["query"])
                        for a in accepted + bank_seeds
                    ):
                        continue
                    bank_seeds.append({"query": candidate, "category": category, "source": "bank"})
                    break

    expanded_bank = expand_queries_with_fanout(
        bank_seeds, max_total=max(0, remaining), fanout_per_seed=1
    )

    query_strings: list[str] = []
    meta_by_query: dict[str, dict] = {}
    for item in accepted:
        meta_by_query[item["query"]] = {
            "category": item["category"],
            "source": item["source"],
            "parent_query": None,
            "funnel_stage": CATEGORY_FUNNEL_STAGE.get(item["category"], "consideration"),
        }
        query_strings.append(item["query"])
    for item in expanded_bank:
        if item["query"] in meta_by_query:
            continue
        meta_by_query[item["query"]] = {
            "category": item["category"],
            "source": "bank",
            "parent_query": item.get("parent_query"),
            "funnel_stage": item.get("funnel_stage"),
        }
        query_strings.append(item["query"])
    return query_strings, meta_by_query


async def _published_queries_by_brand(settings) -> dict[str, list[str]]:
    """Recent published posts' target queries, newest first, exact-deduped."""
    cutoff = datetime.utcnow() - timedelta(days=max(1, settings.citation_audit_published_days))
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(ContentPiece.brand_id, ContentPiece.target_query)
                .where(
                    ContentPiece.status == "published",
                    ContentPiece.published_at >= cutoff,
                    ContentPiece.target_query.isnot(None),
                )
                .order_by(ContentPiece.published_at.desc())
            )
        ).all()
    pools: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for brand_id, query in rows:
        key = normalize_query(query or "")
        if not key or key in seen.setdefault(brand_id, set()):
            continue
        seen[brand_id].add(key)
        pools.setdefault(brand_id, []).append(query.strip())
    return pools


async def _observed_questions_by_brand() -> dict[str, list[str]]:
    """Observed customer questions (GHL calls/chats/forms), newest first."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(ObservedQuestion.brand_id, ObservedQuestion.question)
                .where(ObservedQuestion.created_at >= cutoff)
                .order_by(ObservedQuestion.created_at.desc())
            )
        ).all()
    pools: dict[str, list[str]] = {}
    for brand_id, question in rows:
        if question and question.strip():
            pools.setdefault(brand_id, []).append(question.strip())
    return pools


async def _gsc_queries_for_brand(brand: Brand, settings) -> list[str]:
    """Real Google demand worth auditing on AI engines. Failure → [] so a GSC
    hiccup never sinks the audit."""
    if not brand.gsc_site_url:
        return []
    try:
        current, previous = await GSCService().get_query_rows_compare(brand.gsc_site_url)
        if not current:
            return []
        rows = select_gsc_candidates(
            current,
            previous,
            brand_terms=brand_search_terms(brand.name, brand.wp_url),
            min_impressions=settings.citation_audit_gsc_min_impressions,
            max_candidates=max(1, settings.citation_audit_gsc_slots) * 3,
        )
    except Exception as e:
        logger.warning("Citation audit: GSC pool failed for %s: %s", brand.id, e)
        return []
    return [
        row["query"]
        for row in rows
        if any(hint in normalize_query(row["query"]) for hint in _RELEVANCE_HINTS)
    ]


async def _published_posts_by_url(brand_id: str) -> dict[str, int]:
    """{normalized wp_post_url: ContentPiece.id} for ALL published posts of a
    brand — matched against citation URLs to prove "the AI cited our post"."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(ContentPiece.id, ContentPiece.wp_post_url).where(
                    ContentPiece.brand_id == brand_id,
                    ContentPiece.status == "published",
                    ContentPiece.wp_post_url.isnot(None),
                )
            )
        ).all()
    out: dict[str, int] = {}
    for piece_id, url in rows:
        key = _url_key(url)
        if key:
            out.setdefault(key, piece_id)
    return out


async def _notify_provider_unavailable(reason: str, brand_id: str | None = None):
    async with AsyncSessionLocal() as session:
        notifications = NotificationService(session)
        await notifications.create(
            type="citation_manual",
            title="Citation audit skipped — provider unavailable",
            body=reason,
        )
        await record_worker_error(
            session,
            "citation_audit",
            reason,
            error_details={"brand_id": brand_id} if brand_id else None,
            notify=False,  # the citation_manual notification above already alerts
        )
        await session.commit()


async def run_citation_audit():
    logger.info("Starting citation audit")
    settings = get_settings()
    citation_service = CitationService()

    if not await citation_service.provider_available():
        reason = citation_service.unavailable_reason()
        logger.warning("Citation audit skipped — %s", reason)
        await _notify_provider_unavailable(reason)
        return

    async with AsyncSessionLocal() as session:
        brands = list((await session.execute(select(Brand))).scalars().all())

    if not brands:
        logger.info("Citation audit: no brands configured")
        return

    published_pools = await _published_queries_by_brand(settings)
    observed_pools = await _observed_questions_by_brand()

    audit_run_id = str(uuid.uuid4())

    for brand in brands:
        gsc_pool = await _gsc_queries_for_brand(brand, settings)
        query_strings, meta_by_query = _build_brand_queries(
            brand,
            published=published_pools.get(brand.id, []),
            gsc=gsc_pool,
            observed=observed_pools.get(brand.id, []),
            settings=settings,
        )
        if not query_strings:
            continue

        query_meta = {
            q: QueryAuditMeta(
                parent_query=meta_by_query[q].get("parent_query"),
                funnel_stage=meta_by_query[q].get("funnel_stage"),
            )
            for q in query_strings
        }
        results, status = await citation_service.run_audit(brand, query_strings, query_meta=query_meta)

        posts_by_url = await _published_posts_by_url(brand.id)

        async with AsyncSessionLocal() as session:
            notifications = NotificationService(session)
            if status == "manual_required":
                reason = citation_service.unavailable_reason()
                await notifications.create(
                    type="citation_manual",
                    title=f"Citation audit requires manual review: {brand.name}",
                    body=reason,
                )
                await record_worker_error(
                    session,
                    "citation_audit",
                    reason,
                    error_details={"brand_id": brand.id},
                    notify=False,  # the citation_manual notification above already alerts
                )
                await session.commit()
                continue

            for result in results:
                qmeta = meta_by_query.get(result.query, {})
                cited_post_id = None
                if result.citation_url:
                    cited_post_id = posts_by_url.get(_url_key(result.citation_url))
                session.add(
                    CitationRecord(
                        brand_id=brand.id,
                        query=result.query,
                        query_category=qmeta.get("category", "unknown"),
                        query_source=qmeta.get("source", "bank"),
                        platform=result.platform,
                        is_cited=result.is_cited,
                        is_mentioned=result.is_mentioned,
                        is_url_cited=result.is_url_cited,
                        visibility_pct=result.visibility_pct,
                        sample_runs=result.sample_runs,
                        parent_query=result.parent_query or qmeta.get("parent_query"),
                        funnel_stage=result.funnel_stage or qmeta.get("funnel_stage"),
                        competitor_cited=result.competitor_cited,
                        citation_url=result.citation_url,
                        cited_post_id=cited_post_id,
                        audit_run_id=audit_run_id,
                    )
                )
            await session.commit()

    async with AsyncSessionLocal() as session:
        notifications = NotificationService(session)
        await notifications.create(
            type="citation_complete",
            title="Bi-weekly citation audit complete",
            body="Results available in dashboard",
            send_slack=True,
        )
        await session.commit()

    logger.info("Citation audit complete")
