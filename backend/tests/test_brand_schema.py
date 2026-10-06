"""Brand-level schema tests: real cities, no invented facts. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_brand_schema.py
"""
import json
import os
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

from app.models.brand import Brand  # noqa: E402
from app.services.schema_service import (  # noqa: E402
    build_brand_schema_set,
    build_local_business_schema,
    build_organization_schema,
    split_market,
)

LIFTECH = Brand(
    id="liftech",
    name="Liftech Elevator",
    wp_url="https://liftechelevator.com",
    phone="562-997-3639",
    markets=["Long Beach CA", "Signal Hill CA"],
)
NO_MARKETS = Brand(id="axxiom", name="Axxiom Elevator FL", wp_url="https://axxiomelevatorfl.com", phone="[BRAND_PHONE]")

INVENTED = ("numberOfEmployees", "foundingDate", "openingHours", "priceRange", "hoursAvailable", "certified")


def test_split_market():
    assert split_market("Signal Hill CA") == ("Signal Hill", "CA")
    assert split_market("Pompano Beach, FL") == ("Pompano Beach", "FL")
    assert split_market("Washington DC") == ("Washington", "DC")
    assert split_market("National") == ("National", "")
    assert split_market("") == ("", "")


def test_local_business_uses_whole_city_names():
    data = json.loads(build_local_business_schema(LIFTECH))
    assert data["address"] == {
        "@type": "PostalAddress",
        "addressCountry": "US",
        "addressLocality": "Long Beach",
        "addressRegion": "CA",
    }
    assert data["areaServed"] == [
        {"@type": "City", "name": "Long Beach, CA"},
        {"@type": "City", "name": "Signal Hill, CA"},
    ]
    assert data["telephone"] == "562-997-3639"
    assert "serviceArea" not in data


def test_no_markets_and_no_phone_means_no_guesses():
    data = json.loads(build_local_business_schema(NO_MARKETS))
    assert "addressLocality" not in data["address"]
    assert "areaServed" not in data and "telephone" not in data
    assert "National" not in json.dumps(data)
    org = json.loads(build_organization_schema(NO_MARKETS))
    assert "contactPoint" not in org and "[BRAND_PHONE]" not in json.dumps(org)


def test_no_invented_facts_anywhere_in_the_brand_set():
    for item in build_brand_schema_set(LIFTECH):
        text = item["schema_json"]
        for claim in INVENTED:
            assert claim not in text, (item["title"], claim)
        json.loads(text)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
