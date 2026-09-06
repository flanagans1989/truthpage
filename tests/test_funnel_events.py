"""funnel_events instrumentation: track() writes exactly once per call, never
breaks the request it's called from, and the routes wired to it actually
write a row — walked end to end on a throwaway SQLite database, same shape
as tests/test_onboarding_flow.py.
"""
import hashlib
import hmac
import time
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.db.base import Base
from app.db.models.funnel_event import FunnelEvent
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.main import app
from app.routers.auth import _make_session_token
from app.services.analytics import track


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def tenant(db_engine, session_factory):
    async with session_factory() as session:
        row = Tenant(
            name="Acme",
            slug="acme",
            email="owner@acme.com",
            subscription_status="trialing",
            trial_ends_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        session.add(row)
        await session.commit()
    return row


@pytest.fixture
def client(db_engine, session_factory, tenant):
    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["user-agent"] = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36"
    c.cookies.set("session", _make_session_token(str(tenant.id)))
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db_engine, session_factory):
    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    # https base_url: APP_URL is https in tests (see conftest), so the
    # anon-id cookie is set Secure — an http TestClient would silently drop
    # it on the next request and every visit would look "new".
    c = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    c.headers["user-agent"] = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36"
    yield c
    app.dependency_overrides.clear()


async def _events(session_factory, event_name: str | None = None) -> list[FunnelEvent]:
    async with session_factory() as session:
        stmt = select(FunnelEvent)
        if event_name is not None:
            stmt = stmt.where(FunnelEvent.event_name == event_name)
        return list((await session.execute(stmt)).scalars().all())


async def _count(session_factory) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count()).select_from(FunnelEvent))).scalar_one()


class TestTrackNeverBreaksTheRequest:
    @pytest.mark.asyncio
    async def test_track_writes_exactly_one_row(self, session_factory):
        async with session_factory() as session:
            await track(session, "landing_view", anon_id="abc123")
        assert await _count(session_factory) == 1

    @pytest.mark.asyncio
    async def test_track_swallows_a_bad_session_without_raising(self):
        class _ExplodingSession:
            def add(self, obj):
                raise RuntimeError("boom")

            async def rollback(self):
                return None

        # Must not raise — a broken analytics write is not a reason to fail
        # the request it was called from.
        await track(_ExplodingSession(), "landing_view")


class TestAnonIdCookie:
    def test_a_first_visit_gets_a_tp_aid_cookie(self, anon_client):
        response = anon_client.get("/")
        assert "tp_aid" in response.cookies

    def test_a_returning_visit_keeps_its_own_id(self, anon_client):
        first = anon_client.get("/")
        aid = first.cookies["tp_aid"]
        # TestClient persists cookies across requests within a session.
        second = anon_client.get("/")
        assert second.cookies.get("tp_aid", aid) == aid


class TestLandingView:
    @pytest.mark.asyncio
    async def test_landing_view_is_tracked_once(self, anon_client, session_factory):
        anon_client.get("/")
        rows = await _events(session_factory, "landing_view")
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_no_personal_data_ends_up_on_the_row(self, anon_client, session_factory):
        anon_client.get("/")
        rows = await _events(session_factory, "landing_view")
        row = rows[0]
        assert row.anon_id is not None
        # A random uuid4, never an IP or a user-agent string.
        assert "Mozilla" not in (row.anon_id or "")
        assert "." not in (row.anon_id or "")  # rules out a dotted IPv4


class TestSignupFunnel:
    @pytest.mark.asyncio
    async def test_signup_requested_is_tracked(self, anon_client, session_factory):
        anon_client.post("/auth/request", data={"email": "new@customer.com"})
        rows = await _events(session_factory, "signup_requested")
        assert len(rows) == 1


class TestOnboardingCompleted:
    @pytest.mark.asyncio
    async def test_fires_once_on_the_first_subprocessor_only(self, client, session_factory, tenant):
        client.post("/onboarding/library", data={"slugs": ["stripe"]})
        client.post("/onboarding/library", data={"slugs": ["sentry"]})
        rows = await _events(session_factory, "onboarding_completed")
        assert len(rows) == 1
        assert rows[0].tenant_id == tenant.id


class TestCheckoutOpened:
    """_PRICE_IDS is read from settings once at import time (see billing.py),
    so a test has to patch that dict directly rather than settings — patching
    settings.PADDLE_PRICE_ID_GROWTH after import has no effect on it."""

    def test_checkout_opened_is_tracked_when_billing_is_configured(self, client, monkeypatch):
        from app.core.config import settings
        from app.routers import billing

        monkeypatch.setitem(billing._PRICE_IDS, ("growth", "monthly"), "pri_123")
        monkeypatch.setattr(settings, "PADDLE_CLIENT_TOKEN", "test_token")

        response = client.get("/dashboard/billing/checkout")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_checkout_opened_row_is_written(self, client, session_factory, monkeypatch):
        from app.core.config import settings
        from app.routers import billing

        monkeypatch.setitem(billing._PRICE_IDS, ("growth", "monthly"), "pri_123")
        monkeypatch.setattr(settings, "PADDLE_CLIENT_TOKEN", "test_token")

        client.get("/dashboard/billing/checkout")
        rows = await _events(session_factory, "checkout_opened")
        assert len(rows) == 1

    def test_checkout_shows_an_error_page_when_misconfigured(self, client, monkeypatch):
        from app.routers import billing

        monkeypatch.setitem(billing._PRICE_IDS, ("growth", "monthly"), "")
        response = client.get("/dashboard/billing/checkout")
        assert response.status_code == 503
        assert "temporarily unavailable" in response.text.lower()


