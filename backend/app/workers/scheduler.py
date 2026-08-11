import asyncio
import logging
from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.workers.advisor_worker import run_improvement_advisor
from app.workers.citation_worker import run_citation_audit
from app.workers.content_refresh_worker import run_content_refresh
from app.workers.content_worker import run_daily_content
from app.workers.flow_health_worker import run_flow_health
from app.workers.posting_monitor_worker import run_posting_monitor
from app.workers.report_worker import run_monthly_report
from app.workers.schema_publish_worker import run_daily_schema_publish
from app.workers.schema_worker import run_schema_validation
from app.workers.topic_worker import run_topic_discovery

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Chicago")


async def _record_job_run(job_id: str, status: str, detail: str | None, scheduled_for):
    """Persist one JobRun row — lets the health check tell 'job ran and
    produced nothing' from 'job never ran'. Never raises."""
    try:
        from app.database import AsyncSessionLocal
        from app.models.approval import JobRun

        scheduled_naive = None
        if scheduled_for is not None:
            scheduled_naive = scheduled_for.astimezone(tz=None).replace(tzinfo=None)
        async with AsyncSessionLocal() as session:
            session.add(
                JobRun(
                    job_id=job_id,
                    status=status,
                    detail=(detail or "")[:500] or None,
                    scheduled_for=scheduled_naive,
                )
            )
            await session.commit()
    except Exception:
        logger.warning("Failed to record job run for %s", job_id, exc_info=True)


def _on_job_event(event):
    status = "ok"
    detail = None
    if event.code == EVENT_JOB_ERROR:
        status = "error"
        detail = str(getattr(event, "exception", "") or "")
    elif event.code == EVENT_JOB_MISSED:
        status = "missed"
    try:
        asyncio.get_event_loop().create_task(
            _record_job_run(event.job_id, status, detail, getattr(event, "scheduled_run_time", None))
        )
    except Exception:
        logger.warning("Failed to schedule job-run record for %s", event.job_id, exc_info=True)


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
    # Mid-afternoon, hours after the 9am content run has published — verifies
    # each brand's live WP site actually received today's posts and alerts
    # Discord when one went silent.
    scheduler.add_job(
        run_posting_monitor,
        CronTrigger(hour=15, minute=0),
        id="posting_monitor",
        replace_existing=True,
    )
    # Mid-morning, after discovery (8am), generation (9am), and schema (10am)
    # have all run — diagnoses every stage of the flow and alerts Discord when
    # anything failed or produced nothing. The escalation layer the August
    # 2026 silent outage was missing.
    scheduler.add_job(
        run_flow_health,
        CronTrigger(hour=10, minute=30),
        id="flow_health",
        replace_existing=True,
    )
    # Weekly AI improvement advisor — what to improve and why, from live data.
    scheduler.add_job(
        run_improvement_advisor,
        CronTrigger(day_of_week="mon", hour=7, minute=0),
        id="improvement_advisor",
        replace_existing=True,
    )
    # Outcome record per firing (ok/error/missed) → aeo.job_runs, so health
    # checks can tell "ran and produced nothing" from "never ran".
    scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)
    logger.info("APScheduler configured with 10 cron jobs (America/Chicago)")


def start_scheduler():
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("APScheduler started at %s", datetime.utcnow())


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
