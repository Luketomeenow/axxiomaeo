import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import engine, get_db
from app.models.approval import WorkerError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        # Details stay in server logs — this endpoint is unauthenticated.
        logger.warning("Health check database failure: %s", e)

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "service": "axxiom-aeo-api",
        "database": "connected" if db_ok else "disconnected",
    }


@router.get("/api/health/flow")
async def flow_health(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Live per-stage diagnosis of the daily content flow. Read-only — never
    sends alerts, safe for UI polling (WP probes are TTL-cached)."""
    from app.services.pipeline_health_service import PipelineHealthService

    return await PipelineHealthService(db).check_flow()


@router.get("/api/worker-errors")
async def list_worker_errors(
    limit: int = Query(50, ge=1, le=200),
    worker: str | None = Query(None, description="Filter by worker_name"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = select(WorkerError).order_by(WorkerError.created_at.desc()).limit(limit)
    if worker:
        query = query.where(WorkerError.worker_name == worker)
    rows = (await db.execute(query)).scalars().all()
    return {
        "errors": [
            {
                "id": r.id,
                "worker_name": r.worker_name,
                "error_message": r.error_message,
                "error_details": r.error_details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
