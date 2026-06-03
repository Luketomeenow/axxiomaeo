import logging
from datetime import date, datetime, timedelta

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.citation import CitationRecord
from app.models.content import ContentPiece
from app.models.report import MonthlyReport
from app.models.schema_job import SchemaJob
from app.services.ga4_service import GA4Service
from app.services.gsc_service import GSCService

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ga4 = GA4Service()
        self.gsc = GSCService()

    async def get_dashboard_kpis(self) -> dict:
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        content_count = await self.db.scalar(
            select(func.count(ContentPiece.id)).where(
                ContentPiece.published_at >= month_start,
                ContentPiece.status == "published",
            )
        )

        schema_total = await self.db.scalar(select(func.count(SchemaJob.id)))
        schema_valid = await self.db.scalar(
            select(func.count(SchemaJob.id)).where(SchemaJob.validation_status == "valid")
        )

        citations = await self.db.execute(
            select(CitationRecord).where(CitationRecord.checked_at >= month_start)
        )
        citation_rows = citations.scalars().all()
        cited = sum(1 for c in citation_rows if c.is_cited)
        total_citations = len(citation_rows)
        citation_share = round(cited / total_citations * 100, 1) if total_citations else 0

        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_citations = await self.db.execute(
            select(CitationRecord).where(
                CitationRecord.checked_at >= prev_month_start,
                CitationRecord.checked_at < month_start,
            )
        )
        prev_rows = prev_citations.scalars().all()
        prev_cited = sum(1 for c in prev_rows if c.is_cited)
        prev_share = round(prev_cited / len(prev_rows) * 100, 1) if prev_rows else 0

        brands = await self.db.execute(select(Brand))
        ai_sessions = 0
        for brand in brands.scalars().all():
            if brand.ga4_property_id:
                data = await self.ga4.get_ai_referred_sessions(brand.ga4_property_id)
                ai_sessions += data.get("sessions", 0)

        schema_coverage = round(schema_valid / schema_total * 100, 1) if schema_total else 0

        return {
            "citation_share": citation_share,
            "citation_share_prev": prev_share,
            "citation_trend": citation_share - prev_share,
            "ai_referred_sessions": ai_sessions,
            "content_published_mtd": content_count or 0,
            "schema_coverage_pct": schema_coverage,
            "last_updated": now.isoformat(),
        }

    async def get_citation_by_brand(self) -> list[dict]:
        result = await self.db.execute(
            select(
                CitationRecord.brand_id,
                func.count(CitationRecord.id).label("total"),
                func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
            ).group_by(CitationRecord.brand_id)
        )
        rows = []
        for row in result:
            total = row.total or 0
            cited = row.cited or 0
            rows.append(
                {
                    "brand_id": row.brand_id,
                    "citation_share": round(cited / total * 100, 1) if total else 0,
                    "total_queries": total,
                    "cited_queries": cited,
                }
            )
        return rows

    async def get_citation_by_category(self) -> list[dict]:
        result = await self.db.execute(
            select(
                CitationRecord.query_category,
                func.count(CitationRecord.id).label("total"),
                func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
            ).group_by(CitationRecord.query_category)
        )
        rows = []
        for row in result:
            total = row.total or 0
            cited = row.cited or 0
            rows.append(
                {
                    "category": row.query_category,
                    "citation_share": round(cited / total * 100, 1) if total else 0,
                }
            )
        return rows

    async def get_gap_queries(self) -> list[dict]:
        result = await self.db.execute(
            select(CitationRecord)
            .where(CitationRecord.is_cited == False)  # noqa: E712
            .order_by(CitationRecord.checked_at.desc())
            .limit(50)
        )
        return [
            {
                "query": r.query,
                "brand_id": r.brand_id,
                "category": r.query_category,
                "competitor_cited": r.competitor_cited,
                "platform": r.platform,
            }
            for r in result.scalars().all()
            if r.competitor_cited
        ]

    async def generate_monthly_report(self) -> MonthlyReport:
        now = datetime.utcnow()
        month_start = now.replace(day=1)
        kpis = await self.get_dashboard_kpis()
        brand_breakdown = await self.get_citation_by_brand()
        gap_queries = await self.get_gap_queries()

        report = MonthlyReport(
            report_month=month_start.date(),
            overall_citation_share=kpis["citation_share"],
            ai_referred_sessions=kpis["ai_referred_sessions"],
            content_pieces_published=kpis["content_published_mtd"],
            schema_coverage_pct=kpis["schema_coverage_pct"],
            gap_queries=gap_queries[:10],
            brand_breakdown={b["brand_id"]: b for b in brand_breakdown},
            full_report_json=kpis,
        )
        self.db.add(report)
        await self.db.flush()
        return report
