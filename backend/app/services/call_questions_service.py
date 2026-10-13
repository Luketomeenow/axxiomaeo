"""Customer questions from phone calls: CallRail call summaries to observed questions.

CallRail writes an AI summary of most calls (what the caller wanted), and the
marketing warehouse loads them into public.fact_callrail_call, in the same
Postgres as this app. This daily scan turns the questions callers actually
asked into observed questions: the first-priority topic source for discovery,
and part of the weekly AI citation audit.

Personal details never leave the scrub. Names (including the call's
customer_name), phone numbers, emails, links, street addresses and long
numbers are removed before the model sees a summary. The model is told to
generalize, and every question it returns must quote a phrase that really is
in the scrubbed summary and contain no name, number or address. Only the
generalized question is stored. Read-only on the warehouse; each call is
scanned once (aeo.call_question_scans).
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.brand import Brand
from app.models.observed_question import CallQuestionScan
from app.services.cost_service import create_and_record
from app.utils.geography import query_out_of_market

logger = logging.getLogger(__name__)

# CallRail company name (normalized, substring) -> brand id. Motion and
# Nashville are not AEO brands. CALLRAIL_COMPANY_BRANDS (JSON) extends this.
DEFAULT_COMPANY_BRANDS = {
    "ameritex": "ameritex",
    "arizona elevator": "arizona_es",
    "liftech": "liftech",
    "quality elevator": "quality",
    "carolina elevator": "carolina",
    "axxiom florida": "axxiom",
}

INTENTS = (
    "cost", "maintenance", "repair", "modernization", "installation",
    "inspection", "compliance", "other",
)
_BATCH = 20
# One scan at a time (the 7:15 job and a manual backfill could otherwise read
# the same calls twice). The app runs a single process, so a lock suffices.
_scan_lock = asyncio.Lock()
_MAX_PER_CALL = 2

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
_STREET = re.compile(
    r"\b\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,4}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl"
    r"|Parkway|Pkwy|Highway|Hwy|Circle|Cir|Terrace|Ter|Suite|Ste)\b\.?",
    re.I,
)
_LONG_NUMBER = re.compile(r"\b\d{5,}\b")  # account, ticket and ZIP-like numbers
# Words that show up in CallRail's caller name (often the caller-ID business
# or "WIRELESS CALLER") but name no person; scrubbing them would delete the
# building type from the summary and block good questions.
_GENERIC_NAME_TOKENS = {
    "elevator", "elevators", "company", "services", "service", "solutions", "property",
    "properties", "management", "group", "the", "and", "inc", "llc", "corp", "unknown",
    "caller", "customer", "wireless", "mobile", "cell", "phone", "name", "unavailable",
    "hotel", "hospital", "medical", "center", "apartments", "apartment", "condo",
    "condominium", "school", "university", "college", "church", "office", "offices",
    "plaza", "tower", "towers", "building", "senior", "living", "county", "city", "state",
    "district", "association", "hoa", "realty", "partners", "holdings", "trust", "bank",
}

_CALLS_SQL = text("""
SELECT DISTINCT ON (call_id)
       call_id, company_name, customer_name, source, start_time, first_time_caller, call_summary
FROM public.fact_callrail_call
WHERE start_time > now() - make_interval(days => :days)
  AND call_summary IS NOT NULL AND length(call_summary) > 40
ORDER BY call_id, snapshot_date DESC
""")

SYSTEM_PROMPT = """You read short summaries of phone calls to an elevator service company and \
pull out the questions callers actually asked, so the company can publish clear answers to them.

