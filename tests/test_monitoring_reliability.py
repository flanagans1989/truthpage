"""PR 1 — Tier-2 monitoring reliability: escalation is plan-independent, the
daily Tier-2 budget queues rather than skips, and resource-health tracking
fires (and dedupes) the Monitoring Alert email.

Service-level, against the throwaway SQLite database. Network calls
(fetch_raw_html's Tier-1/Tier-2, the LLM analyzer, the mailer) are all
monkeypatched — this suite is about the bookkeeping around them, not the
scraping or classification itself.
"""
from datetime import timedelta

import pytest
from sqlalchemy import select

import app.services.monitoring as monitoring_mod
from app.core.llm.schemas import DiffAnalysis
from app.db.models.change_event import ChangeEvent
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.monitoring import run_subprocessor_check


async def _make_tenant(session_factory, **kwargs) -> Tenant:
    async with session_factory() as session:
        tenant = Tenant(
            name=kwargs.pop("name", "Acme"),
            slug=kwargs.pop("slug", "acme"),
            email=kwargs.pop("email", "owner@acme.com"),
            subscription_status=kwargs.pop("subscription_status", "free"),
            **kwargs,
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return tenant


async def _make_subprocessor(session_factory, tenant: Tenant, **kwargs) -> Subprocessor:
    async with session_factory() as session:
        sp = Subprocessor(
            tenant_id=tenant.id,
            name=kwargs.pop("name", "Vendor"),
            monitored_url=kwargs.pop("monitored_url", "https://vendor.example.com/privacy"),
            **kwargs,
        )
        session.add(sp)
        await session.commit()
        await session.refresh(sp)
        return sp


async def _reload(session_factory, sp_id):
    async with session_factory() as session:
        return await session.get(Subprocessor, sp_id)


def _patch_llm(monkeypatch):
    async def fake_analyze(diff_text):
        return DiffAnalysis(summary="cosmetic", classification="COSMETIC", confidence=0.99)

    monkeypatch.setattr(monitoring_mod._llm_analyzer, "analyze", fake_analyze)


def _patch_mailer_noop(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(monitoring_mod.mailer, "send_review_needed", noop)
    monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", noop)


class TestTier2IsPlanIndependent:
    @pytest.mark.asyncio
    async def test_a_free_plan_subprocessor_still_escalates_to_tier2(self, session_factory, monkeypatch):
        _patch_llm(monkeypatch)
        _patch_mailer_noop(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        calls = {"tier1": 0, "tier2": 0}

        async def fake_fetch_raw_html(url, *, use_browser=False, on_escalate=None):
            if use_browser:
                calls["tier2"] += 1
                return "<html><body>real content</body></html>"
            calls["tier1"] += 1
            # Simulate a Tier-1 bot wall by escalating, exactly like the real
            # fetcher's internal behaviour.
            if on_escalate is not None:
                await on_escalate()
            calls["tier2"] += 1
            return "<html><body>real content</body></html>"

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert calls["tier2"] == 1
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.requires_browser is True
        assert reloaded.last_content_hash is not None


class TestTier2DailyBudget:
    @pytest.mark.asyncio
    async def test_over_budget_queues_the_check_without_fetching_or_counting_a_failure(
        self, session_factory, monkeypatch
    ):
        tenant = await _make_tenant(session_factory, subscription_status="free")
        # Free tier defaults to a budget of 3/day — exhaust it up front.
        async with session_factory() as session:
            t = await session.get(Tenant, tenant.id)
            t.tier2_daily_date = utc_now().date()
            t.tier2_daily_count = t.tier2_daily_limit
            await session.commit()

        sp = await _make_subprocessor(session_factory, tenant, requires_browser=True)

        called = {"fetch": False}

        async def fake_fetch_raw_html(*args, **kwargs):
            called["fetch"] = True
            raise AssertionError("fetch_raw_html must not run when the budget is exhausted")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert called["fetch"] is False
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 0
        # SQLite hands back a naive datetime regardless of how it was stored;
        # compare against a naive "now" rather than the timezone-aware one.
        assert reloaded.next_check_at is not None
        assert reloaded.next_check_at > utc_now().replace(tzinfo=None)

    @pytest.mark.asyncio
    async def test_a_fresh_day_resets_the_counter_and_lets_the_check_through(
        self, session_factory, monkeypatch
    ):
        _patch_llm(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        async with session_factory() as session:
            t = await session.get(Tenant, tenant.id)
            t.tier2_daily_date = utc_now().date() - timedelta(days=1)
            t.tier2_daily_count = 999  # yesterday's exhausted budget
            await session.commit()

        sp = await _make_subprocessor(session_factory, tenant, requires_browser=True)

        async def fake_fetch_raw_html(*args, **kwargs):
            return "<html><body>real content</body></html>"

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        reloaded_tenant = await session_factory().__aenter__()
        t2 = await reloaded_tenant.get(Tenant, tenant.id)
        assert t2.tier2_daily_date == utc_now().date()
        assert t2.tier2_daily_count == 1
        await reloaded_tenant.close()


class TestResourceHealthAndAlerting:
    @pytest.mark.asyncio
    async def test_third_consecutive_failure_sends_one_alert(self, session_factory, monkeypatch):
        tenant = await _make_tenant(session_factory, subscription_status="free", email="owner@acme.com")
        sp = await _make_subprocessor(session_factory, tenant)

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)
        # Isolate from whatever ADMIN_EMAILS a local .env supplies — these
        # tests are about the tenant/dedupe bookkeeping, not who's in it.
        monkeypatch.setattr(monitoring_mod.settings, "ADMIN_EMAILS", "")

        for i in range(3):
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 3
        assert reloaded.has_monitoring_alert is True
        assert reloaded.monitoring_alert_sent_at is not None
        assert "owner@acme.com" in sent
        # Sent exactly once, not once per failure past the threshold.
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_alert_is_not_resent_within_the_dedupe_window(self, session_factory, monkeypatch):
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)
        # Isolate from whatever ADMIN_EMAILS a local .env supplies — these
        # tests are about the tenant/dedupe bookkeeping, not who's in it.
        monkeypatch.setattr(monitoring_mod.settings, "ADMIN_EMAILS", "")

        for i in range(4):  # one past the threshold
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 4
        assert len(sent) == 1  # still just the one from the 3rd failure

    @pytest.mark.asyncio
    async def test_a_recovery_then_a_fresh_streak_alerts_again(self, session_factory, monkeypatch):
        _patch_llm(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)
        # Isolate from whatever ADMIN_EMAILS a local .env supplies — these
        # tests are about the tenant/dedupe bookkeeping, not who's in it.
        monkeypatch.setattr(monitoring_mod.settings, "ADMIN_EMAILS", "")

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        async def ok_fetch(*args, **kwargs):
            return "<html><body>real content</body></html>"

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)
        for _ in range(3):
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)
        assert len(sent) == 1

        # Recovers — health resets.
        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", ok_fetch)
        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 0
        assert reloaded.monitoring_alert_sent_at is None

        # Fails 3 more times right away — alerts again immediately, no
        # 7-day wait, because the dedupe stamp was cleared on recovery.
        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)
        for _ in range(3):
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)
        assert len(sent) == 2
