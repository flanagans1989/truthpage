"""/admin/funnel: auth gate (reuses CurrentAdmin, nothing new), and the
paying-customer decision line — subscription_status == 'active' only, with
past_due/trialing/ever_paid shown for information but excluded from the
kill/continue count. Same fixture shape as tests/test_admin_outreach.py.
"""
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.db.base import Base
from app.db.models.funnel_event import FunnelEvent
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.main import app
from app.routers.auth import _make_session_token
from app.services.funnel_stats import collect_funnel_stats


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
async def admin_tenant(db_engine, session_factory):
    async with session_factory() as session:
        row = Tenant(name="Admin", slug="admin", email="admin@usetrustpages.com", subscription_status="active")
        session.add(row)
        await session.commit()
    return row


def _client(db_engine, session_factory, monkeypatch, admin_emails="admin@usetrustpages.com"):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADMIN_EMAILS", admin_emails)

    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def plain_tenant(db_engine, session_factory):
    async with session_factory() as session:
        row = Tenant(name="Someone", slug="someone", email="someone@else.com", subscription_status="active")
        session.add(row)
        await session.commit()
    return row


class TestAuthGate:
    def test_a_non_admin_gets_404(self, db_engine, session_factory, plain_tenant, monkeypatch):
        client = next(_client(db_engine, session_factory, monkeypatch))
        client.cookies.set("session", _make_session_token(str(plain_tenant.id)))
        assert client.get("/admin/funnel").status_code == 404

    def test_the_admin_email_gets_the_page(self, db_engine, session_factory, admin_tenant, monkeypatch):
        client = next(_client(db_engine, session_factory, monkeypatch))
        client.cookies.set("session", _make_session_token(str(admin_tenant.id)))
        r = client.get("/admin/funnel")
        assert r.status_code == 200
        assert "Ödeyen müşteri" in r.text


class TestFunnelStatsDecisionLine:
    @pytest.mark.asyncio
    async def test_paying_customers_counts_active_only(self, db_engine, session_factory):
        async with session_factory() as session:
            session.add_all([
                Tenant(name="A", slug="a", email="a@x.com", subscription_status="active"),
                Tenant(name="B", slug="b", email="b@x.com", subscription_status="active"),
                Tenant(name="C", slug="c", email="c@x.com", subscription_status="past_due"),
                Tenant(name="D", slug="d", email="d@x.com", subscription_status="trialing"),
                Tenant(name="E", slug="e", email="e@x.com", subscription_status="free"),
            ])
            await session.commit()

        async with session_factory() as session:
            stats = await collect_funnel_stats(session, now=datetime(2026, 9, 6, tzinfo=UTC))

        assert stats.paying_customers == 2
        assert stats.past_due_count == 1
        assert stats.trialing_count == 1
        assert stats.paying_target == 3
        assert stats.days_remaining == 30  # 2026-10-06 minus 2026-09-06

    @pytest.mark.asyncio
    async def test_ever_paid_is_not_windowed_to_30_days_and_ignores_cancellation(self, db_engine, session_factory):
        async with session_factory() as session:
            tenant = Tenant(name="Churned", slug="churned", email="c@x.com", subscription_status="free")
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)

            old = datetime(2026, 1, 1, tzinfo=UTC)  # well outside the 30-day window
            session.add(FunnelEvent(event_name="subscription_started", tenant_id=tenant.id, created_at=old))
            session.add(FunnelEvent(event_name="subscription_canceled", tenant_id=tenant.id, created_at=old))
            await session.commit()

        async with session_factory() as session:
            stats = await collect_funnel_stats(session, now=datetime(2026, 9, 6, tzinfo=UTC))

        # Not currently paying (free), but did pay at some point — a
        # different signal than the decision-line count, shown separately.
        assert stats.paying_customers == 0
        assert stats.ever_paid_count == 1

    @pytest.mark.asyncio
    async def test_conversion_rate_is_none_when_the_prior_step_has_no_actors(self, db_engine, session_factory):
        async with session_factory() as session:
            stats = await collect_funnel_stats(session, now=datetime(2026, 9, 6, tzinfo=UTC))
        assert all(c.rate_percent is None for c in stats.conversions)

    @pytest.mark.asyncio
    async def test_conversion_rate_between_two_populated_steps(self, db_engine, session_factory):
        now = datetime(2026, 9, 6, tzinfo=UTC)
        recent = now - timedelta(days=1)
        async with session_factory() as session:
            for aid in ("v1", "v2", "v3", "v4"):
                session.add(FunnelEvent(event_name="landing_view", anon_id=aid, created_at=recent))
            for aid in ("v1", "v2"):
                session.add(FunnelEvent(event_name="signup_requested", anon_id=aid, created_at=recent))
            await session.commit()

        async with session_factory() as session:
            stats = await collect_funnel_stats(session, now=now)

        step = next(c for c in stats.conversions if c.from_event == "landing_view")
        assert step.to_event == "signup_requested"
        assert step.rate_percent == 50.0
