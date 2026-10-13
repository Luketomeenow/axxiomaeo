"""Startup seed never overwrites Brand Settings. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_seed.py
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(
    DATABASE_URL="postgresql://u:p@127.0.0.1:1/none",
    DB_PASSWORD="",
    SUPABASE_DB_REGION="",
    AZURE_PG_USER="",
    SCHEDULER_ENABLED="false",
)

from app.utils.seed import phone_update  # noqa: E402
from app.utils.seed_data import BRANDS  # noqa: E402


def test_seed_fills_empty_and_replaces_only_known_wrong_numbers():
    retired = ["866-679-4313"]
    assert phone_update(None, "844-646-9660", retired) == "844-646-9660"
    assert phone_update("", "844-646-9660", retired) == "844-646-9660"
    # The pool number an earlier seed wrote, in any format, is corrected.
    assert phone_update("(866) 679-4313", "844-646-9660", retired) == "844-646-9660"
    # A phone someone set in Brand Settings is never touched.
    assert phone_update("844-646-9661", "844-646-9660", retired) is None
    assert phone_update("844.646.9660", "844-646-9660", retired) is None
    assert phone_update("844-646-9660", None, retired) is None


def test_seed_phones_are_main_lines_not_retired_pool_numbers():
    digits = lambda v: re.sub(r"\D", "", v or "")  # noqa: E731
    for brand in BRANDS:
        assert brand.get("phone"), brand["id"]
        retired = {digits(p) for p in brand.get("retired_phones", [])}
        assert digits(brand["phone"]) not in retired, brand["id"]
        assert all(len(r) == 10 for r in retired), brand["id"]


if __name__ == "__main__":
    test_seed_fills_empty_and_replaces_only_known_wrong_numbers()
    test_seed_phones_are_main_lines_not_retired_pool_numbers()
    print("ok")
