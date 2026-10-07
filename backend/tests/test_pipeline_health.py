"""Pipeline health helpers. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_pipeline_health.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(
    DATABASE_URL="postgresql://u:p@127.0.0.1:1/none",
    DB_PASSWORD="",
    SUPABASE_DB_REGION="",
    AZURE_PG_USER="",
    SCHEDULER_ENABLED="false",
)

from app.services.pipeline_health_service import age_days  # noqa: E402

NOW = datetime(2026, 10, 7, 15, 30)


def test_age_days_handles_naive_and_aware_timestamps():
    assert age_days(NOW - timedelta(days=3, hours=1), NOW) == 3
    # Azure returns timestamptz columns as aware datetimes; this used to raise
    # "can't subtract offset-naive and offset-aware datetimes".
    aware = datetime(2026, 10, 4, 9, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert age_days(aware, NOW) == 3
    assert age_days(NOW + timedelta(hours=2), NOW) == 0
    assert age_days(None, NOW) is None


if __name__ == "__main__":
    test_age_days_handles_naive_and_aware_timestamps()
    print("ok")
