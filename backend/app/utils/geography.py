"""Market-scope (jurisdiction) guard.

The generator once published a 3,400-word Maryland AHJ article on the Florida
brand and a Cal/OSHA compliance piece on the Arizona brand (found in the
2026-09 content cleanup). Nothing in the pipeline knew which states a brand
operates in beyond a positive "markets served" line in the prompt, and the
topic sources (Search Console, observed customer questions, citation gaps)
happily supplied out-of-market queries — cloned content on a site makes
Google show that other state's queries for it, and the generator wrote them.

This module gives every stage one shared answer to "is this jurisdiction
ours?":

* topic discovery / manual queue endpoints drop out-of-market *queries*
* the prompt gets an explicit MARKET SCOPE rule
* post-generation validation fails a draft that leans on another state's
  codes, agencies, or requirements (→ correction attempt, then needs_review)

Detection is deliberately conservative to avoid false positives on prose:
full state names (word-bounded, "West Virginia" before "Virginia", plain
"Washington" ignored unless clearly the state or DC) plus a short list of
state-specific regulators (Cal/OSHA, TDLR, NYC DOB). Two-letter postal
abbreviations are only trusted in query/title mode and only in the
"City ST" / "City, ST" shape — "IN", "OR", "ME" and friends are real words.
"""

from __future__ import annotations

import re
from collections import Counter

US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}

# State-specific regulators / programs that identify a jurisdiction even when
# the state name is absent. Any hit is a code-citation for that state.
STATE_AGENCY_ALIASES: dict[str, str] = {
    r"cal\s*/\s*osha": "CA",
    r"cal-?osha": "CA",
    r"\btitle\s+8\b": "CA",           # California Code of Regulations, Title 8
    r"\btdlr\b": "TX",                # Texas Dept. of Licensing and Regulation
    r"\bnyc\s+dob\b": "NY",
    r"\bnyc\s+department\s+of\s+buildings\b": "NY",
    r"\bdob\s+nyc\b": "NY",
}

# States whose bare name is a common non-state word or too ambiguous to trust.
_AMBIGUOUS_NAMES = {"WA", "DC"}

_NAME_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _abbr, _name in US_STATES.items():
    if _abbr in _AMBIGUOUS_NAMES:
        continue
    if _abbr == "VA":
        pat = re.compile(r"(?<!west\s)\bvirginia\b", re.IGNORECASE)
    else:
        pat = re.compile(r"\b" + re.escape(_name.lower()) + r"\b", re.IGNORECASE)
    _NAME_PATTERNS.append((_abbr, pat))

# Explicit forms for the ambiguous pair.
_WA_STATE = re.compile(r"\bwashington\s+state\b|\bstate\s+of\s+washington\b", re.IGNORECASE)
_DC = re.compile(r"\bwashington,?\s+d\.?\s?c\.?\b|\bdistrict\s+of\s+columbia\b", re.IGNORECASE)

_AGENCY_PATTERNS = [(abbr, re.compile(p, re.IGNORECASE)) for p, abbr in STATE_AGENCY_ALIASES.items()]

# "Houston TX", "Baltimore, MD", "New York, NY" — postal abbreviation right
# after a capitalized place word. Only used in query/title mode.
_CITY_ST = re.compile(r"\b[A-Z][a-zA-Z.]+,?\s+([A-Z]{2})\b")


def state_name(abbr: str) -> str:
    return US_STATES.get(abbr, abbr)


def brand_states(markets: list[str] | None) -> set[str]:
    """Postal abbreviations of the states a brand's markets fall in.

    'Houston TX' → TX; 'Washington DC' → DC; 'Columbia SC' → SC;
    'National' / unparseable → contributes nothing.
    """
    states: set[str] = set()
    for market in markets or []:
        m = (market or "").strip()
        if not m or m.lower() == "national":
            continue
        parts = m.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].upper() in US_STATES:
            states.add(parts[1].upper())
            continue
        # Fall back to a full state name inside the market string.
        found = states_in_text(m, abbreviations=True)
        states.update(found.keys())
    return states


def is_national(markets: list[str] | None) -> bool:
    """No resolvable state → the guard has nothing to enforce."""
    return not brand_states(markets)


def states_in_text(text: str, *, abbreviations: bool = False) -> Counter[str]:
    """Count jurisdiction mentions per state (postal abbr → count)."""
    counts: Counter[str] = Counter()
    if not text:
        return counts
    for abbr, pat in _NAME_PATTERNS:
        n = len(pat.findall(text))
        if n:
            counts[abbr] += n
    n = len(_WA_STATE.findall(text))
    if n:
        counts["WA"] += n
    n = len(_DC.findall(text))
    if n:
        counts["DC"] += n
    for abbr, pat in _AGENCY_PATTERNS:
        n = len(pat.findall(text))
        if n:
            counts[abbr] += n
    if abbreviations:
        for abbr in _CITY_ST.findall(text):
            if abbr in US_STATES:
                counts[abbr] += 1
    return counts


