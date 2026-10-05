"""Scheduled jobs run on the Chicago clock even when the server runs on UTC.
Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_scheduler_timezone.py
"""
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(
    DATABASE_URL="postgresql://u:p@127.0.0.1:1/none",
    DB_PASSWORD="",
    SUPABASE_DB_REGION="",
    AZURE_PG_USER="",
    SCHEDULER_ENABLED="false",
    # Azure and Railway hosts run on UTC; reproduce that here.
    TZ="UTC",
)
if hasattr(time, "tzset"):
    time.tzset()

from apscheduler.triggers.cron import CronTrigger  # noqa: E402

from app.workers.scheduler import scheduler, setup_scheduler  # noqa: E402


def test_every_cron_job_uses_the_chicago_clock():
    setup_scheduler()
    try:
        cron_jobs = [j for j in scheduler.get_jobs() if isinstance(j.trigger, CronTrigger)]
        assert len(cron_jobs) >= 10
        for job in cron_jobs:
            assert str(job.trigger.timezone) == "America/Chicago", job.id

        # The 9 AM content run on 5 Oct 2026 (CDT, UTC-5) is 14:00 UTC, not 09:00.
        content = scheduler.get_job("daily_content").trigger
        after = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        nxt = content.get_next_fire_time(None, after).astimezone(timezone.utc)
        assert (nxt.hour, nxt.minute) == (14, 0)
    finally:
        scheduler.remove_all_jobs()


if __name__ == "__main__":
    test_every_cron_job_uses_the_chicago_clock()
    print("ok")
