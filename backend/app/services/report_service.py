import logging
from datetime import datetime, timedelta

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


async def _latest_audit_run_id(db: AsyncSession) -> str | None:
    result = await db.execute(
        select(CitationRecord.audit_run_id)
        .where(CitationRecord.audit_run_id.isnot(None))
        .order_by(CitationRecord.checked_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


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
        latest_run = await _latest_audit_run_id(self.db)
        if latest_run:
            citation_rows = [c for c in citation_rows if c.audit_run_id == latest_run]
        cited = sum(1 for c in citation_rows if c.is_cited)
        total_citations = len(citation_rows)
        citation_share = round(cited / total_citations * 100, 1) if total_citations else 0

        visibility_scores = [c.visibility_pct for c in citation_rows if c.visibility_pct is not None]
        avg_visibility = round(sum(visibility_scores) / len(visibility_scores), 1) if visibility_scores else 0

        brand_citations = cited
        competitor_wins = sum(
            1 for c in citation_rows if not c.is_cited and c.competitor_cited
        )
        share_of_voice = (
            round(brand_citations / (brand_citations + competitor_wins) * 100, 1)
            if (brand_citations + competitor_wins)
            else 0
        )

        topic_coverage = await self.get_topic_coverage()

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
            "avg_visibility_pct": avg_visibility,
            "share_of_voice": share_of_voice,
            "topic_coverage_pct": topic_coverage.get("coverage_pct", 0),
            "platform_consensus_pct": await self._platform_consensus_pct(citation_rows),
            "ai_referred_sessions": ai_sessions,
            "content_published_mtd": content_count or 0,
            "schema_coverage_pct": schema_coverage,
            "last_updated": now.isoformat(),
        }

    async def _platform_consensus_pct(self, rows: list[CitationRecord]) -> float:
        """Share of seed queries cited on 2+ AI platforms."""
        by_key: dict[tuple[str, str], set[str]] = {}
        for r in rows:
            if r.parent_query:
                continue
            key = (r.brand_id, r.query)
            if r.is_cited and r.platform:
                by_key.setdefault(key, set()).add(r.platform)
        if not by_key:
            return 0.0
        multi = sum(1 for platforms in by_key.values() if len(platforms) >= 2)
        return round(multi / len(by_key) * 100, 1)

    async def get_topic_coverage(self) -> dict:
        latest_run = await _latest_audit_run_id(self.db)
        query = select(CitationRecord)
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        result = await self.db.execute(query)
        rows = result.scalars().all()
        categories = {r.query_category for r in rows if r.query_category}
        cited_categories = {
            r.query_category for r in rows if r.query_category and r.is_cited
        }
        total = len(categories) or 1
        return {
            "total_categories": len(categories),
            "cited_categories": len(cited_categories),
            "coverage_pct": round(len(cited_categories) / total * 100, 1),
            "categories": sorted(categories),
        }

    async def get_visibility_by_platform(self) -> list[dict]:
        latest_run = await _latest_audit_run_id(self.db)
        query = select(
            CitationRecord.platform,
            func.count(CitationRecord.id).label("total"),
            func.avg(CitationRecord.visibility_pct).label("avg_visibility"),
            func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
        )
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        query = query.group_by(CitationRecord.platform)
        result = await self.db.execute(query)
        rows = []
        for row in result:
            total = row.total or 0
            cited = row.cited or 0
            rows.append(
                {
                    "platform": row.platform,
                    "citation_share": round(cited / total * 100, 1) if total else 0,
                    "avg_visibility_pct": round(float(row.avg_visibility or 0), 1),
                    "total_checks": total,
                }
            )
        return rows

    async def get_citation_by_funnel(self) -> list[dict]:
        latest_run = await _latest_audit_run_id(self.db)
        query = select(
            CitationRecord.funnel_stage,
            func.count(CitationRecord.id).label("total"),
            func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
            func.avg(CitationRecord.visibility_pct).label("avg_visibility"),
        )
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        query = query.group_by(CitationRecord.funnel_stage)
        result = await self.db.execute(query)
        rows = []
        for row in result:
            total = row.total or 0
            cited = row.cited or 0
            rows.append(
                {
                    "funnel_stage": row.funnel_stage or "unknown",
                    "citation_share": round(cited / total * 100, 1) if total else 0,
                    "avg_visibility_pct": round(float(row.avg_visibility or 0), 1),
                }
            )
        return rows

    async def get_citation_by_brand(self) -> list[dict]:
        latest_run = await _latest_audit_run_id(self.db)
        query = select(
            CitationRecord.brand_id,
            func.count(CitationRecord.id).label("total"),
            func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
        )
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        query = query.group_by(CitationRecord.brand_id)
        result = await self.db.execute(query)
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
        latest_run = await _latest_audit_run_id(self.db)
        query = select(
            CitationRecord.query_category,
            func.count(CitationRecord.id).label("total"),
            func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
        )
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        query = query.group_by(CitationRecord.query_category)
        result = await self.db.execute(query)
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

    async def get_gap_queries(self, limit: int | None = 50) -> list[dict]:
        latest_run = await _latest_audit_run_id(self.db)
        query = select(CitationRecord).where(CitationRecord.is_cited == False)  # noqa: E712
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        query = query.order_by(CitationRecord.checked_at.desc())
        # Default limit is a dashboard/report top-N view — it's cross-brand,
        # so callers needing every brand's rows (e.g. topic discovery) must
        # raise it, or a brand whose rows sort later can be crowded out.
        if limit is not None:
            query = query.limit(limit)
        result = await self.db.execute(query)
        from app.utils.query_fanout import CATEGORY_CONTENT_TYPE

        return [
            {
                "id": r.id,
                "query": r.query,
                "brand_id": r.brand_id,
                "category": r.query_category,
                "competitor_cited": r.competitor_cited,
                "platform": r.platform,
                "visibility_pct": r.visibility_pct,
                "is_mentioned": r.is_mentioned,
                "is_url_cited": r.is_url_cited,
                "recommended_content_type": CATEGORY_CONTENT_TYPE.get(
                    r.query_category or "custom", "faq_hub"
                ),
                "invisible": not r.competitor_cited,
            }
            for r in result.scalars().all()
            if r.competitor_cited or not r.is_cited
        ]

    async def get_top_performing_queries(self, limit: int = 10) -> list[dict]:
        latest_run = await _latest_audit_run_id(self.db)
        query = select(CitationRecord).where(CitationRecord.is_cited == True)  # noqa: E712
        if latest_run:
            query = query.where(CitationRecord.audit_run_id == latest_run)
        query = query.order_by(CitationRecord.checked_at.desc()).limit(limit * 3)
        result = await self.db.execute(query)
        seen: set[tuple[str, str]] = set()
        rows = []
        for r in result.scalars().all():
            key = (r.brand_id, r.query)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "query": r.query,
                    "brand_id": r.brand_id,
                    "platform": r.platform,
                    "citation_url": r.citation_url,
                }
            )
            if len(rows) >= limit:
                break
        return rows

    async def get_traffic_trend(self, days: int = 90) -> dict:
        from app.config import get_settings

        settings = get_settings()
        has_credentials = bool(settings.google_service_account_json)

        brands_result = await self.db.execute(select(Brand))
        brands = brands_result.scalars().all()
        configured_brands = [b for b in brands if b.ga4_property_id]

        if not has_credentials and not configured_brands:
            return {"configured": False, "reason": "no_ga4", "brands": []}
        if not has_credentials:
            return {"configured": False, "reason": "no_credentials", "brands": []}
        if not configured_brands:
            return {"configured": False, "reason": "no_ga4", "brands": []}

        brand_series = []
        for brand in configured_brands:
            ai_data = await self.ga4.get_ai_referred_sessions_timeseries(
                brand.ga4_property_id, days=days
            )
            organic_data = await self.ga4.get_organic_search_sessions_timeseries(
                brand.ga4_property_id, days=days
            )
            brand_series.append(
                {
                    "brand_id": brand.id,
                    "brand_name": brand.name,
                    "data": ai_data,  # retained for backward compatibility (AI-referred)
                    "ai_data": ai_data,
                    "organic_data": organic_data,
                }
            )

        return {"configured": True, "brands": brand_series}

    async def get_search_vs_generative(self) -> dict:
        """Side-by-side comparison of traditional-search vs generative-AI
        visibility and traffic, aggregated across configured brands."""
        from app.config import get_settings

        has_google = bool(get_settings().google_service_account_json)
        kpis = await self.get_dashboard_kpis()

        brands_result = await self.db.execute(select(Brand))
        brands = brands_result.scalars().all()
        ga4_brands = [b for b in brands if b.ga4_property_id]
        gsc_brands = [b for b in brands if b.gsc_site_url]

        # --- Traditional search visibility (GSC site totals) ---
        gsc_impressions = 0
        gsc_clicks = 0
        weighted_pos = 0.0
        pos_weight = 0
        for brand in gsc_brands:
            totals = await self.gsc.get_site_totals(brand.gsc_site_url)
            gsc_impressions += totals.get("impressions", 0)
            gsc_clicks += totals.get("clicks", 0)
            impr = totals.get("impressions", 0)
            if impr:
                weighted_pos += totals.get("avg_position", 0) * impr
                pos_weight += impr
        avg_position = round(weighted_pos / pos_weight, 1) if pos_weight else 0

        # --- Traditional search traffic (GA4 Organic Search sessions) ---
        organic_sessions = 0
        for brand in ga4_brands:
            data = await self.ga4.get_organic_search_sessions(brand.ga4_property_id)
            organic_sessions += data.get("sessions", 0)

        return {
            "search": {
                "configured": has_google and bool(gsc_brands or ga4_brands),
                "visibility": {
                    "impressions": gsc_impressions,
                    "clicks": gsc_clicks,
                    "avg_position": avg_position,
                },
                "traffic": {"organic_search_sessions": organic_sessions},
            },
            "generative": {
                "configured": True,
                "visibility": {
                    "citation_share": kpis["citation_share"],
                    "avg_visibility_pct": kpis["avg_visibility_pct"],
                    "share_of_voice": kpis["share_of_voice"],
                },
                "traffic": {"ai_referred_sessions": kpis["ai_referred_sessions"]},
            },
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def get_gsc_highlights(self, limit: int = 15) -> dict:
        """Top GSC queries per brand with gsc_site_url configured."""
        from app.config import get_settings

        if not get_settings().google_service_account_json:
            return {"configured": False, "brands": []}

        brands_result = await self.db.execute(select(Brand))
        brands = [b for b in brands_result.scalars().all() if b.gsc_site_url]

        if not brands:
            return {"configured": True, "brands": [], "message": "No GSC site URLs in Brand Settings"}

        out = []
        for brand in brands:
            gaps = await self.get_gap_queries()
            brand_gaps = [g["query"] for g in gaps if g["brand_id"] == brand.id][:10]
            queries = brand_gaps or ["elevator maintenance", "elevator repair", "elevator inspection"]
            snippets = await self.gsc.get_featured_snippets(brand.gsc_site_url, queries[:10])
            ranked = sorted(snippets, key=lambda x: x.get("impressions", 0), reverse=True)[:limit]
            out.append(
                {
                    "brand_id": brand.id,
                    "brand_name": brand.name,
                    "site_url": brand.gsc_site_url,
                    "queries": ranked,
                }
            )

        return {"configured": True, "brands": out}

    async def generate_monthly_report(self) -> MonthlyReport:
        now = datetime.utcnow()
        month_start = now.replace(day=1)
        kpis = await self.get_dashboard_kpis()
        brand_breakdown = await self.get_citation_by_brand()
        gap_queries = await self.get_gap_queries()
        top_queries = await self.get_top_performing_queries()
        by_category = await self.get_citation_by_category()
        by_platform = await self.get_visibility_by_platform()
        by_funnel = await self.get_citation_by_funnel()

        # Store a self-contained snapshot so a stored report renders full charts
        # later without depending on current live data.
        full_report = {
            **kpis,
            "by_category": by_category,
            "by_platform": by_platform,
            "by_funnel": by_funnel,
        }

        # Upsert by month: regenerating the same month updates its row instead of
        # piling up duplicates (report_month has no unique constraint).
        existing = (
            await self.db.execute(
                select(MonthlyReport).where(MonthlyReport.report_month == month_start.date())
            )
        ).scalar_one_or_none()
        report = existing or MonthlyReport(report_month=month_start.date())

        report.overall_citation_share = kpis["citation_share"]
        report.ai_referred_sessions = kpis["ai_referred_sessions"]
        report.content_pieces_published = kpis["content_published_mtd"]
        report.schema_coverage_pct = kpis["schema_coverage_pct"]
        report.gap_queries = gap_queries[:10]
        report.top_performing_queries = top_queries
        report.brand_breakdown = {b["brand_id"]: b for b in brand_breakdown}
        report.full_report_json = full_report
        if existing is None:
            self.db.add(report)
        await self.db.flush()
        return report
