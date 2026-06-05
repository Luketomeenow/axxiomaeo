import asyncio
import logging

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.models.content import ContentQueue
from app.services.content_service import ContentGenerationService

logger = logging.getLogger(__name__)


async def run_weekly_content():
    batch_size = max(1, get_settings().weekly_content_batch_size)
    logger.info("Starting weekly content generation (batch=%s)", batch_size)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(ContentQueue)
                .where(ContentQueue.status == "pending")
                .order_by(ContentQueue.priority, ContentQueue.scheduled_for)
                .limit(batch_size)
            )
            items = list(result.scalars().all())
            if not items:
                logger.info("No pending content in queue")
                return

            for queue_item in items:
                queue_item.status = "in_progress"
            await session.flush()

            service = ContentGenerationService(session)
            for queue_item in items:
                try:
                    await service.generate_draft(
                        brand_id=queue_item.brand_id,
                        content_type=queue_item.content_type or "faq_hub",
                        target_query=queue_item.target_query or "",
                        title=queue_item.title or "",
                        queue_id=queue_item.id,
                    )
                    logger.info("Weekly content draft created for queue item %s", queue_item.id)
                except Exception as e:
                    logger.exception("Failed queue item %s: %s", queue_item.id, e)
                    queue_item.status = "pending"
                    session.add(
                        WorkerError(
                            worker_name="weekly_content",
                            error_message=str(e),
                            error_details={"queue_id": queue_item.id},
                        )
                    )

            await session.commit()
        except Exception as e:
            logger.exception("Weekly content job failed: %s", e)
            session.add(WorkerError(worker_name="weekly_content", error_message=str(e)))
            await session.commit()

    await asyncio.sleep(0)
