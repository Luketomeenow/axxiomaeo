import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.models.brand import Brand
from app.models.citation import CitationRecord
from app.services.citation_service import CitationService
from app.services.notification_service import NotificationService
from app.utils.query_bank import QUERY_BANK, interpolate_query

logger = logging.getLogger(__name__)


def _query_category_map(queries: list[dict]) -> dict[str, str]:
    return {item["query"]: item["category"] for item in queries}


def _build_brand_queries(brand: Brand) -> tuple[list[str], dict[str, str]]:
    queries: list[dict] = []
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
            elif "{state}" not in q and "{city}" not in q:
                queries.append({"query": q, "category": category})

    query_strings = [q["query"] for q in queries[:30]]
    return query_strings, _query_category_map(queries)


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

    for brand in brands:
        query_strings, category_by_query = _build_brand_queries(brand)
        if not query_strings:
            continue

        results, status = await citation_service.run_audit(brand, query_strings)

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
                session.add(
                    CitationRecord(
                        brand_id=brand.id,
                        query=result.query,
                        query_category=category_by_query.get(result.query, "unknown"),
                        platform=result.platform,
                        is_cited=result.is_cited,
                        competitor_cited=result.competitor_cited,
                        citation_url=result.citation_url,
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
