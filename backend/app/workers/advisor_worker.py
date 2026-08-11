"""Weekly Improvement Advisor run — Monday 7am CT, before the week's work.

Generates and persists a fresh advisor report and posts the summary (plus the
top high-priority items) to the general Discord channel.
"""

import logging

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.advisor_service import AdvisorService
from app.services.notification_service import NotificationService, record_worker_error

logger = logging.getLogger(__name__)


async def run_improvement_advisor():
    settings = get_settings()
    if not settings.advisor_enabled:
        logger.info("Improvement advisor disabled (ADVISOR_ENABLED=false)")
        return

    logger.info("Starting weekly improvement advisor")
    async with AsyncSessionLocal() as session:
        try:
            result = await AdvisorService(session).generate(trigger="scheduled")
            if result.get("status") != "ok":
                logger.warning("Improvement advisor: %s", result.get("message"))
                await session.commit()
                return

            report = result["report"]
            top = [
                i["title"]
                for i in report.get("improvements", [])
                if i.get("priority") == "high"
            ][:3]
            body = report.get("summary", "")
            if top:
                body += "\nTop priorities: " + "; ".join(top)
            body += f"\nFull report: {settings.frontend_url}/advisor"
            await NotificationService(session).create(
                type="advisor_report",
                title="Weekly improvement advisor",
                body=body,
            )
            await session.commit()
            logger.info("Improvement advisor complete (report %s)", report.get("id"))
        except Exception as e:
            logger.exception("Improvement advisor failed: %s", e)
            await record_worker_error(session, "improvement_advisor", str(e))
            await session.commit()
