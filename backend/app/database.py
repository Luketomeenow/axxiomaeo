from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_db_url = settings.resolved_database_url()
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _connect_args(url: str) -> dict:
    if "supabase" not in url:
        return {}
    args: dict = {"ssl": "require"}
    if ":6543" in url:
        args["statement_cache_size"] = 0
        args["prepared_statement_cache_size"] = 0
    return args


engine = create_async_engine(
    _db_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    connect_args=_connect_args(_db_url),
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

metadata = MetaData(schema=settings.db_schema or None)


class Base(DeclarativeBase):
    metadata = metadata


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create schema (if configured) and all tables from ORM models."""
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        if settings.db_schema:
            await conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"')
        await conn.run_sync(Base.metadata.create_all)


async def run_sql_migration():
    """Run aeo_schema.sql for fresh Supabase installs."""
    sql_path = Path(__file__).parent.parent / "migrations" / "aeo_schema.sql"
    if not sql_path.exists():
        return
    sql = sql_path.read_text(encoding="utf-8")
    async with engine.begin() as conn:
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                await conn.exec_driver_sql(stmt)


async def check_db_connection() -> bool:
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
