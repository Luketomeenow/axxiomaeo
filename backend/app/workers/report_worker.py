import logging

from app.database import AsyncSessionLocal
from app.services.notification_service import NotificationService, record_worker_error
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)


async def run_monthly_report():
    logger.info("Starting monthly report generation")
    async with AsyncSessionLocal() as session:
        try:
            service = ReportService(session)
            report = await service.generate_monthly_report()
            notifications = NotificationService(session)
            await notifications.create(
                type="report_ready",
                title="Monthly AEO report ready",
                body=f"Citation share: {report.overall_citation_share}%",
            )
            await session.commit()
            logger.info("Monthly report generated: id=%s", report.id)
        except Exception as e:
            logger.exception("Monthly report failed: %s", e)
            await record_worker_error(session, "monthly_report", str(e))
            await session.commit()
