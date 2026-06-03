import asyncio
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.models.content import ContentQueue
from app.services.content_service import ContentGenerationService

logger = logging.getLogger(__name__)


async def run_weekly_content():
    logger.info("Starting weekly content generation")
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(ContentQueue)
                .where(ContentQueue.status == "pending")
                .order_by(ContentQueue.priority, ContentQueue.scheduled_for)
                .limit(1)
            )
            queue_item = result.scalar_one_or_none()
            if not queue_item:
                logger.info("No pending content in queue")
                return

            queue_item.status = "in_progress"
            await session.flush()

            service = ContentGenerationService(session)
            await service.generate_draft(
                brand_id=queue_item.brand_id,
                content_type=queue_item.content_type or "faq_hub",
                target_query=queue_item.target_query or "",
                title=queue_item.title or "",
                queue_id=queue_item.id,
            )
            await session.commit()
            logger.info("Weekly content draft created for queue item %s", queue_item.id)
            await asyncio.sleep(1)
        except Exception as e:
            logger.exception("Weekly content job failed: %s", e)
            session.add(WorkerError(worker_name="weekly_content", error_message=str(e)))
            await session.commit()
