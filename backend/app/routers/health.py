from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    db_ok = False
    db_error = None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_error = str(e)

    status = "ok" if db_ok else "degraded"
    payload = {"status": status, "service": "axxiom-aeo-api", "database": "connected" if db_ok else "disconnected"}
    if db_error:
        payload["database_error"] = db_error
    return payload
