"""Improvement Advisor — periodic AI analysis of what to improve and why.

Third instance of the cached-LLM-JSON pattern (citation_insights_service
analyzes one audit; report_summary_service narrates one report). The advisor
looks across the WHOLE platform — KPIs, per-brand citation share, posting
cadence, pipeline flow health, integrations, costs, worker errors — and
returns prioritized improvements, each grounded in the numbers that justify
it. Unlike the in-memory caches, reports persist to aeo.advisor_reports so
history survives redeploys and weekly runs can be compared.
"""

import json
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import AdvisorReport, WorkerError
from app.models.content import ContentPiece
from app.services.claude_service import ClaudeService
from app.services.cost_service import CostService, create_and_record
from app.services.pipeline_health_service import PipelineHealthService
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

ADVISOR_PROMPT = """You are the operations and AEO strategist for a platform that publishes \
content for a network of elevator service brands and tracks whether AI answer engines \
(ChatGPT, Gemini, Perplexity) cite them.

Below is a live snapshot (JSON): dashboard KPIs, citation share per brand, per-engine \
visibility, sample citation gaps, posts published per brand over the last 7 days, the \
pipeline flow-health stages, monthly costs, and worker-error counts.

Identify what most needs improving. Return ONLY valid JSON (no markdown fences), exactly:

{{
  "summary": "2-3 sentence plain-English state of the platform right now",
  "improvements": [
    {{"title": "short action", "why": "the data that justifies it — cite concrete numbers/brands/engines",
      "category": "content|citations|integrations|pipeline|schema",
      "priority": "high|medium|low", "brand_id": "brand id or null", "effort": "low|medium|high"}}
  ],
  "quick_wins": ["small concrete action doable this week", "..."]
}}

Rules:
- Ground every "why" in the supplied numbers — never generic advice.
- A broken pipeline stage or failing integration outranks content strategy.
- A brand with far lower citation share or zero recent posts deserves a targeted item.
- Max 10 improvements, ordered most-impactful first. 3-5 quick wins.

Snapshot:
{data}
"""


class AdvisorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reports = ReportService(db)
        self.claude = ClaudeService()

    async def get_latest(self, refresh: bool = False, trigger: str = "manual") -> dict:
        if not refresh:
            row = (
                await self.db.execute(
                    select(AdvisorReport).order_by(AdvisorReport.created_at.desc()).limit(1)
                )
            ).scalar_one_or_none()
            if row:
                return {"status": "ok", "cached": True, "report": self._row_to_dict(row)}
        return await self.generate(trigger=trigger)

    async def history(self, limit: int = 10) -> list[dict]:
        rows = (
            await self.db.execute(
                select(AdvisorReport).order_by(AdvisorReport.created_at.desc()).limit(limit)
            )
        ).scalars().all()
        return [self._row_to_dict(r) for r in rows]

    async def generate(self, trigger: str) -> dict:
        data = await self._aggregate()
        if not data.get("kpis") and not data.get("citation_by_brand"):
            return {
                "status": "no_data",
                "message": "Not enough data yet — run a citation audit and publish some "
                "content, then the advisor has something to analyze.",
            }

        payload = await self._generate_llm(data)
        if payload is None:
            return {"status": "error", "message": "Generation failed — try again."}

        row = AdvisorReport(trigger=trigger, payload=payload)
        self.db.add(row)
        await self.db.flush()
        return {"status": "ok", "cached": False, "report": self._row_to_dict(row)}

    def _row_to_dict(self, row: AdvisorReport) -> dict:
        return {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "trigger": row.trigger,
            **(row.payload or {}),
        }

    async def _aggregate(self) -> dict:
        async def safe(coro, default):
            try:
                return await coro
            except Exception as e:  # one dead feed must not kill the advisor
                logger.warning("Advisor aggregate feed failed: %s", e)
                return default

        kpis = await safe(self.reports.get_dashboard_kpis(), {})
        kpis.pop("last_updated", None)
        flow = await safe(
            PipelineHealthService(self.db).check_flow(include_wp_auth=False), {}
        )
        gaps = await safe(self.reports.get_gap_queries(limit=15), [])
        return {
            "kpis": kpis,
            "citation_by_brand": await safe(self.reports.get_citation_by_brand(), []),
            "visibility_by_platform": await safe(self.reports.get_visibility_by_platform(), []),
            "gap_examples": [
                {
                    "query": g["query"],
                    "brand": g["brand_id"],
                    "platform": g.get("platform"),
                    "competitor": g.get("competitor_cited"),
                }
                for g in gaps
            ],
            "posts_last_7_days": await safe(self._posting_cadence(), []),
            "flow_health": [
                {k: s[k] for k in ("key", "status", "detail")} for s in flow.get("stages", [])
            ],
            "monthly_costs": await safe(self._costs(), {}),
            "worker_errors_7d": await safe(self._worker_error_counts(), []),
        }

    async def _posting_cadence(self) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=7)
        rows = (
            await self.db.execute(
                select(
                    ContentPiece.brand_id,
                    func.date(ContentPiece.published_at).label("day"),
                    func.count(ContentPiece.id),
                )
                .where(
                    ContentPiece.status == "published",
                    ContentPiece.published_at >= cutoff,
                )
                .group_by(ContentPiece.brand_id, func.date(ContentPiece.published_at))
                .order_by(ContentPiece.brand_id, func.date(ContentPiece.published_at))
            )
        ).all()
        return [
            {"brand_id": b, "day": str(day), "posts": n} for b, day, n in rows
        ]

    async def _costs(self) -> dict:
        costs = await CostService(self.db).monthly_costs()
        return {
            "period_month": costs.get("period_month"),
            "total_usd": costs.get("total_usd"),
            "items": [
                {"label": i.get("label"), "cost_usd": i.get("cost_usd")}
                for i in (costs.get("items") or [])[:8]
            ],
        }

    async def _worker_error_counts(self) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=7)
        rows = (
            await self.db.execute(
                select(WorkerError.worker_name, func.count(WorkerError.id))
                .where(WorkerError.created_at >= cutoff)
                .group_by(WorkerError.worker_name)
                .order_by(func.count(WorkerError.id).desc())
            )
        ).all()
        return [{"worker_name": name, "count": n} for name, n in rows]

    async def _generate_llm(self, data: dict) -> dict | None:
        prompt = ADVISOR_PROMPT.format(data=json.dumps(data, default=str)[:14000])
        try:
            response = await create_and_record(
                self.claude.client,
                operation="improvement_advisor",
                model=self.claude.model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = self._parse(response.content[0].text)
        except Exception:
            logger.exception("Improvement advisor generation failed")
            return None
        if parsed is None:
            return None
        stage_statuses = {s.get("status") for s in data.get("flow_health", [])}
        parsed["data_summary"] = {
            "citation_share": (data.get("kpis") or {}).get("citation_share"),
            "brands_posting_7d": len({r["brand_id"] for r in data.get("posts_last_7_days", [])}),
            "flow_overall": (
                "fail" if "fail" in stage_statuses else "warn" if "warn" in stage_statuses else "ok"
            ),
        }
        return parsed

    def _parse(self, raw: str) -> dict | None:
        text = raw.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Improvement advisor returned non-JSON")
            return None

        improvements = []
        for item in (data.get("improvements") or [])[:10]:
            if not isinstance(item, dict):
                continue
            improvements.append(
                {
                    "title": str(item.get("title", "")),
                    "why": str(item.get("why", "")),
                    "category": str(item.get("category", "content")),
                    "priority": str(item.get("priority", "medium")),
                    "brand_id": (str(item["brand_id"]) if item.get("brand_id") else None),
                    "effort": str(item.get("effort", "medium")),
                }
            )
        return {
            "summary": str(data.get("summary", "")),
            "improvements": improvements,
            "quick_wins": [str(x) for x in (data.get("quick_wins") or []) if str(x).strip()][:5],
        }