For each call:
- Include a question only if the caller asked it or clearly wanted it answered: costs and \
quotes, maintenance contracts, repairs, modernization, installation, inspections, codes and \
compliance, equipment, timelines, switching providers.
- Skip dispatch for an existing problem with no question beyond "please send someone", billing \
or invoices, scheduling or confirming an appointment, vendors and sales pitches, job seekers, \
wrong numbers, spam, internal calls, and voicemails without a question.
- Rewrite each question as a general question a building owner or property manager would ask, \
under 140 characters. Never include a person's or company's name, a street address, a phone \
number, an email, an account number or a price the caller was quoted. A city or a building type \
is fine.
- At most 2 questions per call. Most calls have 0 or 1.
- For every question, give "basis": a phrase of 3 to 12 words copied exactly from that call's \
summary, showing where the question came from.
Call submit_questions once, listing every call id, with an empty list for calls without a question."""

SUBMIT_TOOL = {
    "name": "submit_questions",
    "description": "Submit the customer questions found in each call summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "intent": {"type": "string", "enum": list(INTENTS)},
                                    "basis": {"type": "string"},
                                },
                                "required": ["question", "intent", "basis"],
                            },
                        },
                    },
                    "required": ["id", "questions"],
                },
            }
        },
        "required": ["calls"],
    },
}


@dataclass
class CallRow:
    call_id: str
    brand_id: str
    brand_name: str
    summary: str  # scrubbed
    names: set[str]  # the name tokens that were scrubbed
    started_at: datetime | None
    source: str | None
    first_time: bool


# --- pure helpers (unit-tested) ---------------------------------------------


def company_mapping(override_json: str = "") -> dict[str, str]:
    mapping = dict(DEFAULT_COMPANY_BRANDS)
    if override_json.strip():
        try:
            extra = json.loads(override_json)
            mapping.update({_norm(k): str(v) for k, v in extra.items()})
        except (ValueError, AttributeError):
            logger.warning("CALLRAIL_COMPANY_BRANDS is not a JSON object; using the defaults")
    return mapping


def brand_for_company(company_name: str | None, mapping: dict[str, str]) -> str | None:
    name = _norm(company_name)
    if not name:
        return None
    for key, brand_id in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        if _norm(key) in name:
            return brand_id
    return None


def _norm(value) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def name_tokens(names: list[str | None], keep: set[str] = frozenset()) -> set[str]:
    """Words of the caller's name to scrub. ``keep`` = words that are not
    personal: the brand's market cities, since caller ID for an unknown
    number is often just "PHOENIX AZ"."""
    tokens = set()
    for name in names:
        for t in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", name or ""):
            word = t.lower()
            if word not in _GENERIC_NAME_TOKENS and word not in keep:
                tokens.add(word)
    return tokens


def market_words(markets: list[str] | None) -> set[str]:
    return {w for m in (markets or []) for w in _norm(m).split() if len(w) > 2}


def scrub_pii(summary: str, names: list[str | None] = (), keep: set[str] = frozenset()) -> str:
    """Remove personal details before a summary goes anywhere."""
    out = _EMAIL.sub("[email]", summary or "")
    out = _URL.sub("[link]", out)
    out = _PHONE.sub("[phone]", out)
    out = _STREET.sub("[address]", out)
    out = _LONG_NUMBER.sub("[number]", out)
    for token in name_tokens(list(names), keep):
        out = re.sub(rf"\b{re.escape(token)}\b", "[name]", out, flags=re.I)
    return out


def grounded(basis: str | None, summary: str) -> bool:
    """The model's basis phrase really appears in the (scrubbed) summary."""
    b = _norm(basis)
    return len(b.split()) >= 3 and b in _norm(summary)


def clean_question(question: str | None, names: set[str]) -> str | None:
    """A storable question, or None if it is malformed or leaks a detail."""
    q = " ".join(str(question or "").split()).strip()
    if not 15 <= len(q) <= 180:
        return None
    if "[" in q or "]" in q:
        return None
    if any(p.search(q) for p in (_EMAIL, _URL, _PHONE, _STREET, _LONG_NUMBER)):
        return None
    if names & set(_norm(q).split()):
        return None
    q = q.rstrip(".!") + ("" if q.endswith("?") else "?")
    return q[0].upper() + q[1:]


def parse_extraction(raw: dict, batch: dict[str, CallRow]) -> tuple[list[dict], dict[str, int]]:
    """Validated questions from the tool input, plus questions-per-call for
    every call the model answered (so those calls are marked scanned)."""
    found: list[dict] = []
    per_call: dict[str, int] = {}
    for entry in raw.get("calls") or []:
        if not isinstance(entry, dict):
            continue
        call = batch.get(str(entry.get("id")))
        if call is None:
            continue
        per_call.setdefault(call.call_id, 0)
        names = call.names
        for q in (entry.get("questions") or [])[:_MAX_PER_CALL]:
            if not isinstance(q, dict):
                continue
            question = clean_question(q.get("question"), names)
            if not question or not grounded(q.get("basis"), call.summary):
                continue
            per_call[call.call_id] += 1
            found.append(
                {
                    "call_id": call.call_id,
                    "brand_id": call.brand_id,
                    "question": question,
                    "intent": q.get("intent") if q.get("intent") in INTENTS else "other",
                    "basis": " ".join(str(q.get("basis")).split())[:200],
                    "asked_at": call.started_at,
                    "call_source": call.source,
                    "first_time_caller": call.first_time,
                    "index": per_call[call.call_id],
                }
            )
    return found, per_call


def _naive_utc(value) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# --- service -------------------------------------------------------------------


class CallQuestionsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def run(self, days: int | None = None, max_calls: int | None = None) -> dict:
        """Scan call summaries from the last ``days`` (default: the lookback
        setting), newest first, at most ``max_calls`` (default: the setting)."""
        async with _scan_lock:
            return await self._run(days, max_calls)

    async def _run(self, days: int | None, max_calls: int | None) -> dict:
        s = self.settings
        days = max(1, min(90, days or s.call_questions_lookback_days))
        max_calls = max(1, max_calls or s.call_questions_max_calls)
        brands = {b.id: b for b in (await self.db.execute(select(Brand))).scalars().all()}
        mapping = company_mapping(s.callrail_company_brands)
        try:
            # Savepoint: a missing warehouse table must not abort the caller's
            # transaction (same reason as callrail_service).
            async with self.db.begin_nested():
                rows = (await self.db.execute(_CALLS_SQL, {"days": days})).all()
        except Exception:
            logger.exception("Call questions: CallRail warehouse unavailable")
            return {"status": "unavailable", "message": "CallRail call data is not readable right now."}

        stats = {"calls_with_summary": len(rows), "not_an_aeo_brand": 0, "already_scanned": 0}
        scanned = set()
        ids = [r.call_id for r in rows]
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            scanned |= set(
                (
                    await self.db.execute(
                        select(CallQuestionScan.call_id).where(CallQuestionScan.call_id.in_(chunk))
                    )
                ).scalars().all()
            )

        calls: list[CallRow] = []
        for r in rows:
            brand_id = brand_for_company(r.company_name, mapping)
            if not brand_id or brand_id not in brands:
                stats["not_an_aeo_brand"] += 1
                continue
            if r.call_id in scanned:
                stats["already_scanned"] += 1
                continue
            keep = market_words(brands[brand_id].markets)
            calls.append(
                CallRow(
                    call_id=str(r.call_id),
                    brand_id=brand_id,
                    brand_name=brands[brand_id].name,
                    summary=scrub_pii(r.call_summary, [r.customer_name], keep),
                    names=name_tokens([r.customer_name], keep),
                    started_at=_naive_utc(r.start_time),
                    source=r.source,
                    first_time=str(r.first_time_caller).lower() == "true",
                )
            )
        calls.sort(key=lambda c: c.started_at or datetime.min, reverse=True)
        stats["not_scanned_over_cap"] = max(0, len(calls) - max_calls)
        calls = calls[:max_calls]
        stats["calls_scanned"] = 0

        found: list[dict] = []
        for start in range(0, len(calls), _BATCH):
            batch = {f"c{i}": c for i, c in enumerate(calls[start:start + _BATCH])}
            raw = await self._ask(batch, brands)
            if raw is None:
                continue  # not marked scanned, so the next run retries these calls
            questions, per_call = parse_extraction(raw, batch)
            found += questions
            for call in batch.values():
                if call.call_id in per_call:
                    self.db.add(
                        CallQuestionScan(call_id=call.call_id, brand_id=call.brand_id, questions=per_call[call.call_id])
                    )
                    stats["calls_scanned"] += 1
            await self.db.flush()

        out_of_market = 0
        items = []
        for q in found:
            brand = brands[q["brand_id"]]
            if query_out_of_market(q["question"], "", brand.markets):
                out_of_market += 1
                continue
            items.append(
                {
                    "brand_id": q["brand_id"],
                    "question": q["question"],
                    "source": "call",
                    "asked_at": q["asked_at"],
                    "external_ref": f"callrail:{q['call_id']}:{q['index']}",
                    "detail": {
                        "origin": "callrail_summary",
                        "intent": q["intent"],
                        "basis": q["basis"],
                        "call_source": q["call_source"],
                        "first_time_caller": q["first_time_caller"],
                    },
                }
            )
        from app.services.observed_questions import store_observed_questions

        stored = await store_observed_questions(self.db, items) if items else {"accepted": 0, "duplicates": 0}
        return {
            "status": "ok",
            **stats,
            "questions_found": len(found),
            "out_of_market": out_of_market,
            "stored": stored["accepted"],
            "duplicates": stored["duplicates"],
        }

    async def _ask(self, batch: dict[str, CallRow], brands: dict[str, Brand]) -> dict | None:
        from app.services.claude_service import ClaudeService

        claude = ClaudeService()
        payload = [
            {
                "id": key,
                "brand": call.brand_name,
                "markets": ", ".join(brands[call.brand_id].markets or []),
                "summary": call.summary,
            }
            for key, call in batch.items()
        ]
        messages = [{"role": "user", "content": json.dumps(payload)}]
        # Structured outputs are not enabled on the Foundry deployment: tool
        # call with tool_choice auto first, forced only on the retry.
        for tool_choice in ({"type": "auto"}, {"type": "tool", "name": SUBMIT_TOOL["name"]}):
            try:
                response = await create_and_record(
                    claude.client,
                    operation="call_questions",
                    model=claude.model,
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    tools=[SUBMIT_TOOL],
                    tool_choice=tool_choice,
                    messages=messages,
                )
            except Exception as exc:
                logger.warning("Call questions: extraction call failed (%s): %s", tool_choice["type"], type(exc).__name__)
                continue
            if getattr(response, "stop_reason", None) == "max_tokens":
                # A tool call cut off mid-JSON is not trustworthy; the calls
                # stay unscanned and the next run retries them.
                logger.warning("Call questions: extraction hit max_tokens; batch left for the next run")
                return None
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and block.name == SUBMIT_TOOL["name"]:
                    return block.input if isinstance(block.input, dict) else None
        return None
