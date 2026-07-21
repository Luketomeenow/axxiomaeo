from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.citation import CitationRecord
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/citations", tags=["citations"])


def _serialize_record(r: CitationRecord) -> dict:
    return {
        "id": r.id,
        "brand_id": r.brand_id,
        "query": r.query,
        "query_category": r.query_category,
        "platform": r.platform,
        "is_cited": r.is_cited,
        "is_mentioned": r.is_mentioned,
        "is_url_cited": r.is_url_cited,
        "visibility_pct": r.visibility_pct,
        "sample_runs": r.sample_runs,
        "parent_query": r.parent_query,
        "funnel_stage": r.funnel_stage,
        "competitor_cited": r.competitor_cited,
        "citation_url": r.citation_url,
        "audit_run_id": r.audit_run_id,
        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
    }


def _parse_date(value: str, param: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{param} must be an ISO date (YYYY-MM-DD)") from e


@router.get("/latest")
async def get_latest_citations(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(CitationRecord).order_by(CitationRecord.checked_at.desc()).limit(200)
    )
    return [_serialize_record(r) for r in result.scalars().all()]


@router.get("/runs")
async def list_audit_runs(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Every citation audit run, newest first — id, date window, check counts.
    Powers the run/range selector on the Citations page."""
    result = await db.execute(
        select(
            CitationRecord.audit_run_id,
            func.min(CitationRecord.checked_at).label("started_at"),
            func.max(CitationRecord.checked_at).label("finished_at"),
            func.count(CitationRecord.id).label("total"),
            func.sum(func.cast(CitationRecord.is_cited, Integer)).label("cited"),
        )
        .where(CitationRecord.audit_run_id.isnot(None))
        .group_by(CitationRecord.audit_run_id)
        .order_by(func.max(CitationRecord.checked_at).desc())
    )
    return [
        {
            "audit_run_id": row.audit_run_id,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "total_checks": row.total or 0,
            "cited_checks": int(row.cited or 0),
        }
        for row in result
    ]


@router.get("/records")
async def get_citation_records(
    run_id: str | None = Query(None, description="Filter to one audit run"),
    start: str | None = Query(None, description="ISO date — include checks on/after this day"),
    end: str | None = Query(None, description="ISO date — include checks on/before this day"),
    limit: int = Query(3000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Citation checks for an audit run, a date range, or all history.

    No filters → full history (newest first, capped at ``limit``; the response
    carries ``total`` so the UI can tell when the cap truncated it).
    """
    filters = []
    if run_id:
        filters.append(CitationRecord.audit_run_id == run_id)
    if start:
        filters.append(CitationRecord.checked_at >= _parse_date(start, "start"))
    if end:
        # inclusive day: everything strictly before the next midnight
        filters.append(CitationRecord.checked_at < _parse_date(end, "end") + timedelta(days=1))

    total = await db.scalar(
        select(func.count(CitationRecord.id)).where(*filters)
    )
    result = await db.execute(
        select(CitationRecord)
        .where(*filters)
        .order_by(CitationRecord.checked_at.desc())
        .limit(limit)
    )
    records = [_serialize_record(r) for r in result.scalars().all()]
    return {"records": records, "total": total or 0, "truncated": (total or 0) > len(records)}


@router.post("/audit")
async def trigger_citation_audit(
    background_tasks: BackgroundTasks,
    _user: dict = Depends(get_current_user),
):
    from app.services.citation_service import CitationService
    from app.workers.citation_worker import run_citation_audit

    service = CitationService()
    if not await service.provider_available():
        return {
            "status": "unavailable",
            "message": service.unavailable_reason(),
        }

    background_tasks.add_task(run_citation_audit)
    return {"status": "audit_started"}


@router.get("/gaps")
async def get_gap_analysis(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = ReportService(db)
    return await service.get_gap_queries()


@router.get("/insights")
async def get_citation_insights(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """AI analysis of the latest audit (cached per audit run; refresh=1 forces)."""
    from app.services.citation_insights_service import CitationInsightsService

    return await CitationInsightsService(db).get_insights(refresh=refresh)
