"""Daily customer-question scan (7:15am CT, before the 8am topic discovery).

Reads new CallRail call summaries from the marketing warehouse and stores the
questions callers asked as observed questions, so the same morning's
discovery can pick them up. Quiet when it works; a failure is a worker error.
"""

import logging

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.notification_service import record_worker_error

logger = logging.getLogger(__name__)


async def run_call_questions():
    if not get_settings().call_questions_enabled:
        logger.info("Call question scan disabled (CALL_QUESTIONS_ENABLED=false)")
        return

    from app.services.call_questions_service import CallQuestionsService

    async with AsyncSessionLocal() as session:
        try:
            result = await CallQuestionsService(session).run()
            await session.commit()
            if result.get("status") != "ok":
                logger.warning("Call question scan: %s", result.get("message"))
                await record_worker_error(session, "call_questions", result.get("message", "scan failed"))
                await session.commit()
                return
            logger.info(
                "Call question scan: %s call(s) scanned, %s new question(s) stored",
                result.get("calls_scanned"), result.get("stored"),
            )
        except Exception as e:
            logger.exception("Call question scan failed: %s", e)
            await session.rollback()
            await record_worker_error(session, "call_questions", str(e))
            await session.commit()
