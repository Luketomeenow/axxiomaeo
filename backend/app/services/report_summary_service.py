"""AI-written executive summary for a stored monthly report.

Mirrors citation_insights_service: one Claude call per report, cached in-memory
(keyed by report_id), defensive JSON parse, graceful no-data. Compares the
report to the chronologically previous one so the narrative is about what
CHANGED month over month, not just this month's absolutes.
"""

import json
import logging
import re

from sqlalchemy import select

from app.models.report import MonthlyReport
from app.services.claude_service import ClaudeService
from app.services.cost_service import create_and_record

logger = logging.getLogger(__name__)

# report_id -> generated summary payload.
_CACHE: dict[int, dict] = {}

SUMMARY_PROMPT = """You are an AEO (Answer Engine Optimization) analyst writing the monthly \
executive summary for a network of elevator service brands. The goal is getting these brands \
cited by AI answer engines (ChatGPT, Gemini, Perplexity).

Below is this month's report data and last month's headline numbers for comparison (JSON). \
Write a concise, plain-English executive summary focused on WHAT CHANGED and WHAT TO DO.

Return ONLY valid JSON (no markdown fences) in exactly this shape:

{{
  "summary": "3-4 sentence executive read: overall trajectory vs last month and why it matters",
  "highlights": ["a concrete win or positive move this month, with the number", "..."],
  "watch_outs": ["a decline, risk, or competitor gain, with the number", "..."],
  "next_steps": ["a specific recommended action for next month", "..."]
}}

Rules:
- Ground every point in the data — cite concrete numbers and month-over-month deltas.
- 2-5 items per list. Be specific to elevator AEO, not generic.
- If there is no previous month, frame it as the baseline.

Report data:
{data}
"""


class ReportSummaryService:
    def __init__(self, db):
        self.db = db
        self.claude = ClaudeService()

    async def get_summary(self, report_id: int, refresh: bool = False) -> dict:
        if not refresh and report_id in _CACHE:
            return {"status": "ok", "cached": True, **_CACHE[report_id]}

        report = await self.db.get(MonthlyReport, report_id)
        if not report:
            return {"status": "no_data", "message": "Report not found."}

        previous = None
        if report.report_month is not None:
            previous = (
                await self.db.execute(
                    select(MonthlyReport)
                    .where(MonthlyReport.report_month < report.report_month)
                    .order_by(MonthlyReport.report_month.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        data = self._build_data(report, previous)
        summary = await self._generate(data)
        payload = {"report_id": report_id, **summary}
        _CACHE[report_id] = payload
        return {"status": "ok", "cached": False, **payload}

    def _headline(self, report: MonthlyReport | None) -> dict | None:
        if report is None:
            return None
        return {
            "month": report.report_month.isoformat() if report.report_month else None,
            "citation_share": float(report.overall_citation_share or 0),
            "ai_referred_sessions": report.ai_referred_sessions or 0,
            "content_pieces_published": report.content_pieces_published or 0,
            "schema_coverage_pct": float(report.schema_coverage_pct or 0),
        }

    def _build_data(self, report: MonthlyReport, previous: MonthlyReport | None) -> dict:
        full = report.full_report_json or {}
        return {
            "current": {
                **(self._headline(report) or {}),
                "avg_visibility_pct": full.get("avg_visibility_pct"),
                "share_of_voice": full.get("share_of_voice"),
                "topic_coverage_pct": full.get("topic_coverage_pct"),
                "by_category": full.get("by_category"),
                "by_platform": full.get("by_platform"),
            },
            "previous": self._headline(previous),
            "top_performing_queries": (report.top_performing_queries or [])[:10],
            "gap_queries": (report.gap_queries or [])[:10],
            "brand_breakdown": report.brand_breakdown or {},
        }

    async def _generate(self, data: dict) -> dict:
        prompt = SUMMARY_PROMPT.format(data=json.dumps(data, default=str)[:10000])
        try:
            response = await create_and_record(
                self.claude.client,
                operation="report_summary",
                model=self.claude.model,
                max_tokens=1536,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse(response.content[0].text)
        except Exception:
            logger.exception("Report summary generation failed")
            return _empty_summary()

    def _parse(self, raw: str) -> dict:
        text = raw.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Report summary returned non-JSON")
            return _empty_summary()

        def _strs(key: str) -> list[str]:
            return [str(x) for x in (data.get(key) or []) if str(x).strip()][:5]

        return {
            "summary": str(data.get("summary", "")),
            "highlights": _strs("highlights"),
            "watch_outs": _strs("watch_outs"),
            "next_steps": _strs("next_steps"),
        }


def _empty_summary() -> dict:
    return {"summary": "", "highlights": [], "watch_outs": [], "next_steps": []}
