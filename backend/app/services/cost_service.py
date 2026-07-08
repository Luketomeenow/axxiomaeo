"""Estimated API-spend tracking for the Reports page.

Estimates monthly cost across the three paid AI services the platform uses —
content creation (Claude), image generation (Ideogram), and AI-visibility
tracking (Bright Data) — from volume we already record (drafts generated,
images produced, citation records scraped) times configurable unit rates.

These are estimates for tracking/budgeting, not billing-grade metering. Set the
rates (COST_PER_* env) to your actual observed/negotiated prices; upgrade to
exact token metering later if you need precision.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.citation import CitationRecord
from app.models.content import ContentDraft


class CostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        s = get_settings()
        self.rate_content = s.cost_per_content_generation_usd
        self.rate_image = s.cost_per_image_usd
        self.rate_record = s.cost_per_citation_record_usd

    async def monthly_costs(self, month_start: datetime | None = None) -> dict:
        now = datetime.utcnow()
        month_start = month_start or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Content creation: one generation per draft created this month (each is
        # a full-article Claude call plus its image-planning / correction calls).
        content_units = await self.db.scalar(
            select(func.count(ContentDraft.id)).where(ContentDraft.created_at >= month_start)
        ) or 0

        # Image generation: every image produced on this month's drafts.
        images_json_rows = (
            await self.db.execute(
                select(ContentDraft.images_json).where(ContentDraft.created_at >= month_start)
            )
        ).scalars().all()
        image_units = sum(len(j) for j in images_json_rows if isinstance(j, list))

        # AI-visibility tracking: every Bright Data record scraped this month.
        record_units = await self.db.scalar(
            select(func.count(CitationRecord.id)).where(CitationRecord.checked_at >= month_start)
        ) or 0

        content_usd = round(content_units * self.rate_content, 2)
        image_usd = round(image_units * self.rate_image, 2)
        tracking_usd = round(record_units * self.rate_record, 2)

        return {
            "period_month": month_start.date().isoformat(),
            "estimated": True,
            "items": [
                {
                    "key": "content",
                    "label": "Content creation (Claude)",
                    "units": content_units,
                    "unit": "generations",
                    "rate_usd": self.rate_content,
                    "cost_usd": content_usd,
                },
                {
                    "key": "images",
                    "label": "Image generation",
                    "units": image_units,
                    "unit": "images",
                    "rate_usd": self.rate_image,
                    "cost_usd": image_usd,
                },
                {
                    "key": "tracking",
                    "label": "AI-visibility tracking (Bright Data)",
                    "units": record_units,
                    "unit": "records",
                    "rate_usd": self.rate_record,
                    "cost_usd": tracking_usd,
                },
            ],
            "total_usd": round(content_usd + image_usd + tracking_usd, 2),
        }
