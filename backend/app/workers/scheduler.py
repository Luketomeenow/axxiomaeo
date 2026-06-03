import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.workers.citation_worker import run_citation_audit
from app.workers.content_worker import run_weekly_content
from app.workers.report_worker import run_monthly_report
from app.workers.schema_worker import run_schema_validation

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Chicago")


def setup_scheduler():
    scheduler.add_job(
        run_weekly_content,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_content",
        replace_existing=True,
    )
    scheduler.add_job(
        run_citation_audit,
        CronTrigger(day="1,15", hour=8, minute=0),
        id="citation_audit",
        replace_existing=True,
    )
    scheduler.add_job(
        run_schema_validation,
        CronTrigger(day="1", hour=7, minute=0),
        id="schema_validation",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly_report,
        CronTrigger(day="last", hour=23, minute=0),
        id="monthly_report",
        replace_existing=True,
    )
    logger.info("APScheduler configured with 4 cron jobs (America/Chicago)")


def start_scheduler():
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("APScheduler started at %s", datetime.utcnow())


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
