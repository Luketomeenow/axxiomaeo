"""State fact sheet tests. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_state_facts.py

The fact sheet is only useful if every line in it is traceable, so the first
tests enforce the contract (official URL + verbatim quote on every fact) and
coverage (every state a brand serves has an entry). The rest pin the TDI fix
with sentences copied from live AmeriTex articles (2026-09-25 scan).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.prompts.content_prompts import (  # noqa: E402
    CORRECTION_PROMPT,
    REFRESH_CONTENT_PROMPT,
    build_prompt,
    shared_prompt_fields,
)
from app.utils.geography import brand_states  # noqa: E402
from app.utils.seed_data import BRANDS  # noqa: E402
from app.utils.state_facts import (  # noqa: E402
    authority_links,
    facts_for,
    load_state_facts,
    state_facts_block,
    validate_state_facts,
)

AMERITEX = ["Houston TX", "Dallas TX", "Austin TX", "San Antonio TX", "Los Angeles CA", "San Diego CA"]
CAROLINA = ["Columbia SC"]

# Verbatim from live ameritexelevator.com posts, 2026-09-25.
LIVE_TDI_SENTENCES = [
    "Dallas follows the International Building Code and the Texas Department of Insurance (TDI) "
    "Elevator Safety Program rules.",
    "Texas requires current elevator inspection certificates to be posted inside every cab; a "
    "TDI-licensed inspector verifies compliance with ASME A17.1 standards during each mandatory "
    "periodic inspection.",
    "Annual Operating Certificates: Every elevator must hold a valid certificate of operation issued by TDI.",
    "To evaluate elevator service companies in Dallas or Houston before signing a contract, verify "
    "state licensing through the Texas Department of Insurance, confirm compliance with ASME A17.1.",
]
LIVE_WRONG_CITATION = (
    "In Texas, elevator safety is enforced under Texas Administrative Code Title 28, Part 2, Chapter 74."
)


def _html(*paragraphs: str) -> str:
    return "<h1>Elevator inspections</h1>" + "".join(f"<p>{p}</p>" for p in paragraphs)


def test_every_fact_is_sourced():
    data = load_state_facts()
    assert data.get("verified_on"), "fact sheet needs a verified_on date"
    for st, entry in data["states"].items():
        auth = entry.get("authority")
        assert auth and auth.get("name") and auth.get("url", "").startswith("https://"), st
        assert auth.get("source_quote"), f"{st} authority has no verbatim quote"
        for key in ("statute", "rules", "code_adoption"):
            ref = entry.get(key)
            if ref:
                assert ref.get("url", "").startswith("http"), f"{st}.{key} has no source URL"
                assert ref.get("source_quote"), f"{st}.{key} has no verbatim quote"
        for req in entry.get("requirements", []):
            assert req.get("claim") and req.get("url", "").startswith("http"), (st, req.get("id"))
            assert req.get("source_quote"), f"{st} requirement {req.get('id')} has no verbatim quote"
        for group in ("not_the_regulator", "not_required", "local_authorities"):
            for item in entry.get(group, []):
                assert item.get("url", "").startswith("http"), f"{st}.{group} item has no source URL"


def test_patterns_compile():
    for st, entry in load_state_facts()["states"].items():
        for group in ("wrong_citations", "not_required"):
            for item in entry.get(group, []):
                if item.get("pattern"):
                    re.compile(item["pattern"], re.IGNORECASE)
        for req in entry.get("requirements", []):
            for key in ("all", "any", "none"):
                for p in (req.get("match") or {}).get(key, []):
                    re.compile(p, re.IGNORECASE)


def test_every_brand_state_is_covered():
    covered = set(load_state_facts()["states"])
    for brand in BRANDS:
        missing = brand_states(brand["markets"]) - covered
        assert not missing, f"{brand['id']} serves {missing} with no verified fact entry"


def test_sheet_never_contradicts_itself():
    # Every correct name and verified claim must pass the validator. Guards the
    # collision where a never-name alias is a prefix of a real agency name
    # ("South Carolina Department of Labor" vs "... Labor, Licensing and Regulation").
    parts = []
    for entry in load_state_facts()["states"].values():
        auth = entry["authority"]
        parts += [auth["name"], *auth.get("aliases", [])]
        parts += [r["claim"] for r in entry.get("requirements", [])]
        parts += [loc["name"] for loc in entry.get("local_authorities", [])]
    for markets in (AMERITEX, CAROLINA, ["Baltimore MD", "Washington DC", "Philadelphia PA", "Richmond VA"]):
        ok, reason, _ = validate_state_facts("<p>" + "</p><p>".join(parts) + "</p>", markets)
        assert ok, reason


def test_texas_regulator_is_tdlr_not_tdi():
    tx = facts_for(["TX"])[0]
    assert tx["authority"]["short"] == "TDLR"
    assert "Licensing and Regulation" in tx["authority"]["name"]
    wrong = {n for w in tx["not_the_regulator"] for n in [w["name"], *w.get("aliases", [])]}
    assert "Texas Department of Insurance" in wrong and "TDI" in wrong


def test_prompt_block_names_the_real_regulator_and_forbids_tdi():
    block = state_facts_block("AmeriTex Elevator", AMERITEX)
    assert "Texas Department of Licensing and Regulation (TDLR)" in block
    assert "NEVER name as the elevator regulator" in block and "Texas Department of Insurance" in block
    assert "CALIFORNIA" in block and "TEXAS" in block
    # Only the brand's own states are rendered.
    assert "SOUTH CAROLINA" not in block


def test_no_facts_block_forbids_state_claims():
    block = state_facts_block("Somebody", ["National"])
    assert "none are verified" in block and "Do NOT name any" in block


def test_authority_links_are_official_pages():
    links = dict(authority_links(AMERITEX))
    assert any("tdlr.texas.gov" in url for url in links.values()), links


def test_build_prompt_carries_facts_and_links_for_every_type():
    for content_type in ("faq_hub", "local_page", "vertical_page", "comparison", "data_stats"):
        prompt = build_prompt(content_type, "AmeriTex Elevator", "elevator inspection Dallas", AMERITEX)
        assert "STATE REGULATORY FACTS" in prompt, content_type
        assert "tdlr.texas.gov" in prompt, content_type
        for placeholder in ("{state_facts}", "{authority_links}", "{market_scope}"):
            assert placeholder not in prompt, (content_type, placeholder)


def test_correction_and_refresh_prompts_carry_facts():
    shared = shared_prompt_fields("AmeriTex Elevator", AMERITEX)
    fix = CORRECTION_PROMPT.format(failure_reason="x", target_query="q", brand_name="AmeriTex", **shared)
    assert "Texas Department of Licensing and Regulation" in fix
    refresh = REFRESH_CONTENT_PROMPT.format(
        brand_name="AmeriTex", target_query="q", content_type="faq_hub", **shared
    )
    assert "Texas Department of Insurance (TDI)" in refresh and "TDLR" in refresh


def test_live_tdi_sentences_fail_validation():
    for sentence in LIVE_TDI_SENTENCES:
        ok, reason, details = validate_state_facts(_html(sentence), AMERITEX)
        assert not ok, sentence
        assert "Texas Department of Licensing and Regulation" in reason
        assert details["wrong_regulators"]


def test_tdi_fails_on_any_brand():
    ok, _, _ = validate_state_facts(_html(LIVE_TDI_SENTENCES[0]), CAROLINA)
    assert not ok


def test_wrong_title_28_citation_fails():
    ok, reason, _ = validate_state_facts(_html(LIVE_WRONG_CITATION), AMERITEX)
    assert not ok and "16" in reason, reason


def test_correct_texas_copy_passes():
    ok, reason, _ = validate_state_facts(
        _html(
            "In Texas, elevators are regulated by the Texas Department of Licensing and Regulation (TDLR).",
            "AmeriTex schedules inspections and keeps the paperwork ready for the inspector.",
        ),
        AMERITEX,
    )
    assert ok, reason


def test_unrelated_words_do_not_trip():
    # "TDI" must be a whole word; these contain the letters but not the acronym.
    ok, reason, _ = validate_state_facts(_html("The tech outdid the schedule; stdin logs were clean."), AMERITEX)
    assert ok, reason


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
