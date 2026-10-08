"""Customer questions from call summaries: privacy scrub, grounding, parsing.
No database, no network. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_call_questions.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(
    DATABASE_URL="postgresql://u:p@127.0.0.1:1/none",
    DB_PASSWORD="",
    SUPABASE_DB_REGION="",
    AZURE_PG_USER="",
    SCHEDULER_ENABLED="false",
)

from app.services.call_questions_service import (  # noqa: E402
    CallRow,
    brand_for_company,
    clean_question,
    company_mapping,
    grounded,
    market_words,
    name_tokens,
    parse_extraction,
    scrub_pii,
)

PHOENIX = ["Phoenix AZ", "Tucson AZ", "Scottsdale AZ", "Mesa AZ"]

SUMMARY = (
    "John Ramirez from Desert Sky Apartments called from 480-555-0142 (john@desertsky.com) about "
    "their building at 4120 East Camelback Road. He asked how much it would cost to modernize the "
    "two hydraulic elevators in their 4 story apartment building in Phoenix and whether the "
    "city inspection is due this year. Account 8834512. Agent offered a site visit."
)


def test_scrub_removes_personal_details_but_keeps_the_market_city():
    keep = market_words(PHOENIX)
    out = scrub_pii(SUMMARY, ["JOHN RAMIREZ"], keep)
    for leaked in ("John", "Ramirez", "480-555-0142", "john@desertsky.com", "4120 East Camelback Road", "8834512"):
        assert leaked not in out, leaked
    assert "[phone]" in out and "[email]" in out and "[address]" in out and "[number]" in out
    assert "Phoenix" in out and "hydraulic elevators" in out
    # Caller ID for an unknown number is often just the city: never scrub a market city.
    assert name_tokens(["PHOENIX AZ"], keep) == set()
    assert name_tokens(["MARRIOTT HOTEL"], keep) == {"marriott"}


def test_company_names_map_to_brands():
    mapping = company_mapping()
    assert brand_for_company("AmeriTex Elevator", mapping) == "ameritex"
    assert brand_for_company("Arizona Elevator Solutions", mapping) == "arizona_es"
    assert brand_for_company("Axxiom Florida", mapping) == "axxiom"
    assert brand_for_company("Carolina Elevator", mapping) == "carolina"
    assert brand_for_company("Motion Elevator", mapping) is None
    assert brand_for_company("Axxiom Elevator Nashville", mapping) is None
    assert brand_for_company("Motion Elevator", company_mapping('{"Motion Elevator": "axxiom"}')) == "axxiom"
    assert brand_for_company("Liftech Elevator", company_mapping("not json")) == "liftech"


def test_grounding_needs_a_real_phrase_from_the_summary():
    out = scrub_pii(SUMMARY, ["JOHN RAMIREZ"], market_words(PHOENIX))
    assert grounded("cost to modernize the two hydraulic elevators", out)
    assert grounded("Cost to modernize, the two hydraulic elevators!", out)  # punctuation is ignored
    assert not grounded("modernize", out)  # too short to show where it came from
    assert not grounded("asked about escalator replacement pricing", out)


def test_questions_that_leak_details_are_rejected():
    names = {"ramirez", "john"}
    assert clean_question("how much does it cost to modernize a hydraulic elevator", names) == (
        "How much does it cost to modernize a hydraulic elevator?"
    )
    assert clean_question("How much will John Ramirez pay for a modernization?", names) is None
    assert clean_question("Can you call me back at 480-555-0142 about a quote?", names) is None
    assert clean_question("Is the elevator at 4120 East Camelback Road due for inspection?", names) is None
    assert clean_question("What does [name] need for the inspection?", names) is None
    assert clean_question("Cost?", names) is None


def test_parse_keeps_only_grounded_clean_questions():
    keep = market_words(PHOENIX)
    call = CallRow(
        call_id="CAL123",
        brand_id="arizona_es",
        brand_name="Arizona Elevator Solutions",
        summary=scrub_pii(SUMMARY, ["JOHN RAMIREZ"], keep),
        names=name_tokens(["JOHN RAMIREZ"], keep),
        started_at=datetime(2026, 10, 7, 15, 0),
        source="Google Business Profile",
        first_time=True,
    )
    quiet = CallRow("CAL456", "arizona_es", "Arizona Elevator Solutions", "Caller confirmed tomorrow's appointment.",
                    set(), None, "Direct", False)
    raw = {
        "calls": [
            {"id": "c0", "questions": [
                {"question": "How much does it cost to modernize two hydraulic elevators in a 4-story apartment building?",
                 "intent": "cost", "basis": "cost to modernize the two hydraulic elevators"},
                {"question": "How often is a city elevator inspection required in Phoenix?",
                 "intent": "inspection", "basis": "city inspection is due this year"},
                {"question": "What does John Ramirez owe?", "intent": "other", "basis": "Account [number]"},
                {"question": "Third question is ignored?", "intent": "other", "basis": "Agent offered a site visit"},
            ]},
            {"id": "c1", "questions": []},
            {"id": "c9", "questions": [{"question": "Unknown call id question here?", "intent": "x", "basis": "x y z"}]},
        ]
    }
    found, per_call = parse_extraction(raw, {"c0": call, "c1": quiet})
    assert [q["question"] for q in found] == [
        "How much does it cost to modernize two hydraulic elevators in a 4-story apartment building?",
        "How often is a city elevator inspection required in Phoenix?",
    ]
    assert per_call == {"CAL123": 2, "CAL456": 0}  # the quiet call is still marked scanned
    assert [q["index"] for q in found] == [1, 2]
    assert found[0]["intent"] == "cost" and found[0]["call_source"] == "Google Business Profile"


def test_scheduler_runs_the_scan_before_topic_discovery():
    from app.workers.scheduler import scheduler, setup_scheduler

    setup_scheduler()
    try:
        scan = scheduler.get_job("call_questions").trigger
        discovery = scheduler.get_job("topic_discovery").trigger
        assert str(scan.timezone) == "America/Chicago"
        now = datetime(2026, 10, 8, 6, 0, tzinfo=scan.timezone)
        assert scan.get_next_fire_time(None, now) < discovery.get_next_fire_time(None, now)
    finally:
        scheduler.remove_all_jobs()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
