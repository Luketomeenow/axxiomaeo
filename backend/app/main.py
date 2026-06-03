import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import brands, citations, content, health, notifications, reports, schema
from app.workers.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        from app.utils.seed import seed_brands_and_queue

        await seed_brands_and_queue()
    except Exception as e:
        logger.warning("Seed skipped or partial: %s", e)
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(brands.router)
    app.include_router(content.router)
    app.include_router(schema.router)
    app.include_router(citations.router)
    app.include_router(reports.router)
    app.include_router(notifications.router)

    return app


app = create_app()