class TestBillingStatus:
    """/healthz opens its own session against the real (dummy-in-CI) engine
    rather than the injected one (see tests/test_i18n_routes.py), so it
    can't be driven end-to-end here — billing_status() is tested directly,
    same function /healthz calls."""

    def test_configured_outside_production(self, monkeypatch):
        from app.core.config import settings
        from app.main import billing_status

        monkeypatch.setattr(settings, "PADDLE_ENVIRONMENT", "sandbox")
        assert billing_status() == "configured"

    def test_configured_in_production_with_everything_set(self, monkeypatch):
        from app.core.config import settings
        from app.main import billing_status

        monkeypatch.setattr(settings, "PADDLE_ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "PADDLE_API_KEY", "key")
        monkeypatch.setattr(settings, "PADDLE_CLIENT_TOKEN", "token")
        monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", "secret")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "pri_123")
        assert billing_status() == "configured"

    def test_flags_a_missing_production_price_id(self, monkeypatch):
        from app.core.config import settings
        from app.main import billing_status

        monkeypatch.setattr(settings, "PADDLE_ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "PADDLE_API_KEY", "key")
        monkeypatch.setattr(settings, "PADDLE_CLIENT_TOKEN", "token")
        monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", "secret")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "")
        assert billing_status() == "misconfigured"

    def test_flags_a_malformed_price_id(self, monkeypatch):
        from app.core.config import settings
        from app.main import billing_status

        monkeypatch.setattr(settings, "PADDLE_ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "PADDLE_API_KEY", "key")
        monkeypatch.setattr(settings, "PADDLE_CLIENT_TOKEN", "token")
        monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", "secret")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "not-a-price-id")
        assert billing_status() == "misconfigured"


def _sign_paddle(payload: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    h1 = hmac.new(secret.encode(), f"{ts}:{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


class TestPaddleWebhookFunnelEvents:
    """subscription_started fires only for the actual subscription.activated
    event (not every subscription.updated), and subscription_canceled for
    subscription.canceled — see app/routers/webhooks.py."""

    @pytest_asyncio.fixture
    async def paid_tenant(self, db_engine, session_factory):
        async with session_factory() as session:
            row = Tenant(
                name="Acme",
                slug="acme",
                email="owner@acme.com",
                subscription_status="trialing",
                paddle_customer_id="ctm_123",
                trial_ends_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    @pytest.fixture
    def webhook_client(self, db_engine, session_factory, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", "test-webhook-secret")

        async def _override():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db_session] = _override
        c = TestClient(app, raise_server_exceptions=False)
        yield c
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_subscription_activated_tracks_subscription_started(
        self, webhook_client, session_factory, paid_tenant
    ):
        import json

        payload = json.dumps({
            "event_type": "subscription.activated",
            "data": {"id": "sub_1", "customer_id": "ctm_123", "status": "active", "items": []},
        }).encode()
        header = _sign_paddle(payload, "test-webhook-secret")
        response = webhook_client.post(
            "/webhooks/paddle", content=payload, headers={"paddle-signature": header}
        )
        assert response.status_code == 200
        rows = await _events(session_factory, "subscription_started")
        assert len(rows) == 1
        assert rows[0].tenant_id == paid_tenant.id

    @pytest.mark.asyncio
    async def test_plain_subscription_updated_does_not_track_subscription_started(
        self, webhook_client, session_factory, paid_tenant
    ):
        import json

        payload = json.dumps({
            "event_type": "subscription.updated",
            "data": {"id": "sub_1", "customer_id": "ctm_123", "status": "active", "items": []},
        }).encode()
        header = _sign_paddle(payload, "test-webhook-secret")
        webhook_client.post("/webhooks/paddle", content=payload, headers={"paddle-signature": header})
        rows = await _events(session_factory, "subscription_started")
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_subscription_canceled_tracks_subscription_canceled(
        self, webhook_client, session_factory, paid_tenant
    ):
        import json

        payload = json.dumps({
            "event_type": "subscription.canceled",
            "data": {"id": "sub_1", "customer_id": "ctm_123", "status": "canceled"},
        }).encode()
        header = _sign_paddle(payload, "test-webhook-secret")
        response = webhook_client.post(
            "/webhooks/paddle", content=payload, headers={"paddle-signature": header}
        )
        assert response.status_code == 200
        rows = await _events(session_factory, "subscription_canceled")
        assert len(rows) == 1
        assert rows[0].tenant_id == paid_tenant.id
