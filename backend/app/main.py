import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import init_db
from app.routers import (
    brands,
    citations,
    content,
    health,
    notifications,
    recommendations,
    reports,
    schema,
)
from app.workers.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        from app.utils.seed import seed_brands_and_queue

        await seed_brands_and_queue()
    except Exception as e:
        logger.error("Database init/seed failed: %s", e)
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Axxiom AEO Automation API",
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_kwargs: dict = {
        "allow_origins": settings.cors_origin_list,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.environment == "development":
        # Vite may use 5174+ if 5173 is taken — allow any local dev port.
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    elif settings.cors_origin_regex:
        # Production: e.g. allow Netlify deploy previews / branch deploys.
        cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_request: Request, _exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable — check DATABASE_URL or DB_PASSWORD in backend/.env"},
        )

    app.include_router(health.router)
    app.include_router(brands.router)
    app.include_router(content.router)
    app.include_router(schema.router)
    app.include_router(citations.router)
    app.include_router(reports.router)
    app.include_router(notifications.router)
    app.include_router(recommendations.router)

    return app


app = create_app()
