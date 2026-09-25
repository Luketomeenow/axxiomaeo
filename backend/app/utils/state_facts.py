"""Verified per-state elevator regulatory facts.

Why this exists: the prompts told the model to cite "state regulations where
relevant" and "local elevator code specifics" without ever saying who the
regulator is, so it guessed. For Texas it guessed the Texas Department of
Insurance (TDI) — 99 of 149 live AmeriTex posts named TDI as the elevator
regulator (956 mentions, found 2026-09-25), often alongside an invented
"Texas Administrative Code Title 28" citation. Texas elevators are regulated
by TDLR under 16 TAC Chapter 74.

The fix replaces guessing with a fact sheet (``app/data/state_facts.json``):
every entry carries the official URL it came from and a verbatim quote, and
anything that could not be verified from an official page is left out. The
same JSON is vendored into the marketing hub, where the social-post claims
lint checks captions against it.

Three consumers here:

* ``state_facts_block`` — prompt text: the ONLY state-level facts the model
  may state, for the brand's own states, plus the names it must never use.
* ``authority_links`` — the official regulator pages, added to the prompt's
  approved external-link list so articles can cite the real agency.
* ``validate_state_facts`` — post-generation gate: a draft that names a known
  wrong regulator (any state), uses a known wrong rule citation, or states a
  requirement the fact sheet records as NOT in force fails → correction pass.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from app.utils.geography import brand_states, state_name

FACTS_PATH = Path(__file__).resolve().parent.parent / "data" / "state_facts.json"


@lru_cache
def load_state_facts() -> dict:
    with FACTS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _states() -> dict[str, dict]:
    return load_state_facts().get("states", {})


def facts_for(states: Iterable[str]) -> list[dict]:
    """Fact entries for the given postal codes, in a stable order, skipping
    states the sheet has no verified entry for."""
    table = _states()
    return [dict(table[s], state=s) for s in sorted(set(states)) if s in table]


def _alias_pattern(alias: str) -> re.Pattern[str]:
    # Word-bounded, whitespace-tolerant ("Texas  Department of\nInsurance").
    words = [re.escape(w) for w in alias.split()]
    return re.compile(r"\b" + r"\s+".join(words) + r"\b", re.IGNORECASE)


@lru_cache
def _wrong_regulator_patterns() -> list[tuple[str, str, re.Pattern[str], dict]]:
    """(state, alias, pattern, entry) for every not_the_regulator alias in the
    sheet. Checked against ALL states: TDI is not an elevator regulator on a
    Carolina page either."""
    out = []
    for st, entry in _states().items():
        for wrong in entry.get("not_the_regulator", []) or []:
            names = {wrong.get("name", "")} | set(wrong.get("aliases") or [])
            for alias in sorted(n for n in names if n):
                out.append((st, alias, _alias_pattern(alias), wrong))
    return out


@lru_cache
def _wrong_citation_patterns() -> list[tuple[str, re.Pattern[str], dict]]:
    out = []
    for st, entry in _states().items():
        for wc in entry.get("wrong_citations", []) or []:
            out.append((st, re.compile(wc["pattern"], re.IGNORECASE), wc))
    return out


_NEGATION = re.compile(
    r"\b(not|no|never|isn'?t|aren'?t|doesn'?t|don'?t|hasn'?t|haven'?t|without)\b", re.IGNORECASE
)


@lru_cache
def _not_required_patterns() -> list[tuple[str, re.Pattern[str], dict]]:
    out = []
    for st, entry in _states().items():
        for nr in entry.get("not_required", []) or []:
            if nr.get("pattern"):
                out.append((st, re.compile(nr["pattern"], re.IGNORECASE), nr))
    return out


def authority_links(markets: list[str] | None) -> list[tuple[str, str]]:
    """(label, url) for each of the brand's states' official regulator page."""
    links = []
    for entry in facts_for(brand_states(markets)):
        auth = entry.get("authority") or {}
        if auth.get("url"):
            label = auth.get("short") or auth.get("name") or entry["name"]
            links.append((f"{entry['name']} elevator regulator ({label})", auth["url"]))
    return links


def authority_link_lines(markets: list[str] | None) -> str:
    """Extra lines for the prompt's EXTERNAL LINKS list (empty if none)."""
    return "".join(f"\n    {label}: {url}" for label, url in authority_links(markets))


