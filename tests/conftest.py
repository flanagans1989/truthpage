import os

# Settings reads .env locally; in CI there is none, so provide safe dummies
# BEFORE anything imports app.core.config.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("RESEND_API_KEY", "test")


# ── Shared throwaway database ────────────────────────────────────────────────
# SQLite, in memory, created from the models. The local .env points at the
# production Neon database, so a test that reaches for a real engine must
# never get that one.

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient


@pytest_asyncio.fixture
async def db_engine():
    from app.db.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
def anon_client(db_engine, session_factory):
    """A signed-out browser. No lifespan: it would start the sweep scheduler."""
    from app.db.session import get_db_session
    from app.main import app

    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    client = TestClient(app, raise_server_exceptions=False)
    # Without this every request looks like a bot to the language nudge.
    client.headers["user-agent"] = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36"
    yield client
    app.dependency_overrides.clear()
