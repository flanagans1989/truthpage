"""PR 1 — Tier-2 monitoring reliability: escalation is plan-independent,
Tier-2 budget is a per-source quota (with a tenant-wide safety valve) that
queues rather than skips, content health (bot walls / empty pages) counts as
a real failure, and two independent alarms — failure-count and staleness —
keep a source from going silently unwatched.

Service-level, against the throwaway SQLite database. Network calls
(fetch_raw_html's Tier-1/Tier-2, the LLM analyzer, the mailer) are all
monkeypatched — this suite is about the bookkeeping around them, not the
scraping or classification itself.
"""
import asyncio
from datetime import timedelta

import pytest

import app.services.monitoring as monitoring_mod
from app.core.llm.schemas import DiffAnalysis
from app.core.scraper import fetcher as fetcher_mod
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.monitoring import run_subprocessor_check
from app.services.tier2_budget import try_spend_source_budget

# Real vendor pages are always well over the 500-char content-health floor;
# a bare "<html><body>real content</body></html>" fixture used to sail
# through checks that now correctly treat it as too short to be real.
_HEALTHY_HTML = "<html><body>" + ("Our sub-processors and their purposes are listed below. " * 20) + "</body></html>"
assert len(_HEALTHY_HTML) > 500

_CLOUDFLARE_CHALLENGE_HTML = (
    "<html><head><title>Just a moment...</title></head>"
    "<body>Checking your browser before accessing vendor.example.com. "
    "This process is automatic. Enable JavaScript and cookies to continue.</body></html>"
)


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
    monkeypatch.setattr(monitoring_mod.mailer, "send_staleness_alert", noop)
    monkeypatch.setattr(monitoring_mod.mailer, "send_tier2_safety_valve_alert", noop)


def _isolate_admin_emails(monkeypatch):
    # These tests are about the tenant/dedupe bookkeeping, not about
    # whatever ADMIN_EMAILS a local .env happens to supply.
    monkeypatch.setattr(monitoring_mod.settings, "ADMIN_EMAILS", "")


