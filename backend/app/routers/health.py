import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

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
