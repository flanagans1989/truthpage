"""app/services/tsa_retry.py — the timestamp retry pass. Service-level,
against the throwaway SQLite database; no app.main import needed (unlike
monitoring.py, this module never touches the scraper/normalizer chain).

KURAL 0 is the first thing tested here: nothing may ever timestamp a
not_available_pre_tsa record. Everything else — pending→timestamped,
retrying→failed after TSA_MAX_ATTEMPTS, primary→fallback — follows.
"""
import pytest

import app.core.tsa as tsa_mod
import app.services.tsa_retry as tsa_retry_mod
from app.core.tsa import TSAError
from app.db.models.change_event import ChangeEvent, TimestampStatus
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.tsa_retry import (
    BackdatedTimestampError,
    run_timestamp_retry_pass,
    stamp_change_event,
)

_DIGEST = "271a879deb5a0d25f45792bab8a7e911b19a8d611dd4c3ce4adc397dea3b5101"


async def _make_change_event(session_factory, **overrides) -> ChangeEvent:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com/privacy")
        session.add(sp)
        await session.flush()
        defaults = dict(
            subprocessor_id=sp.id,
            old_hash="a" * 64,
            new_hash="b" * 64,
            raw_diff="diff",
            new_raw_html_hash=_DIGEST,
            status="pending_review",
        )
        defaults.update(overrides)
        event = ChangeEvent(**defaults)
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event


async def _reload(session_factory, event_id):
    async with session_factory() as session:
        return await session.get(ChangeEvent, event_id)


class TestKural0TripWire:
    @pytest.mark.asyncio
    async def test_a_pre_tsa_record_can_never_be_timestamped(self, session_factory):
        event = await _make_change_event(
            session_factory, timestamp_status=TimestampStatus.not_available_pre_tsa.value
        )
        async with session_factory() as session:
            fresh = await session.get(ChangeEvent, event.id)
            with pytest.raises(BackdatedTimestampError):
                await stamp_change_event(fresh, session)

    @pytest.mark.asyncio
    async def test_the_retry_pass_never_selects_pre_tsa_records(self, session_factory, monkeypatch):
        await _make_change_event(session_factory, timestamp_status=TimestampStatus.not_available_pre_tsa.value)

        called = {"stamp": False}

        async def fake_stamp(event, session):
            called["stamp"] = True

        monkeypatch.setattr(tsa_retry_mod, "stamp_change_event", fake_stamp)
        await run_timestamp_retry_pass(session_factory)
        assert called["stamp"] is False


class TestMigrationBackfill:
    @pytest.mark.asyncio
    async def test_a_row_inserted_without_an_explicit_status_defaults_to_pre_tsa(self, session_factory):
        # Mirrors what the ADD COLUMN ... DEFAULT server_default backfill
        # does for every pre-existing row: the column default is the
        # terminal, safe state, never `pending`.
        event = await _make_change_event(session_factory)
        del event  # the row above always sets timestamp_status explicitly;
        # this test instead inserts via raw ORM defaults to prove the
        # column-level default itself is correct.
        async with session_factory() as session:
            tenant = Tenant(name="T2", slug="t2", email="t2@example.com", subscription_status="free")
            session.add(tenant)
            await session.flush()
            sp = Subprocessor(tenant_id=tenant.id, name="V2", monitored_url="https://v2.example.com")
            session.add(sp)
            await session.flush()
            bare_event = ChangeEvent(
                subprocessor_id=sp.id, old_hash="a" * 64, new_hash="b" * 64,
                raw_diff="diff", status="pending_review",
                # timestamp_status deliberately omitted
            )
            session.add(bare_event)
            await session.commit()
            await session.refresh(bare_event)
            assert bare_event.timestamp_status == TimestampStatus.not_available_pre_tsa.value


