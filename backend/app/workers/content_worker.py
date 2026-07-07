import asyncio
import logging

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.content import ContentQueue
from app.services.content_service import ContentGenerationService
from app.services.notification_service import record_worker_error

logger = logging.getLogger(__name__)


async def run_daily_content():
    settings = get_settings()
    per_brand_limit = max(1, settings.content_generation_max_per_brand)
    logger.info(
        "Starting daily content generation (per_brand_limit=%s, auto_publish=%s)",
        per_brand_limit,
        settings.auto_publish_enabled,
    )

    async with AsyncSessionLocal() as session:
        try:
            brands = list((await session.execute(select(Brand).order_by(Brand.id))).scalars().all())

            # Per-brand, not one global LIMIT — a global limit has no
            # fairness guarantee: one brand's backlog can starve every
            # other brand's queue item for the whole run.
            items = []
            for brand in brands:
                result = await session.execute(
                    select(ContentQueue)
                    .where(ContentQueue.status == "pending", ContentQueue.brand_id == brand.id)
                    .order_by(ContentQueue.priority, ContentQueue.scheduled_for)
                    .limit(per_brand_limit)
                )
                items.extend(result.scalars().all())

            if not items:
                logger.info("No pending content in queue")
                return

            for queue_item in items:
                queue_item.status = "in_progress"
            await session.flush()

            service = ContentGenerationService(session)
            for queue_item in items:
                try:
                    draft = await service.generate_draft(
                        brand_id=queue_item.brand_id,
                        content_type=queue_item.content_type or "faq_hub",
                        target_query=queue_item.target_query or "",
                        title=queue_item.title or "",
                        queue_id=queue_item.id,
                    )
                    logger.info("Daily content draft created for queue item %s", queue_item.id)
                except Exception as e:
                    logger.exception("Failed queue item %s: %s", queue_item.id, e)
                    queue_item.status = "pending"
                    await record_worker_error(
                        session,
                        "daily_content",
                        str(e),
                        error_details={"queue_id": queue_item.id},
                    )
                    continue

                # Monitor-after model: drafts that PASS validation publish to
                # their own brand immediately. Invalid drafts still stop in
                # needs_review; a failed publish keeps the draft in
                # pending_review and alerts, so nothing is ever lost.
                if settings.auto_publish_enabled and draft is not None and draft.status == "pending_review":
                    try:
                        result = await service.approve_and_publish(draft.id, user_id="auto-publish")
                        # Persist immediately so a later item's failure can't
                        # roll back a publish that already hit WordPress.
                        await session.commit()
                        logger.info(
                            "Auto-published draft %s → %s", draft.id, result.get("post_url")
                        )
                    except Exception as e:
                        logger.exception("Auto-publish failed for draft %s: %s", draft.id, e)
                        await record_worker_error(
                            session,
                            "daily_content",
                            f"Auto-publish failed for draft {draft.id} ({queue_item.brand_id}): {e}",
                            error_details={"draft_id": draft.id, "queue_id": queue_item.id},
                        )

            await session.commit()
        except Exception as e:
            logger.exception("Daily content job failed: %s", e)
            await record_worker_error(session, "daily_content", str(e))
            await session.commit()

    await asyncio.sleep(0)
