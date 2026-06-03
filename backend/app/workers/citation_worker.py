import asyncio
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.models.brand import Brand
from app.models.citation import CitationRecord
from app.models.content import ContentQueue
from app.services.citation_service import CitationService
from app.services.content_service import ContentGenerationService
from app.services.notification_service import NotificationService
from app.utils.query_bank import QUERY_BANK, interpolate_query

logger = logging.getLogger(__name__)


async def run_citation_audit():
    logger.info("Starting citation audit")
    async with AsyncSessionLocal() as session:
        try:
            brands = await session.execute(select(Brand))
            citation_service = CitationService()
            notifications = NotificationService(session)

            for brand in brands.scalars().all():
                queries = []
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
                results, status = await citation_service.run_audit(brand.name, query_strings)

                if status == "manual_required":
                    await notifications.create(
                        type="citation_manual",
                        title=f"Citation audit requires manual review: {brand.name}",
                        body="Peec.ai API unavailable",
                    )
                    session.add(
                        WorkerError(
                            worker_name="citation_audit",
                            error_message="Peec.ai unavailable",
                            error_details={"brand_id": brand.id},
                        )
                    )
                    continue

                for i, result in enumerate(results):
                    cat = queries[i]["category"] if i < len(queries) else "unknown"
                    session.add(
                        CitationRecord(
                            brand_id=brand.id,
                            query=result.query,
                            query_category=cat,
                            platform=result.platform,
                            is_cited=result.is_cited,
                            competitor_cited=result.competitor_cited,
                            citation_url=result.citation_url,
                        )
                    )

            await notifications.create(
                type="citation_complete",
                title="Bi-weekly citation audit complete",
                body="Results available in dashboard",
                send_slack=True,
            )
            await session.commit()
            logger.info("Citation audit complete")
        except Exception as e:
            logger.exception("Citation audit failed: %s", e)
            session.add(WorkerError(worker_name="citation_audit", error_message=str(e)))
            await session.commit()
