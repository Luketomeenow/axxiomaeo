from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.get("/latest")
async def latest_advisor_report(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Most recent Improvement Advisor report (refresh=1 regenerates)."""
    from app.services.advisor_service import AdvisorService

    return await AdvisorService(db).get_latest(refresh=refresh)


@router.get("/history")
async def advisor_history(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.services.advisor_service import AdvisorService

    return {"reports": await AdvisorService(db).history(limit=limit)}
