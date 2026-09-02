"""Hitting the plan's vendor limit shows an upgrade modal instead of a bare
422 an htmx swap would silently drop. Route-level, throwaway SQLite DB.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.core.config import settings
from app.db.base import Base
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.main import app
from app.routers.auth import _make_session_token


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def free_tenant_at_limit(db_engine):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        for i in range(settings.FREE_TIER_MAX_SUBPROCESSORS):
            session.add(
                Subprocessor(
                    tenant_id=tenant.id,
                    name=f"Vendor {i}",
                    monitored_url=f"https://vendor{i}.example.com/privacy",
                )
            )
        await session.commit()
    return tenant


@pytest.fixture
def client(db_engine, free_tenant_at_limit):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    c = TestClient(app)
    c.cookies.set("session", _make_session_token(str(free_tenant_at_limit.id)))
    yield c
    app.dependency_overrides.clear()


class TestLimitReached:
    def test_adding_past_the_limit_returns_200_not_422(self, client):
        r = client.post(
            "/dashboard/subprocessors",
            data={"name": "One too many", "monitored_url": "https://one-too-many.example.com"},
        )
        assert r.status_code == 200

    def test_the_upgrade_modal_is_in_the_response(self, client):
        r = client.post(
            "/dashboard/subprocessors",
            data={"name": "One too many", "monitored_url": "https://one-too-many.example.com"},
        )
        assert "upgrade-modal-slot" in r.text
        assert "hx-swap-oob" in r.text
        assert "$29/mo" in r.text
        assert "$89/mo" in r.text

    def test_the_rejected_vendor_is_not_added(self, client):
        client.post(
            "/dashboard/subprocessors",
            data={"name": "One too many", "monitored_url": "https://one-too-many.example.com"},
        )
        assert "One too many" not in client.get("/dashboard").text
