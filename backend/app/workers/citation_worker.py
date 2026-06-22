import logging
import uuid

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.models.brand import Brand
from app.models.citation import CitationRecord
from app.services.citation_service import CitationService
from app.services.geo_aeo_tracker_service import QueryAuditMeta
from app.services.notification_service import NotificationService
from app.utils.query_bank import QUERY_BANK, interpolate_query
from app.utils.query_fanout import CATEGORY_FUNNEL_STAGE, expand_queries_with_fanout

logger = logging.getLogger(__name__)


def _build_brand_queries(brand: Brand) -> tuple[list[str], dict[str, dict]]:
    queries: list[dict] = []

    for custom in brand.target_queries or []:
        if isinstance(custom, str) and custom.strip():
            queries.append({"query": custom.strip(), "category": "custom"})

    for category, data in QUERY_BANK.items():
        for q in data["queries"]:
            if "{city}" in q and brand.markets:
                for market in brand.markets[:3]:
                    parts = market.rsplit(" ", 1)
                    city = parts[0] if len(parts) > 1 else market
                    state = parts[1] if len(parts) > 1 else ""
                    queries.append(
                        {
                            "query": interpolate_query(q, city, state),
                            "category": category,
                        }
                    )
            elif "{state}" in q and brand.markets:
                states = set()
                for market in brand.markets[:5]:
                    parts = market.rsplit(" ", 1)
                    if len(parts) > 1:
                        states.add(parts[1])
                for state in states:
                    queries.append(
                        {
                            "query": interpolate_query(q, "", state),
                            "category": category,
                        }
                    )
            elif "{state}" not in q and "{city}" not in q:
                queries.append({"query": q, "category": category})

    seen: set[str] = set()
    unique: list[dict] = []
    for item in queries:
        if item["query"] not in seen:
            seen.add(item["query"])
            item["funnel_stage"] = CATEGORY_FUNNEL_STAGE.get(item["category"], "consideration")
            unique.append(item)

    expanded = expand_queries_with_fanout(unique[:20], max_total=30, fanout_per_seed=1)

    query_strings = [q["query"] for q in expanded]
    meta_by_query = {
        q["query"]: {
            "category": q["category"],
            "parent_query": q.get("parent_query"),
            "funnel_stage": q.get("funnel_stage"),
        }
        for q in expanded
    }
    return query_strings, meta_by_query


async def _notify_tracker_unavailable(brand_id: str | None = None):
    async with AsyncSessionLocal() as session:
        notifications = NotificationService(session)
        await notifications.create(
            type="citation_manual",
            title="Citation audit skipped — tracker unavailable",
            body="Start GEO/AEO Tracker on :3000 with Bright Data keys, or set CITATION_PROVIDER=none",
        )
        session.add(
            WorkerError(
                worker_name="citation_audit",
                error_message="Citation provider unavailable",
                error_details={"brand_id": brand_id} if brand_id else None,
            )
        )
        await session.commit()


async def run_citation_audit():
    logger.info("Starting citation audit")
    citation_service = CitationService()

    if not await citation_service.provider_available():
        logger.warning("Citation audit skipped — provider unavailable")
        await _notify_tracker_unavailable()
        return

    async with AsyncSessionLocal() as session:
        brands = list((await session.execute(select(Brand))).scalars().all())

    if not brands:
        logger.info("Citation audit: no brands configured")
        return

    audit_run_id = str(uuid.uuid4())

    for brand in brands:
        query_strings, meta_by_query = _build_brand_queries(brand)
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

        async with AsyncSessionLocal() as session:
            notifications = NotificationService(session)
            if status == "manual_required":
                await notifications.create(
                    type="citation_manual",
                    title=f"Citation audit requires manual review: {brand.name}",
                    body="Citation provider unavailable — check GEO_AEO_TRACKER_URL or CITATION_PROVIDER",
                )
                session.add(
                    WorkerError(
                        worker_name="citation_audit",
                        error_message="Citation provider unavailable",
                        error_details={"brand_id": brand.id},
                    )
                )
                await session.commit()
                continue

            for result in results:
                qmeta = meta_by_query.get(result.query, {})
                session.add(
                    CitationRecord(
                        brand_id=brand.id,
                        query=result.query,
                        query_category=qmeta.get("category", "unknown"),
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
