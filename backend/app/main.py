import logging
import re
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

    allow_origin_regex: str | None = None
    if settings.environment == "development":
        # Vite may use 5174+ if 5173 is taken — allow any local dev port.
        allow_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    elif settings.cors_origin_regex:
        # Production: e.g. allow Netlify deploy previews / branch deploys.
        allow_origin_regex = settings.cors_origin_regex

    cors_kwargs: dict = {
        "allow_origins": settings.cors_origin_list,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if allow_origin_regex:
        cors_kwargs["allow_origin_regex"] = allow_origin_regex
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    def _cors_headers(request: Request) -> dict:
        """CORS headers for error responses. Error responses (500/503) are
        produced ABOVE the CORS middleware, so they ship without an
        Access-Control-Allow-Origin header — the browser then reports a
        misleading CORS error that hides the real failure. Re-attach the header
        for allowed origins so the frontend receives the actual status + detail."""
        origin = request.headers.get("origin")
        if not origin:
            return {}
        allowed = origin in settings.cors_origin_list or bool(
            allow_origin_regex and re.fullmatch(allow_origin_regex, origin)
        )
        if not allowed:
            return {}
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, _exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable — check DATABASE_URL or DB_PASSWORD in backend/.env"},
            headers=_cors_headers(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        # Return the real 500 (with CORS headers) instead of a masked
        # "Failed to fetch". Internal tool → include the error for debugging.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Server error: {type(exc).__name__}: {str(exc)[:300]}"},
            headers=_cors_headers(request),
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
