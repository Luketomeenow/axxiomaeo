from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.report import MonthlyReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/latest")
async def get_latest_report(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(select(MonthlyReport).order_by(MonthlyReport.created_at.desc()).limit(1))
    report = result.scalar_one_or_none()
    if not report:
        return {"message": "No reports generated yet"}
    return {
        "id": report.id,
        "report_month": report.report_month.isoformat() if report.report_month else None,
        "overall_citation_share": float(report.overall_citation_share or 0),
        "ai_referred_sessions": report.ai_referred_sessions,
        "content_pieces_published": report.content_pieces_published,
        "schema_coverage_pct": float(report.schema_coverage_pct or 0),
        "top_performing_queries": report.top_performing_queries,
        "gap_queries": report.gap_queries,
        "brand_breakdown": report.brand_breakdown,
        "full_report_json": report.full_report_json,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = ReportService(db)
    kpis = await service.get_dashboard_kpis()
    by_brand = await service.get_citation_by_brand()
    by_category = await service.get_citation_by_category()
    by_funnel = await service.get_citation_by_funnel()
    by_platform = await service.get_visibility_by_platform()
    topic_coverage = await service.get_topic_coverage()
    gaps = await service.get_gap_queries()
    gsc = await service.get_gsc_highlights()
    return {
        **kpis,
        "citation_by_brand": by_brand,
        "citation_by_category": by_category,
        "citation_by_funnel": by_funnel,
        "visibility_by_platform": by_platform,
        "topic_coverage": topic_coverage,
        "gap_queries": gaps[:20],
        "gsc_highlights": gsc,
    }


@router.get("/gsc")
async def get_gsc_highlights(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = ReportService(db)
    return await service.get_gsc_highlights()


@router.get("/traffic-trend")
async def get_traffic_trend(
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = ReportService(db)
    return await service.get_traffic_trend(days=days)


@router.post("/generate")
async def generate_report(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Generate a monthly report snapshot from current dashboard KPIs."""
    service = ReportService(db)
    report = await service.generate_monthly_report()
    return {
        "id": report.id,
        "report_month": report.report_month.isoformat() if report.report_month else None,
        "overall_citation_share": float(report.overall_citation_share or 0),
        "ai_referred_sessions": report.ai_referred_sessions,
        "content_pieces_published": report.content_pieces_published,
        "schema_coverage_pct": float(report.schema_coverage_pct or 0),
        "gap_queries": report.gap_queries,
        "brand_breakdown": report.brand_breakdown,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
