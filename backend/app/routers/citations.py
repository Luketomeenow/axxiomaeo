from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.citation import CitationRecord
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/citations", tags=["citations"])


@router.get("/latest")
async def get_latest_citations(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(CitationRecord).order_by(CitationRecord.checked_at.desc()).limit(200)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "brand_id": r.brand_id,
            "query": r.query,
            "query_category": r.query_category,
            "platform": r.platform,
            "is_cited": r.is_cited,
            "competitor_cited": r.competitor_cited,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        }
        for r in records
    ]


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
            "message": (
                "Citation provider unavailable — start GEO/AEO Tracker on :3000 "
                "with Bright Data keys, or set CITATION_PROVIDER=none in backend/.env"
            ),
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
