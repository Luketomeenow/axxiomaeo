"""Billing-grade API-cost tracking.

Records one `cost_events` row per billable API call — Claude (real input/output
tokens), image generation (per image), Bright Data (per record) — with cost
computed from the configured rates at write time. The Reports page sums the
ledger per month.

Recording is strictly best-effort: it opens its own short-lived session and
swallows every error, so cost logging can never break content generation, image
generation, or a citation audit (mirrors record_worker_error). For months with
no ledger data yet, monthly_costs() falls back to a volume estimate so history
still shows something.
"""

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.citation import CitationRecord
from app.models.content import ContentDraft
from app.models.cost import CostEvent

logger = logging.getLogger(__name__)

# Which spend bucket each provider rolls up into on the report.
PROVIDER_CATEGORY = {
    "anthropic": "content",
    "ideogram": "images",
    "fal": "images",
    "openai": "images",
    "brightdata": "tracking",
}

_CATEGORY_LABEL = {
    "content": "Content creation (Claude)",
    "images": "Image generation",
    "tracking": "AI-visibility tracking (Bright Data)",
}


def _compute_cost(provider: str, input_tokens: int | None, output_tokens: int | None, units: int | None) -> float:
    s = get_settings()
    if provider == "anthropic":
        it = input_tokens or 0
        ot = output_tokens or 0
        return it / 1_000_000 * s.anthropic_input_cost_per_mtok + ot / 1_000_000 * s.anthropic_output_cost_per_mtok
    if provider in ("ideogram", "fal", "openai"):
        return (units or 0) * s.cost_per_image_usd
    if provider == "brightdata":
        return (units or 0) * s.cost_per_citation_record_usd
    return 0.0


async def record_cost_event(
    provider: str,
    operation: str,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    units: int | None = None,
    model: str | None = None,
    brand_id: str | None = None,
) -> None:
    """Write one ledger row. Best-effort: never raises into the caller."""
    try:
        from app.database import AsyncSessionLocal

        cost = round(_compute_cost(provider, input_tokens, output_tokens, units), 5)
        async with AsyncSessionLocal() as session:
            session.add(
                CostEvent(
                    provider=provider,
                    operation=operation,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    units=units,
                    cost_usd=cost,
                    brand_id=brand_id,
                )
            )
            await session.commit()
    except Exception:
        logger.debug("cost event not recorded (%s/%s)", provider, operation, exc_info=True)


async def create_and_record(client, *, operation: str, model: str, brand_id: str | None = None, **create_kwargs):
    """Call Claude's messages.create and log its real token usage as a cost event.

    Returns the raw response, so callers use it exactly as before. Recording is
    best-effort and never blocks the response.
    """
    response = await client.messages.create(model=model, **create_kwargs)
    try:
        usage = getattr(response, "usage", None)
        await record_cost_event(
            "anthropic",
            operation,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            model=model,
            brand_id=brand_id,
        )
    except Exception:
        logger.debug("anthropic usage not recorded (%s)", operation, exc_info=True)
    return response


class CostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def monthly_costs(self, month_start: datetime | None = None) -> dict:
        now = datetime.utcnow()
        month_start = month_start or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        rows = (
            await self.db.execute(select(CostEvent).where(CostEvent.created_at >= month_start))
        ).scalars().all()

        if not rows:
            # No ledger data for this month (e.g. before this shipped) — show the
            # volume estimate so the panel isn't empty.
            return await self._estimate(month_start)

        cats: dict[str, dict] = {
            k: {"cost_usd": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "units": 0}
            for k in ("content", "images", "tracking")
        }
        for e in rows:
            c = cats[PROVIDER_CATEGORY.get(e.provider, "content")]
            c["cost_usd"] += float(e.cost_usd or 0)
            c["calls"] += 1
            c["input_tokens"] += e.input_tokens or 0
            c["output_tokens"] += e.output_tokens or 0
            c["units"] += e.units or 0

        items = []
        for key in ("content", "images", "tracking"):
            c = cats[key]
            item = {
                "key": key,
                "label": _CATEGORY_LABEL[key],
                "cost_usd": round(c["cost_usd"], 2),
                "calls": c["calls"],
            }
            if key == "content":
                item["input_tokens"] = c["input_tokens"]
                item["output_tokens"] = c["output_tokens"]
                item["unit"] = "calls"
                item["units"] = c["calls"]
            else:
                item["units"] = c["units"]
                item["unit"] = "images" if key == "images" else "records"
            items.append(item)

        return {
            "period_month": month_start.date().isoformat(),
            "source": "ledger",
            "estimated": False,
            "items": items,
            "total_usd": round(sum(i["cost_usd"] for i in items), 2),
        }

    async def _estimate(self, month_start: datetime) -> dict:
        """Volume-based fallback for months with no ledger rows."""
        s = get_settings()
        content_units = await self.db.scalar(
            select(func.count(ContentDraft.id)).where(ContentDraft.created_at >= month_start)
        ) or 0
        images_json_rows = (
            await self.db.execute(
                select(ContentDraft.images_json).where(ContentDraft.created_at >= month_start)
            )
        ).scalars().all()
        image_units = sum(len(j) for j in images_json_rows if isinstance(j, list))
        record_units = await self.db.scalar(
            select(func.count(CitationRecord.id)).where(CitationRecord.checked_at >= month_start)
        ) or 0

        content_usd = round(content_units * s.cost_per_content_generation_usd, 2)
        image_usd = round(image_units * s.cost_per_image_usd, 2)
        tracking_usd = round(record_units * s.cost_per_citation_record_usd, 2)
        return {
            "period_month": month_start.date().isoformat(),
            "source": "estimate",
            "estimated": True,
            "items": [
                {"key": "content", "label": _CATEGORY_LABEL["content"], "units": content_units,
                 "unit": "generations", "cost_usd": content_usd},
                {"key": "images", "label": _CATEGORY_LABEL["images"], "units": image_units,
                 "unit": "images", "cost_usd": image_usd},
                {"key": "tracking", "label": _CATEGORY_LABEL["tracking"], "units": record_units,
                 "unit": "records", "cost_usd": tracking_usd},
            ],
            "total_usd": round(content_usd + image_usd + tracking_usd, 2),
        }