def agency_mentions(text: str) -> Counter[str]:
    """Only the regulator aliases (Cal/OSHA, TDLR, …) — these are code
    citations by definition, so one is enough to fail a draft."""
    counts: Counter[str] = Counter()
    for abbr, pat in _AGENCY_PATTERNS:
        n = len(pat.findall(text or ""))
        if n:
            counts[abbr] += n
    return counts


def out_of_market_states(
    text: str, markets: list[str] | None, *, abbreviations: bool = False
) -> Counter[str]:
    home = brand_states(markets)
    if not home:
        return Counter()
    found = states_in_text(text, abbreviations=abbreviations)
    return Counter({abbr: n for abbr, n in found.items() if abbr not in home})


def query_out_of_market(query: str, title: str, markets: list[str] | None) -> str | None:
    """Name of the first out-of-market state a topic names, else None.

    Used to drop discovery candidates and reject manual queue adds — a query
    that names another state can only produce an article about that state.
    """
    foreign = out_of_market_states(f"{query or ''} {title or ''}", markets, abbreviations=True)
    if not foreign:
        return None
    abbr = sorted(foreign.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return state_name(abbr)


def market_scope_rule(brand_name: str, markets: list[str] | None) -> str:
    """Prompt paragraph: the positive scope plus the no-guessing rule for codes."""
    states = sorted(state_name(s) for s in brand_states(markets))
    if states:
        scope = ", ".join(states)
        return (
            f"- MARKET SCOPE (hard rule): {brand_name} operates ONLY in {scope}. Every code, statute, "
            f"agency, licensing rule, inspection interval, and AHJ you name must be federal (ASME A17.1 / "
            f"A17.3, ADA, OSHA) or belong to {scope}. NEVER write about, cite, or compare another state's "
            f"requirements (e.g. no Cal/OSHA or Title 8 unless California is listed above; no Maryland, "
            f"Texas, or New York rules unless listed). If the target query names another jurisdiction, "
            f"answer the underlying question for {scope} and do not mention the other state.\n"
            f"- CODE CITATIONS: name only codes and requirements you are certain apply in {scope}. If you "
            f"cannot attribute a section number, statute, or agency rule to one of the approved URLs above, "
            f"OMIT it — a wrong code reference on an elevator page is a liability, so no citation beats a "
            f"guessed one."
        )
    return (
        f"- MARKET SCOPE: {brand_name}'s service area is national. Do not present any single state's "
        f"code, agency, or statute as if it applied everywhere; keep requirements federal (ASME A17.1 / "
        f"A17.3, ADA, OSHA) unless the target query itself asks about a specific state.\n"
        f"- CODE CITATIONS: if you cannot attribute a section number, statute, or agency rule to one of "
        f"the approved URLs above, OMIT it — no citation beats a guessed one."
    )


def validate_market_scope(
    html: str,
    *,
    title: str,
    target_query: str,
    markets: list[str] | None,
    brand_name: str,
    max_body_mentions: int = 2,
) -> tuple[bool, str, dict]:
    """Fail a draft that is about — or cites the regulators of — another state.

    Rules (any one fails):
      * the title or target query names an out-of-market state
      * any out-of-market regulator alias (Cal/OSHA, TDLR, …) appears at all
      * an out-of-market state is named more than ``max_body_mentions`` times
        (one passing mention in a national comparison is fine; a section on
        it is not)

    Returns (ok, reason, details) — details feed validation_result so the
    reviewer can see what tripped.
    """
    from app.utils.helpers import strip_html

    home = brand_states(markets)
    if not home:
        return True, "", {"checked": False, "reason": "national/unknown markets"}

    home_names = ", ".join(sorted(state_name(s) for s in home))
    head_hit = query_out_of_market(target_query, title, markets)
    if head_hit:
        return (
            False,
            f"Out-of-market topic: the title/query is about {head_hit}, but {brand_name} serves only "
            f"{home_names}. Rewrite for {home_names} and do not mention {head_hit}.",
            {"checked": True, "head": head_hit},
        )

    text = strip_html(html or "")
    body = out_of_market_states(text, markets)
    agencies = Counter({a: n for a, n in agency_mentions(text).items() if a not in home})
    if agencies:
        abbr, n = agencies.most_common(1)[0]
        return (
            False,
            f"Out-of-market code citation: the article cites a {state_name(abbr)} regulator "
            f"({n}×), but {brand_name} serves only {home_names}. Remove every {state_name(abbr)}-specific "
            f"agency, statute, and requirement; cite only federal codes (ASME A17.1, ADA, OSHA) or "
            f"{home_names} rules you can attribute to the approved URLs, otherwise omit the citation.",
            {"checked": True, "agencies": dict(agencies), "foreign": dict(body)},
        )

    heavy = {abbr: n for abbr, n in body.items() if n > max_body_mentions}
    if heavy:
        abbr, n = sorted(heavy.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return (
            False,
            f"Out-of-market jurisdiction: the article references {state_name(abbr)} {n}× but {brand_name} "
            f"serves only {home_names}. Remove all {state_name(abbr)}-specific codes, agencies, and "
            f"requirements and answer for {home_names} instead.",
            {"checked": True, "foreign": dict(body)},
        )

    return True, "", {"checked": True, "foreign": dict(body)}
