"""AI analysis of the latest citation audit → strategic AEO recommendations.

Distinct from the Recommendations Inbox (which turns individual citation gaps
into publishable content). This produces a narrative read of the WHOLE audit —
strengths, weaknesses, per-engine patterns, competitor threats, and prioritized
next steps — so a human can understand the dashboard at a glance.

Claude is called once per audit run and cached in-memory (keyed by
audit_run_id): cheap on repeat views, refreshes when a new audit lands or the
caller forces it. Reuses ReportService aggregates — invents no new signal.
"""

import json
import logging
import re

from sqlalchemy import select

from app.models.citation import CitationRecord
from app.services.claude_service import ClaudeService
from app.services.report_service import ReportService, _latest_audit_run_id

logger = logging.getLogger(__name__)

# audit_run_id -> generated insights payload (without transient status fields).
_CACHE: dict[str, dict] = {}

INSIGHTS_PROMPT = """You are an Answer Engine Optimization (AEO) strategist for a network of \
elevator service brands. Your job is to get these brands cited by AI answer engines \
(ChatGPT, Gemini, Perplexity) when people ask elevator questions.

Below is the latest citation-audit data (JSON): whether each brand was cited, per-engine \
visibility, category/funnel breakdowns, queries where competitors won instead, and the \
queries where we already win.

Analyze it and return ONLY valid JSON (no markdown fences) in exactly this shape:

{{
  "summary": "2-3 sentence plain-English read of where we stand right now",
  "strengths": ["specific thing working well", "..."],
  "weaknesses": ["specific gap or risk", "..."],
  "platform_insights": [
    {{"platform": "ChatGPT|Gemini|Perplexity", "insight": "what the data shows for this engine and why"}}
  ],
  "competitor_threats": [
    {{"competitor": "name or domain", "detail": "where/how they are winning citations from us"}}
  ],
  "recommendations": [
    {{"title": "short action", "detail": "what to do and the expected AEO impact",
      "priority": "high|medium|low", "category": "content|schema|local|technical|coverage"}}
  ]
}}

Rules:
- Ground every point in the data — cite concrete numbers, engines, queries, or competitors.
- Recommendations must be concrete and elevator/AEO-specific (not generic marketing advice).
- 3-6 items per list. Order recommendations most-impactful first.
- If a brand is invisible on an engine where a competitor is cited, that is high priority.

Audit data:
{data}
"""


class CitationInsightsService:
    def __init__(self, db):
        self.db = db
        self.reports = ReportService(db)
        self.claude = ClaudeService()

    async def get_insights(self, refresh: bool = False) -> dict:
        run_id = await _latest_audit_run_id(self.db)
        if not run_id:
            return {
                "status": "no_data",
                "message": "No citation audit has run yet. Run a citation audit to collect data, "
                "then generate AI recommendations here.",
            }
        if not refresh and run_id in _CACHE:
            return {"status": "ok", "cached": True, **_CACHE[run_id]}

        data = await self._aggregate(run_id)
        if data["overall"]["total_checks"] == 0:
            return {
                "status": "no_data",
                "message": "The latest audit has no results yet — try again once it finishes.",
            }

        insights = await self._generate(data)
        payload = {
            "audit_run_id": run_id,
            "data_summary": data["overall"],
            **insights,
        }
        _CACHE[run_id] = payload
        return {"status": "ok", "cached": False, **payload}

    async def _overall(self, run_id: str) -> dict:
        rows = (
            await self.db.execute(
                select(CitationRecord).where(CitationRecord.audit_run_id == run_id)
            )
        ).scalars().all()
        total = len(rows)
        cited = sum(1 for r in rows if r.is_cited)
        vis = [r.visibility_pct for r in rows if r.visibility_pct is not None]
        competitors: dict[str, int] = {}
        for r in rows:
            if not r.is_cited and r.competitor_cited:
                competitors[r.competitor_cited] = competitors.get(r.competitor_cited, 0) + 1
        return {
            "total_checks": total,
            "cited": cited,
            "citation_share_pct": round(cited / total * 100, 1) if total else 0,
            "avg_visibility_pct": round(sum(vis) / len(vis), 1) if vis else 0,
            "top_competitors": [
                {"name": name, "wins": n}
                for name, n in sorted(competitors.items(), key=lambda kv: -kv[1])[:8]
            ],
        }

    async def _aggregate(self, run_id: str) -> dict:
        gaps = await self.reports.get_gap_queries(limit=40)
        top = await self.reports.get_top_performing_queries(limit=10)
        return {
            "overall": await self._overall(run_id),
            "by_platform": await self.reports.get_visibility_by_platform(),
            "by_brand": await self.reports.get_citation_by_brand(),
            "by_category": await self.reports.get_citation_by_category(),
            "by_funnel": await self.reports.get_citation_by_funnel(),
            "gap_examples": [
                {
                    "query": g["query"],
                    "brand": g["brand_id"],
                    "platform": g.get("platform"),
                    "competitor": g.get("competitor_cited"),
                }
                for g in gaps[:30]
            ],
            "top_cited": [
                {"query": t["query"], "brand": t["brand_id"], "platform": t.get("platform")}
                for t in top
            ],
        }

    async def _generate(self, data: dict) -> dict:
        prompt = INSIGHTS_PROMPT.format(data=json.dumps(data, default=str)[:12000])
        try:
            response = await self.claude.client.messages.create(
                model=self.claude.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse(response.content[0].text)
        except Exception:
            logger.exception("Citation insights generation failed")
            return _empty_insights()

    def _parse(self, raw: str) -> dict:
        text = raw.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Citation insights returned non-JSON")
            return _empty_insights()

        def _strs(key: str, limit: int = 6) -> list[str]:
            return [str(x) for x in (data.get(key) or []) if str(x).strip()][:limit]

        def _objs(key: str, fields: tuple[str, ...], limit: int = 6) -> list[dict]:
            out = []
            for item in (data.get(key) or [])[:limit]:
                if isinstance(item, dict):
                    out.append({f: str(item.get(f, "")) for f in fields})
            return out

        return {
            "summary": str(data.get("summary", "")),
            "strengths": _strs("strengths"),
            "weaknesses": _strs("weaknesses"),
            "platform_insights": _objs("platform_insights", ("platform", "insight")),
            "competitor_threats": _objs("competitor_threats", ("competitor", "detail")),
            "recommendations": _objs(
                "recommendations", ("title", "detail", "priority", "category"), limit=8
            ),
        }


def _empty_insights() -> dict:
    return {
        "summary": "",
        "strengths": [],
        "weaknesses": [],
        "platform_insights": [],
        "competitor_threats": [],
        "recommendations": [],
    }
