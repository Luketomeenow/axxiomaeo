"""Market-scope guard tests. Runs under pytest or plainly:

    cd backend && venv/bin/python tests/test_market_scope.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.prompts.content_prompts import CONTENT_TYPE_CONFIG, build_prompt  # noqa: E402
from app.utils.geography import (  # noqa: E402
    brand_states,
    market_scope_rule,
    out_of_market_states,
    query_out_of_market,
    states_in_text,
    validate_market_scope,
)

FL = ["Pompano Beach FL", "Sarasota FL"]
AZ = ["Phoenix AZ", "Tucson AZ", "Scottsdale AZ", "Mesa AZ"]
SC = ["Columbia SC"]
QUALITY = ["Baltimore MD", "Washington DC", "Philadelphia PA", "Richmond VA"]
AMERITEX = ["Houston TX", "Dallas TX", "Austin TX", "San Antonio TX", "Los Angeles CA", "San Diego CA"]


def test_brand_states():
    assert brand_states(FL) == {"FL"}
    assert brand_states(QUALITY) == {"MD", "DC", "PA", "VA"}
    assert brand_states(AMERITEX) == {"TX", "CA"}
    assert brand_states(["National"]) == set()
    assert brand_states([]) == set()
    assert brand_states(["South Carolina"]) == {"SC"}


def test_states_in_text_word_boundaries():
    c = states_in_text("Arkansas and Kansas differ; West Virginia is not Virginia.")
    assert c["AR"] == 1 and c["KS"] == 1
    assert c["WV"] == 1 and c["VA"] == 1  # the trailing bare "Virginia"
    only_wv = states_in_text("Charleston, West Virginia adopted A17.1.")
    assert only_wv["WV"] == 1 and only_wv["VA"] == 0
    # plain "Washington" is ignored (person/city ambiguity); explicit forms count
    assert states_in_text("George Washington opened it.") == {}
    assert states_in_text("Washington State requires…")["WA"] == 1
    assert states_in_text("in Washington, D.C. the DOB…")["DC"] == 1


def test_agency_aliases():
    c = states_in_text("Per Cal/OSHA and Title 8, the MCP must be certified.")
    assert c["CA"] == 2
    assert states_in_text("TDLR inspects annually")["TX"] == 1
    assert states_in_text("the NYC DOB elevator unit")["NY"] == 1


def test_abbreviations_only_in_query_mode():
    assert states_in_text("Elevator service Houston TX")["TX"] == 0
    assert states_in_text("Elevator service Houston TX", abbreviations=True)["TX"] == 1
    # bare two-letter words are never states
    assert states_in_text("Call us IN the OR", abbreviations=True) == {}


def test_query_out_of_market():
    assert query_out_of_market("Maryland AHJ requirements for elevators", "", FL) == "Maryland"
    assert query_out_of_market("California elevator code compliance", "", AZ) == "California"
    assert query_out_of_market("elevator inspection requirements Texas", "", SC) == "Texas"
    assert query_out_of_market("elevator service Baltimore, MD", "", QUALITY) is None
    assert query_out_of_market("Los Angeles elevator modernization California", "", AMERITEX) is None
    assert query_out_of_market("how often should elevators be inspected", "", FL) is None
    # national brands are never filtered
    assert query_out_of_market("Maryland elevator code", "", ["National"]) is None


def _article(body: str, n_faq: int = 3) -> str:
    faqs = "".join(f"<h2>Question {i}?</h2><p>{body}</p>" for i in range(n_faq))
    return f"<h1>Guide</h1><p>{body}</p>{faqs}"


def test_validate_fails_foreign_title():
    ok, reason, details = validate_market_scope(
        _article("Elevators need annual inspection."),
        title="Maryland AHJ Requirements for Elevators",
        target_query="elevator maintenance",
        markets=FL,
        brand_name="Axxiom Elevator Florida",
    )
    assert not ok and "Maryland" in reason and details["head"] == "Maryland"


def test_validate_fails_foreign_regulator_once():
    ok, reason, _ = validate_market_scope(
        _article("Under Cal/OSHA, the maintenance control program must be on site."),
        title="Elevator maintenance control programs",
        target_query="elevator MCP requirements",
        markets=AZ,
        brand_name="Arizona Elevator Solutions",
    )
    assert not ok and "California regulator" in reason


def test_validate_allows_passing_mention_but_not_a_section():
    # _article repeats the body once per FAQ plus the intro → 2 mentions = the limit
    passing = _article("Florida requires annual inspection; Texas differs slightly.", n_faq=1)
    ok, _, details = validate_market_scope(
        passing, title="Florida elevator inspections", target_query="elevator inspection florida",
        markets=FL, brand_name="Axxiom Elevator Florida",
    )
    assert ok and details["foreign"] == {"TX": 2}

    heavy = _article("In Texas, inspections happen yearly; Texas owners file with the state of Texas.", n_faq=2)
    ok, reason, _ = validate_market_scope(
        heavy, title="Elevator inspections", target_query="elevator inspections",
        markets=SC, brand_name="Carolina Elevator Service",
    )
    assert not ok and "Texas" in reason


def test_validate_skips_national():
    ok, _, details = validate_market_scope(
        _article("Maryland Maryland Maryland Maryland."),
        title="Maryland", target_query="maryland", markets=["National"], brand_name="Axxiom",
    )
    assert ok and details["checked"] is False


def test_out_of_market_ignores_home_states():
    c = out_of_market_states("Maryland, Virginia, and Pennsylvania rules; also Texas.", QUALITY)
    assert c == {"TX": 1}


def test_prompt_renders_for_every_content_type():
    for ct in CONTENT_TYPE_CONFIG:
        prompt = build_prompt(ct, "Axxiom Elevator Florida", "elevator inspection frequency", FL,
                              title="T", city="Sarasota", state="FL")
        assert "MARKET SCOPE" in prompt and "Florida" in prompt and "{market_scope}" not in prompt
        assert "no citation beats a guessed one" in prompt
    national = build_prompt("faq_hub", "Axxiom", "q", ["National"])
    assert "service area is national" in national


def test_market_scope_rule_lists_all_home_states():
    rule = market_scope_rule("Quality Elevator Company", QUALITY)
    for name in ("District of Columbia", "Maryland", "Pennsylvania", "Virginia"):
        assert name in rule


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if failures else 0)
