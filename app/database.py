from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _prepare_engine_args() -> tuple[str, dict]:
    """Strip asyncpg-incompatible URL params and build correct connect_args.

    asyncpg does not accept ``sslmode`` or ``channel_binding`` as URL query
    parameters — it requires SSL to be passed as a boolean flag in
    connect_args instead.  This function:

    1. Strips ``sslmode`` and ``channel_binding`` from the query string.
    2. Translates ``sslmode=require`` → ``connect_args={"ssl": True}``.
    3. Detects Neon pooler endpoints (PgBouncer in transaction mode) and sets
       ``statement_cache_size=0`` to prevent "prepared statement already
       exists" errors.
    """
    raw_url = settings.DATABASE_URL
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Extract SSL-related params that asyncpg can't handle in the URL
    sslmode = params.pop("sslmode", [None])[0]
    params.pop("channel_binding", None)

    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))

    connect_args: dict = {}

    # Apply SSL for remote hosts or when sslmode=require is explicitly set
    is_local = "localhost" in raw_url or "127.0.0.1" in raw_url
    needs_ssl = sslmode in ("require", "verify-ca", "verify-full") or not is_local
    if needs_ssl:
        connect_args["ssl"] = True

    # Neon pooler (PgBouncer) runs in transaction mode — asyncpg must not
    # cache prepared statements or it will receive "already exists" errors.
    if parsed.hostname and "-pooler." in parsed.hostname:
        connect_args["statement_cache_size"] = 0

    return clean_url, connect_args


_DB_URL, _CONNECT_ARGS = _prepare_engine_args()

engine = create_async_engine(
    _DB_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=_CONNECT_ARGS,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
