import asyncio
from logging.config import fileConfig
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import all models so Alembic can autogenerate migrations
from app.database import Base  # noqa: F401
import app.models  # noqa: F401
from app.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Tables that Alembic must NEVER touch.
# PostGIS installs spatial_ref_sys, geography_columns, geometry_columns etc.
# Neon creates playing_with_neon as a tutorial table.
# Without this filter, autogenerate emits DROP TABLE for all of them.
# ---------------------------------------------------------------------------
_EXCLUDE_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
    "playing_with_neon",
}


def include_object(object, name, type_, reflected, compare_to):
    """Return False for any table that should be invisible to Alembic."""
    if type_ == "table" and name in _EXCLUDE_TABLES:
        return False
    return True


def _prepare_migration_args() -> tuple[str, dict]:
    """Same URL-cleaning logic as app/database.py.

    Strips asyncpg-incompatible query params (``sslmode``, ``channel_binding``)
    from the URL and translates them to connect_args so Alembic's migration
    engine can connect to Neon without errors.
    """
    raw_url = settings.DATABASE_URL
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    sslmode = params.pop("sslmode", [None])[0]
    params.pop("channel_binding", None)

    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))

    connect_args: dict = {}

    is_local = "localhost" in raw_url or "127.0.0.1" in raw_url
    needs_ssl = sslmode in ("require", "verify-ca", "verify-full") or not is_local
    if needs_ssl:
        connect_args["ssl"] = True

    if parsed.hostname and "-pooler." in parsed.hostname:
        connect_args["statement_cache_size"] = 0

    return clean_url, connect_args


_MIGRATION_URL, _MIGRATION_CONNECT_ARGS = _prepare_migration_args()

# Override sqlalchemy.url so alembic.ini's placeholder is never used at runtime.
config.set_main_option("sqlalchemy.url", _MIGRATION_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=_MIGRATION_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_MIGRATION_CONNECT_ARGS,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