class TestTier2IsPlanIndependent:
    @pytest.mark.asyncio
    async def test_a_free_plan_subprocessor_still_escalates_to_tier2(self, session_factory, monkeypatch):
        _patch_llm(monkeypatch)
        _patch_mailer_noop(monkeypatch)
        _isolate_admin_emails(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        calls = {"tier1": 0, "tier2": 0}

        async def fake_fetch_raw_html(url, *, use_browser=False, on_escalate=None):
            if use_browser:
                calls["tier2"] += 1
                return _HEALTHY_HTML
            calls["tier1"] += 1
            # Simulate a Tier-1 bot wall by escalating, exactly like the real
            # fetcher's internal behaviour.
            if on_escalate is not None:
                await on_escalate()
            calls["tier2"] += 1
            return _HEALTHY_HTML

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert calls["tier2"] == 1
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.requires_browser is True
        assert reloaded.last_content_hash is not None


class TestFetcherEscalatesOnContentSignatures:
    """The shared content_health keyword list also drives Tier-1's own
    escalation decision (fetcher.py) — a Tier-1 response that merely *looks*
    like a challenge page (HTTP 200, no distinguishing status code) must
    still escalate to Tier-2."""

    @pytest.mark.asyncio
    async def test_a_tier1_challenge_page_escalates_to_tier2(self, monkeypatch):
        async def fake_tier1(url):
            return _CLOUDFLARE_CHALLENGE_HTML, True  # bot-wall keyword match

        called = {"tier2": False}

        async def fake_tier2(url):
            called["tier2"] = True
            return _HEALTHY_HTML

        monkeypatch.setattr(fetcher_mod, "_fetch_tier1", fake_tier1)
        monkeypatch.setattr(fetcher_mod, "_fetch_tier2", fake_tier2)

        result = await fetcher_mod.fetch_raw_html("https://vendor.example.com/privacy")

        assert called["tier2"] is True
        assert result == _HEALTHY_HTML


class TestTier2DailyBudget:
    @pytest.mark.asyncio
    async def test_source_quota_exhausted_queues_the_check_and_marks_it_deferred(
        self, session_factory, monkeypatch
    ):
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(
            session_factory,
            tenant,
            requires_browser=True,
            tier2_daily_date=utc_now().date(),
        )
        # Exhaust this source's own quota up front (default 2/day).
        from app.core.config import settings as _settings

        async with session_factory() as session:
            row = await session.get(Subprocessor, sp.id)
            row.tier2_daily_count = _settings.TIER2_DAILY_PER_SOURCE
            await session.commit()

        called = {"fetch": False}

        async def fake_fetch_raw_html(*args, **kwargs):
            called["fetch"] = True
            raise AssertionError("fetch_raw_html must not run when the source's Tier-2 budget is exhausted")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert called["fetch"] is False
        reloaded = await _reload(session_factory, sp.id)
        # (1) never advances last_checked_at
        assert reloaded.last_checked_at is None
        assert reloaded.consecutive_failure_count == 0
        # (2) visibly marked deferred, not silently skipped
        assert reloaded.tier2_deferred is True
        assert reloaded.next_check_at is not None
        assert reloaded.next_check_at > utc_now().replace(tzinfo=None)

    @pytest.mark.asyncio
    async def test_a_fresh_day_resets_the_source_counter_and_lets_the_check_through(
        self, session_factory, monkeypatch
    ):
        _patch_llm(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(
            session_factory,
            tenant,
            requires_browser=True,
            tier2_daily_date=utc_now().date() - timedelta(days=1),
            tier2_daily_count=999,  # yesterday's exhausted quota
        )

        async def fake_fetch_raw_html(*args, **kwargs):
            return _HEALTHY_HTML

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.tier2_daily_date == utc_now().date()
        assert reloaded.tier2_daily_count == 1
        assert reloaded.tier2_deferred is False
        assert reloaded.last_checked_at is not None

    @pytest.mark.asyncio
    async def test_one_exhausted_source_does_not_starve_another_source(self, session_factory, monkeypatch):
        """Starvation regression: a per-tenant pool sized 1:1 with vendor
        limits meant one misbehaving source could eat the whole tenant's
        budget. The per-source quota makes that structurally impossible —
        assert directly that a second source is untouched by the first's
        exhaustion."""
        _patch_llm(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        from app.core.config import settings as _settings

        starved = await _make_subprocessor(
            session_factory, tenant, name="Starved Vendor",
            monitored_url="https://starved.example.com/privacy",
            requires_browser=True,
            tier2_daily_date=utc_now().date(),
            tier2_daily_count=_settings.TIER2_DAILY_PER_SOURCE,
        )
        healthy = await _make_subprocessor(
            session_factory, tenant, name="Healthy Vendor",
            monitored_url="https://healthy.example.com/privacy",
            requires_browser=True,
        )

        async def fake_fetch_raw_html(*args, **kwargs):
            return _HEALTHY_HTML

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch_raw_html)

        async with session_factory() as session:
            await run_subprocessor_check(starved.id, session)
        async with session_factory() as session:
            await run_subprocessor_check(healthy.id, session)

        starved_reloaded = await _reload(session_factory, starved.id)
        healthy_reloaded = await _reload(session_factory, healthy.id)
        assert starved_reloaded.tier2_deferred is True
        assert starved_reloaded.last_checked_at is None
        assert healthy_reloaded.tier2_deferred is False
        assert healthy_reloaded.last_checked_at is not None


class TestSweepOrdering:
    @pytest.mark.asyncio
    async def test_sweep_checks_the_least_recently_checked_source_first(self, session_factory, monkeypatch):
        from app.scheduler.jobs import sweep_due_subprocessors

        tenant = await _make_tenant(session_factory, subscription_status="free")
        never_checked = await _make_subprocessor(
            session_factory, tenant, name="Never checked",
            monitored_url="https://never.example.com/privacy",
        )
        checked_long_ago = await _make_subprocessor(
            session_factory, tenant, name="Checked long ago",
            monitored_url="https://long-ago.example.com/privacy",
            last_checked_at=utc_now() - timedelta(days=30),
        )
        checked_recently = await _make_subprocessor(
            session_factory, tenant, name="Checked recently",
            monitored_url="https://recent.example.com/privacy",
            last_checked_at=utc_now() - timedelta(minutes=5),
        )

        order = []

        async def fake_check(subprocessor_id, session):
            order.append(subprocessor_id)

        monkeypatch.setattr("app.scheduler.jobs.run_subprocessor_check", fake_check)

        await sweep_due_subprocessors(session_factory)

        # NULLS FIRST (never checked), then oldest-first among the rest.
        assert order == [never_checked.id, checked_long_ago.id, checked_recently.id]


class TestContentHealth:
    @pytest.mark.asyncio
    async def test_a_bot_wall_page_is_a_failure_not_a_snapshot(self, session_factory, monkeypatch):
        _isolate_admin_emails(monkeypatch)
        _patch_mailer_noop(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        async def fake_fetch(*args, **kwargs):
            return _CLOUDFLARE_CHALLENGE_HTML  # HTTP 200 in the real world

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 1
        assert reloaded.last_failure_reason == "bot_wall"
        assert reloaded.last_checked_at is None
        assert reloaded.last_content_hash is None
        assert reloaded.last_raw_html is None

    @pytest.mark.asyncio
    async def test_a_short_empty_body_is_a_failure(self, session_factory, monkeypatch):
        _isolate_admin_emails(monkeypatch)
        _patch_mailer_noop(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        async def fake_fetch(*args, **kwargs):
            return "<html><body>" + ("x" * 300) + "</body></html>"

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 1
        assert reloaded.last_failure_reason == "empty_content"
        assert reloaded.last_checked_at is None


class TestStalenessAlarm:
    @pytest.mark.asyncio
    async def test_a_source_stale_for_days_alerts_even_with_zero_failures(self, session_factory, monkeypatch):
        _patch_llm(monkeypatch)
        _isolate_admin_emails(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free", email="owner@acme.com")
        sp = await _make_subprocessor(
            session_factory, tenant,
            last_checked_at=utc_now() - timedelta(days=4),  # STALENESS_ALERT_DAYS default is 3
        )

        sent = []

        async def fake_staleness_alert(**kwargs):
            sent.append(kwargs["email"])

        async def noop(**kwargs):
            return None

        monkeypatch.setattr(monitoring_mod.mailer, "send_staleness_alert", fake_staleness_alert)
        monkeypatch.setattr(monitoring_mod.mailer, "send_review_needed", noop)
        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", noop)

        async def fake_fetch(*args, **kwargs):
            return _HEALTHY_HTML  # this run itself succeeds — staleness is about the *prior* gap

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert "owner@acme.com" in sent
        assert len(sent) == 1


class TestResourceHealthAndAlerting:
    @pytest.mark.asyncio
    async def test_third_consecutive_failure_sends_one_alert(self, session_factory, monkeypatch):
        _isolate_admin_emails(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free", email="owner@acme.com")
        sp = await _make_subprocessor(session_factory, tenant)

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)

        for _ in range(3):
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 3
        assert reloaded.last_failure_reason == "http_error"
        assert reloaded.has_monitoring_alert is True
        assert reloaded.monitoring_alert_sent_at is not None
        assert "owner@acme.com" in sent
        # Sent exactly once, not once per failure past the threshold.
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_alert_is_not_resent_within_the_dedupe_window(self, session_factory, monkeypatch):
        _isolate_admin_emails(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)

        for _ in range(4):  # one past the threshold
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)

        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.consecutive_failure_count == 4
        assert len(sent) == 1  # still just the one from the 3rd failure

    @pytest.mark.asyncio
    async def test_a_still_ongoing_outage_resends_after_the_dedupe_window(self, session_factory, monkeypatch):
        """DOĞRULAMA 2: a 7-day dedupe window is a resend cadence, not a
        one-time latch — an outage that outlasts the window alerts again."""
        _isolate_admin_emails(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free", email="owner@acme.com")
        sp = await _make_subprocessor(session_factory, tenant)

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)

        for _ in range(3):
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)
        assert len(sent) == 1

        # Simulate the outage having been going on for 8 days — push the
        # dedupe stamp back past the 7-day window.
        async with session_factory() as session:
            row = await session.get(Subprocessor, sp.id)
            row.monitoring_alert_sent_at = utc_now() - timedelta(days=8)
            await session.commit()

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert len(sent) == 2

    @pytest.mark.asyncio
    async def test_a_recovery_then_a_fresh_streak_alerts_again(self, session_factory, monkeypatch):
        _patch_llm(monkeypatch)
        _isolate_admin_emails(monkeypatch)
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant)

        sent = []

        async def fake_alert(**kwargs):
            sent.append(kwargs["email"])

        monkeypatch.setattr(monitoring_mod.mailer, "send_monitoring_alert", fake_alert)

        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("HTTP 500")

        async def ok_fetch(*args, **kwargs):
            return _HEALTHY_HTML

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
        assert reloaded.last_failure_reason is None
        assert reloaded.monitoring_alert_sent_at is None

        # Fails 3 more times right away — alerts again immediately, no
        # 7-day wait, because the dedupe stamp was cleared on recovery.
        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", failing_fetch)
        for _ in range(3):
            async with session_factory() as session:
                await run_subprocessor_check(sp.id, session)
        assert len(sent) == 2


class TestAtomicBudgetSpend:
    @pytest.mark.asyncio
    async def test_two_stale_in_memory_copies_still_add_up_to_two(self, session_factory):
        """DOĞRULAMA 1: the classic read-modify-write race is two workers
        each holding their own (already-loaded, now stale) copy of the same
        row. A plain "mutate the Python attribute and commit" implementation
        would have both copies see the pre-spend count and both write back
        the same +1 — a lost update. The atomic UPDATE...CASE...RETURNING in
        tier2_budget.py operates on the database row directly, so it cannot
        lose an update regardless of what either in-memory copy believes."""
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant, requires_browser=True)
        today = utc_now().date()

        async with session_factory() as s1, session_factory() as s2:
            stale_copy_1 = await s1.get(Subprocessor, sp.id)
            stale_copy_2 = await s2.get(Subprocessor, sp.id)
            assert stale_copy_1.tier2_daily_count == 0
            assert stale_copy_2.tier2_daily_count == 0

            ok1 = await try_spend_source_budget(stale_copy_1, today, s1)
            ok2 = await try_spend_source_budget(stale_copy_2, today, s2)

        assert ok1 is True
        assert ok2 is True
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.tier2_daily_count == 2

    @pytest.mark.asyncio
    async def test_genuinely_concurrent_spends_still_add_up_correctly(self, session_factory):
        tenant = await _make_tenant(session_factory, subscription_status="free")
        sp = await _make_subprocessor(session_factory, tenant, requires_browser=True)
        today = utc_now().date()

        async def _spend():
            async with session_factory() as session:
                row = await session.get(Subprocessor, sp.id)
                return await try_spend_source_budget(row, today, session)

        results = await asyncio.gather(_spend(), _spend())

        assert all(results)
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.tier2_daily_count == 2
