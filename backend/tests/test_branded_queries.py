"""Branded/navigational queries never become topics. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_branded_queries.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(DATABASE_URL="postgresql://u:p@127.0.0.1:1/none", DB_PASSWORD="", SUPABASE_DB_REGION="", AZURE_PG_USER="")

from app.services.topic_discovery_service import _one_edit_apart, brand_search_terms, is_branded_query  # noqa: E402


def test_one_letter_misspellings_of_the_brand_are_branded():
    axxiom = brand_search_terms("Axxiom Elevator Florida", "https://axxiomelevatorfl.com")
    assert is_branded_query("axiom elevator", axxiom)  # became a post titled "Axiom Elevator"
    assert is_branded_query("axxiom elevator reviews", axxiom)
    assert not is_branded_query("elevator inspection checklist florida", axxiom)
    liftech = brand_search_terms("Liftech Elevator", "https://liftechelevator.com")
    assert is_branded_query("liftec elevator long beach", liftech)
    assert not is_branded_query("elevator lift capacity", liftech)


def test_one_edit_apart():
    assert _one_edit_apart("axiom", "axxiom")
    assert _one_edit_apart("liftec", "liftech")
    assert _one_edit_apart("ameritax", "ameritex")
    assert not _one_edit_apart("axxiom", "axxiom")
    assert not _one_edit_apart("amerika", "ameritex")


if __name__ == "__main__":
    test_one_letter_misspellings_of_the_brand_are_branded()
    test_one_edit_apart()
    print("ok")