def _render_entry(entry: dict) -> str:
    name = entry["name"].upper()
    lines = [f"  {name}"]
    auth = entry.get("authority") or {}
    if auth.get("name"):
        short = auth.get("short")
        who = auth["name"] + (f" ({short})" if short and short not in auth["name"] else "")
        prog = f", {auth['program']}" if auth.get("program") else ""
        lines.append(f"    • Elevator regulator: {who}{prog}. Official page: {auth.get('url', '')}")
    for key, label in (("statute", "Statute"), ("rules", "Rules")):
        ref = entry.get(key) or {}
        if ref.get("citation"):
            lines.append(f"    • {label}: {ref['citation']}")
    code = entry.get("code_adoption") or {}
    if code.get("edition"):
        eff = f", effective {code['effective']}" if code.get("effective") else ""
        exc = ""
        if code.get("exceptions"):
            exc = " Exceptions: " + "; ".join(code["exceptions"]) + "."
        lines.append(f"    • Adopted code: {code.get('standard', 'ASME A17.1')}, {code['edition']}{eff}.{exc}")
    else:
        lines.append(
            "    • Adopted ASME A17.1 edition: NOT verified — do not name an edition year for "
            f"{entry['name']}."
        )
    for req in entry.get("requirements", []) or []:
        lines.append(f"    • {req['claim']}")
    for loc in entry.get("local_authorities", []) or []:
        lines.append(f"    • Local authority: {loc['name']} — {loc.get('scope', '')}".rstrip(" —"))
    for wrong in entry.get("not_the_regulator", []) or []:
        aliases = ", ".join(sorted({wrong.get("name", "")} | set(wrong.get("aliases") or []) - {""}))
        lines.append(f"    • NEVER name as the elevator regulator: {aliases}. {wrong.get('why', '')}".rstrip())
    for wc in entry.get("wrong_citations", []) or []:
        lines.append(f"    • NEVER cite {wc['wrong']}. The correct citation is {wc['correct']}.")
    for nr in entry.get("not_required", []) or []:
        lines.append(f"    • NOT a requirement in {entry['name']}: {nr['claim']} {nr.get('why', '')}".rstrip())
    for caution in entry.get("cautions", []) or []:
        lines.append(f"    • CAUTION: {caution}")
    return "\n".join(lines)


def state_facts_block(brand_name: str, markets: list[str] | None) -> str:
    """Prompt paragraph: the verified facts for the brand's states — and the
    instruction that nothing else at state level may be stated."""
    home = brand_states(markets)
    entries = facts_for(home)
    missing = sorted(state_name(s) for s in home - {e["state"] for e in entries})
    version = load_state_facts().get("verified_on", "")

    if not entries:
        return (
            "- STATE REGULATORY FACTS: none are verified for this brand's service area. Do NOT name any "
            "state or local agency, statute, rule number, permit type, inspection interval, or adopted "
            "code edition. Keep requirements federal (ASME A17.1 by name only, ADA, OSHA) and describe what "
            f"{brand_name} checks or recommends instead."
        )

    header = (
        f"- STATE REGULATORY FACTS (hard rule — verified from official state sources, {version}). These are "
        f"the ONLY state-level regulatory facts you may state for {brand_name}. Name agencies exactly as "
        "written here. If a requirement, deadline, fee, edition, or agency is not listed below, do not "
        f"state it — describe what {brand_name} checks or recommends instead. A wrong regulator or "
        "citation on an elevator page is a liability; no claim beats a guessed one."
    )
    body = "\n".join(_render_entry(e) for e in entries)
    tail = ""
    if missing:
        tail = (
            f"\n  No verified facts for {', '.join(missing)}: name no agency, statute, rule, or "
            "requirement for it."
        )
    return f"{header}\n{body}{tail}"


def validate_state_facts(html: str, markets: list[str] | None) -> tuple[bool, str, dict]:
    """Fail a draft that contradicts the fact sheet.

    Any one fails:
      * a known wrong regulator is named (checked for every state — TDI is not
        an elevator regulator anywhere)
      * a known wrong rule citation appears (e.g. "Title 28 … Chapter 74")
      * a requirement the sheet records as NOT in force in one of the brand's
        states is stated

    Returns (ok, reason, details); details feed ``validation_result`` so the
    reviewer sees exactly what tripped.
    """
    from app.utils.helpers import strip_html

    text = strip_html(html or "")
    home = brand_states(markets)
    details: dict = {"checked": True}

    wrong_regs: dict[str, int] = {}
    first_wrong = None
    for st, alias, pat, entry in _wrong_regulator_patterns():
        n = len(pat.findall(text))
        if n:
            wrong_regs[alias] = wrong_regs.get(alias, 0) + n
            first_wrong = first_wrong or (st, alias, entry)
    if wrong_regs:
        details["wrong_regulators"] = wrong_regs
        st, alias, entry = first_wrong
        correct = (_states()[st].get("authority") or {})
        right = correct.get("name", "the state regulator")
        if correct.get("short") and correct["short"] not in right:
            right += f" ({correct['short']})"
        total = sum(wrong_regs.values())
        return (
            False,
            f"Wrong regulator: the article names {', '.join(sorted(wrong_regs))} ({total}×) as an elevator "
            f"authority. {entry.get('why', '')} In {state_name(st)}, elevators are regulated by {right}. "
            f"Replace every mention with {right} and state only the facts listed in STATE REGULATORY FACTS; "
            f"do not mention {alias} at all.",
            details,
        )

    for st, pat, wc in _wrong_citation_patterns():
        m = pat.search(text)
        if m:
            details["wrong_citation"] = {"state": st, "found": m.group(0)}
            return (
                False,
                f"Wrong citation: \"{m.group(0)}\" is not the {state_name(st)} elevator rule. The correct "
                f"citation is {wc['correct']}. Fix every occurrence.",
                details,
            )

    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    for st, pat, nr in _not_required_patterns():
        if st not in home:
            continue
        # Sentence by sentence, skipping denials ("video is not required …").
        m = next(
            (hit for sent in sentences if not _NEGATION.search(sent) for hit in [pat.search(sent)] if hit),
            None,
        )
        if m:
            details["not_required"] = {"state": st, "id": nr.get("id"), "found": m.group(0)}
            return (
                False,
                f"Unsupported requirement: the article presents this as required in {state_name(st)} — "
                f"\"{m.group(0)}\". Per the verified fact sheet: {nr['claim']} {nr.get('why', '')} "
                "Remove the claim.".replace("  ", " "),
                details,
            )

    return True, "", details
