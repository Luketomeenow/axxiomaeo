import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.workers.citation_worker import run_citation_audit
from app.workers.content_refresh_worker import run_content_refresh
from app.workers.content_worker import run_daily_content
from app.workers.report_worker import run_monthly_report
from app.workers.schema_publish_worker import run_daily_schema_publish
from app.workers.schema_worker import run_schema_validation
from app.workers.topic_worker import run_topic_discovery

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Chicago")


def setup_scheduler():
    # One hour before content generation so new topics flow into the same run.
    scheduler.add_job(
        run_topic_discovery,
        CronTrigger(hour=8, minute=0),
        id="topic_discovery",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_content,
        CronTrigger(hour=9, minute=0),
        id="daily_content",
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
    # One brand-schema per brand per day (self-healing). No-op unless
    # SCHEMA_AUTO_PUBLISH_ENABLED=true. Runs after daily content (9am).
    scheduler.add_job(
        run_daily_schema_publish,
        CronTrigger(hour=10, minute=0),
        id="daily_schema_publish",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly_report,
        CronTrigger(day="last", hour=23, minute=0),
        id="monthly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_content_refresh,
        CronTrigger(day_of_week="sun", hour=6, minute=0),
        id="content_refresh",
        replace_existing=True,
    )
    logger.info("APScheduler configured with 7 cron jobs (America/Chicago)")


def start_scheduler():
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("APScheduler started at %s", datetime.utcnow())


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
