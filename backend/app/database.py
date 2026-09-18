from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_db_url = settings.resolved_database_url()
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)


OSSRDBMS_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

_token_cache: dict = {"token": "", "expires_on": 0.0}
_credential = None


async def _entra_token() -> str:
    """Microsoft Entra access token for Azure Database for PostgreSQL, used as
    the connection password. asyncpg awaits this callable on every NEW pool
    connection; the token is cached until 5 minutes before expiry so a busy
    pool never hits the identity endpoint per connection. Credential chain:
    the app's user-assigned managed identity (AZURE_PG_CLIENT_ID) in Azure,
    `az login` on a developer machine."""
    global _credential
    import time

    if _token_cache["token"] and _token_cache["expires_on"] - time.time() > 300:
        return _token_cache["token"]
    if _credential is None:
        from azure.identity.aio import DefaultAzureCredential

        _credential = DefaultAzureCredential(
            managed_identity_client_id=settings.azure_pg_client_id or None
        )
    token = await _credential.get_token(OSSRDBMS_SCOPE)
    _token_cache["token"] = token.token
    _token_cache["expires_on"] = float(token.expires_on)
    return token.token


def _connect_args(url: str) -> dict:
    if settings.uses_azure_pg:
        # Azure Flexible Server: TLS always; password = Entra token (refreshed
        # per connection, see _entra_token). No statement-cache tweaks needed —
        # this is a direct connection, not a transaction pooler.
        return {"ssl": "require", "password": _entra_token}
    if "supabase" not in url:
        return {}
    args: dict = {"ssl": "require"}
    if ":6543" in url:
        args["statement_cache_size"] = 0
        args["prepared_statement_cache_size"] = 0
    return args


_engine_kwargs: dict = {}
if settings.uses_azure_pg:
    # Entra tokens live ~1h; recycle connections well inside that so a
    # long-lived pool never keeps a connection whose token has expired
    # (the server does not drop it, but a reconnect after a network blip would
    # fail without a fresh token — the callable handles that).
    _engine_kwargs.update(pool_size=settings.azure_pg_pool_size, max_overflow=5, pool_recycle=1800)

engine = create_async_engine(
    _db_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    connect_args=_connect_args(_db_url),
    **_engine_kwargs,
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


async def run_alter_migrations():
    """Apply additive SQL migrations (idempotent)."""
    migrations_dir = Path(__file__).parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("alter_aeo_*.sql"))
    if not sql_files:
        return
    async with engine.begin() as conn:
        for sql_path in sql_files:
            sql = sql_path.read_text(encoding="utf-8")
            for statement in sql.split(";"):
                lines = [
                    line
                    for line in statement.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                ]
                stmt = "\n".join(lines).strip()
                if stmt:
                    await conn.exec_driver_sql(stmt)


async def init_db():
    """Create schema (if configured) and all tables from ORM models."""
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        if settings.uses_azure_pg:
            # Azure: the tables are created by the Cloud Shell restore
            # (scripts/azure/aeo-data-cutover.sh --init) under Luke's login so
            # they are owned by `dataservices` and mirror to Fabric. If the app
            # itself ran create_all first, the tables would belong to the
            # managed identity and the restore would collide — refuse.
            count = (
                await conn.exec_driver_sql(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                    (settings.db_schema,),
                )
            ).scalar()
            if not count:
                raise RuntimeError(
                    f"Azure schema '{settings.db_schema}' has no tables — run "
                    "scripts/azure/aeo-data-cutover.sh --init before deploying the app"
                )
        elif settings.db_schema:
            await conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"')
        await conn.run_sync(Base.metadata.create_all)
    await run_alter_migrations()


async def close_credential():
    """Release the Entra credential's HTTP session on shutdown."""
    global _credential
    if _credential is not None:
        await _credential.close()
        _credential = None


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
