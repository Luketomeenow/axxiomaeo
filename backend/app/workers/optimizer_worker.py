"""Optimization agent jobs.

Weekly analysis (Monday 7:30am CT, after the 7am improvement advisor): adds
new proposals to System Health and posts a short digest so someone decides
on them. Sync (every 15 minutes, only when something is in flight): follows
approved code changes through GitHub and announces each pull request.
"""

import logging

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.notification_service import NotificationService, record_worker_error

logger = logging.getLogger(__name__)


async def run_optimizer():
    settings = get_settings()
    if not settings.optimizer_enabled:
        logger.info("Optimization agent disabled (OPTIMIZER_ENABLED=false)")
        return

    from app.services.optimizer_service import OptimizerService

    async with AsyncSessionLocal() as session:
        try:
            result = await OptimizerService(session).generate(trigger="scheduled")
            if result.get("status") != "ok":
                await record_worker_error(session, "optimizer", result.get("message", "analysis failed"))
                await session.commit()
                return
            created = result.get("created", [])
            if created:
                lines = [f"• [{p['priority']}] {p['title']}" for p in created[:6]]
                body = (result.get("summary") or "") + "\n" + "\n".join(lines)
                body += f"\nDecide on System Health: {settings.frontend_url}/health"
                await NotificationService(session).create(
                    type="optimizer",
                    title=f"Optimization agent: {len(created)} new proposal(s)",
                    body=body.strip(),
                )
            await session.commit()
            logger.info("Optimization agent added %s proposal(s)", len(created))
        except Exception as e:
            logger.exception("Optimization agent failed: %s", e)
            await session.rollback()
            await record_worker_error(session, "optimizer", str(e))
            await session.commit()


async def run_optimizer_sync():
    settings = get_settings()
    if not settings.optimizer_enabled or not settings.optimizer_github_token:
        return

    from app.services.optimizer_service import OptimizerService

    async with AsyncSessionLocal() as session:
        try:
            await OptimizerService(session).sync_in_flight()
            await session.commit()
        except Exception as e:
            logger.warning("Optimizer sync failed: %s", e)
            await session.rollback()
