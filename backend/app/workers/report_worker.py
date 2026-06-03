import logging

from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.services.notification_service import NotificationService
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
            session.add(WorkerError(worker_name="monthly_report", error_message=str(e)))
            await session.commit()
