from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.report import MonthlyReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _serialize_report(report: MonthlyReport) -> dict:
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


@router.get("/costs")
async def get_report_costs(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Estimated current-month API spend: content (Claude), images, tracking (Bright Data)."""
    from app.services.cost_service import CostService

    return await CostService(db).monthly_costs()


@router.get("/latest")
async def get_latest_report(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(MonthlyReport)
        .order_by(MonthlyReport.report_month.desc(), MonthlyReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        return {"message": "No reports generated yet"}
    return _serialize_report(report)


@router.get("")
async def list_reports(
    limit: int = Query(24, ge=1, le=120),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Newest-first list of historical reports (lightweight rows for the history
    browser + trend chart). Full detail is at GET /api/reports/{id}."""
    total = await db.scalar(select(func.count(MonthlyReport.id)))
    result = await db.execute(
        select(MonthlyReport)
        .order_by(MonthlyReport.report_month.desc(), MonthlyReport.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    reports = [
        {
            "id": r.id,
            "report_month": r.report_month.isoformat() if r.report_month else None,
            "overall_citation_share": float(r.overall_citation_share or 0),
            "ai_referred_sessions": r.ai_referred_sessions,
            "content_pieces_published": r.content_pieces_published,
            "schema_coverage_pct": float(r.schema_coverage_pct or 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.scalars().all()
    ]
    return {"total": total or 0, "reports": reports}


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


@router.get("/search-vs-generative")
async def get_search_vs_generative(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Side-by-side traditional-search vs generative-AI visibility & traffic."""
    service = ReportService(db)
    return await service.get_search_vs_generative()


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
    """Generate (or refresh) this month's report snapshot from current KPIs."""
    service = ReportService(db)
    report = await service.generate_monthly_report()
    await db.commit()  # generate_monthly_report only flushes; persist it here
    return _serialize_report(report)


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Full stored report by id (declared last so it doesn't shadow named routes)."""
    report = await db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _serialize_report(report)


@router.get("/{report_id}/summary")
async def get_report_summary(
    report_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """AI executive summary of a report vs the prior month (cached; refresh=1 forces)."""
    from app.services.report_summary_service import ReportSummaryService

    return await ReportSummaryService(db).get_summary(report_id, refresh=refresh)
