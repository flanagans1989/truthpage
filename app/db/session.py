import ssl as _ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Neon (and any remote host) requires SSL; local dev does not
_is_remote = not any(h in settings.DATABASE_URL for h in ("localhost", "127.0.0.1"))
_connect_args = {"ssl": _ssl.create_default_context()} if _is_remote else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Neon Postgres: detects stale connections before use
    pool_size=3,         # Neon free tier: max 5 connections; leave 2 for migrations/admin
    max_overflow=1,      # allow 1 burst connection (total=4), never hit the hard limit
    connect_args=_connect_args,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