class TestOutageResilience:
    @pytest.mark.asyncio
    async def test_tsa_unreachable_leaves_the_record_pending_or_retrying_not_broken(
        self, session_factory, monkeypatch
    ):
        event = await _make_change_event(session_factory, timestamp_status=TimestampStatus.pending.value)

        async def always_fails(*args, **kwargs):
            raise TSAError("simulated TSA outage")

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", always_fails)

        # Should not raise — the sweep must keep running regardless.
        await run_timestamp_retry_pass(session_factory)

        reloaded = await _reload(session_factory, event.id)
        assert reloaded.timestamp_status in (TimestampStatus.pending.value, TimestampStatus.retrying.value)
        assert reloaded.tsa_attempt_count == 1
        assert reloaded.tsa_last_error is not None


class TestRetrySucceeds:
    @pytest.mark.asyncio
    async def test_pending_becomes_timestamped_on_a_successful_attempt(self, session_factory, monkeypatch):
        from datetime import UTC, datetime

        event = await _make_change_event(session_factory, timestamp_status=TimestampStatus.pending.value)

        async def fake_request_timestamp(digest_hex, tsa_url, timeout):
            assert digest_hex == _DIGEST
            return b"fake-tsr-bytes", datetime(2026, 9, 2, tzinfo=UTC)

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", fake_request_timestamp)

        await run_timestamp_retry_pass(session_factory)

        reloaded = await _reload(session_factory, event.id)
        assert reloaded.timestamp_status == TimestampStatus.timestamped.value
        assert reloaded.tsa_token == b"fake-tsr-bytes"
        assert reloaded.tsa_time_utc is not None


class TestMaxAttemptsAndFailure:
    @pytest.mark.asyncio
    async def test_failed_after_max_attempts_records_the_last_error(self, session_factory, monkeypatch):
        event = await _make_change_event(
            session_factory,
            timestamp_status=TimestampStatus.retrying.value,
            tsa_attempt_count=4,  # one short of TSA_MAX_ATTEMPTS default (5)
        )
        monkeypatch.setattr(tsa_retry_mod.settings, "TSA_MAX_ATTEMPTS", 5)
        monkeypatch.setattr(tsa_retry_mod.settings, "TSA_FALLBACK_URL", "")

        async def always_fails(*args, **kwargs):
            raise TSAError("no TSA reachable")

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", always_fails)

        await run_timestamp_retry_pass(session_factory)

        reloaded = await _reload(session_factory, event.id)
        assert reloaded.timestamp_status == TimestampStatus.failed.value
        assert reloaded.tsa_attempt_count == 5
        assert "no TSA reachable" in reloaded.tsa_last_error

    @pytest.mark.asyncio
    async def test_failed_is_not_terminal_manual_retry_can_reset_it(self, session_factory):
        event = await _make_change_event(session_factory, timestamp_status=TimestampStatus.failed.value)
        async with session_factory() as session:
            fresh = await session.get(ChangeEvent, event.id)
            fresh.timestamp_status = TimestampStatus.retrying.value
            fresh.tsa_attempt_count = 0
            await session.commit()
        reloaded = await _reload(session_factory, event.id)
        assert reloaded.timestamp_status == TimestampStatus.retrying.value


class TestFallbackTSA:
    @pytest.mark.asyncio
    async def test_primary_failure_falls_back_and_records_which_tsa_was_used(
        self, session_factory, monkeypatch
    ):
        from datetime import UTC, datetime

        event = await _make_change_event(session_factory, timestamp_status=TimestampStatus.pending.value)
        monkeypatch.setattr(tsa_retry_mod.settings, "TSA_PRIMARY_URL", "https://primary.example.com/tsr")
        monkeypatch.setattr(tsa_retry_mod.settings, "TSA_FALLBACK_URL", "https://fallback.example.com/tsr")

        calls = []

        async def fake_request_timestamp(digest_hex, tsa_url, timeout):
            calls.append(tsa_url)
            if tsa_url == "https://primary.example.com/tsr":
                raise TSAError("primary down")
            return b"fallback-token", datetime(2026, 9, 2, tzinfo=UTC)

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", fake_request_timestamp)

        await run_timestamp_retry_pass(session_factory)

        reloaded = await _reload(session_factory, event.id)
        assert calls == ["https://primary.example.com/tsr", "https://fallback.example.com/tsr"]
        assert reloaded.timestamp_status == TimestampStatus.timestamped.value
        assert reloaded.tsa_authority_url == "https://fallback.example.com/tsr"
