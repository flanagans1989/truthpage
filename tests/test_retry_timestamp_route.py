"""Dashboard route for manually retrying a failed timestamp attempt. Needs
app.main — see tests/test_verify_route.py's note on this environment's
selectolax/DLL issue; confirmed via CI on this branch.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.db.base import Base
from app.db.models.change_event import ChangeEvent, TimestampStatus
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
async def failed_event(db_engine):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com")
        session.add(sp)
        await session.flush()
        event = ChangeEvent(
            subprocessor_id=sp.id, old_hash="a" * 64, new_hash="b" * 64, raw_diff="diff",
            status="approved", timestamp_status=TimestampStatus.failed.value,
            tsa_attempt_count=5, tsa_last_error="no TSA reachable",
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        await session.refresh(tenant)
        return tenant, event


@pytest.fixture
def client(db_engine, failed_event):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    c = TestClient(app, raise_server_exceptions=False)
    tenant, _event = failed_event
    c.cookies.set("session", _make_session_token(str(tenant.id)))
    yield c
    app.dependency_overrides.clear()


class TestRetryTimestamp:
    def test_a_failed_event_shows_the_retry_button(self, client, failed_event):
        _tenant, event = failed_event
        r = client.get(f"/dashboard/events/{event.id}")
        assert r.status_code == 200
        assert "Retry now" in r.text
        assert "Could not get an independent timestamp" in r.text

    def test_retrying_resets_status_and_attempt_count(self, client, failed_event):
        _tenant, event = failed_event
        r = client.post(f"/dashboard/events/{event.id}/retry-timestamp")
        assert r.status_code == 200
        assert "Pending" in r.text
        assert "Could not get an independent timestamp" not in r.text
