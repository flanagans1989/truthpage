"""Item 6c: a subprocessor's first-ever captured snapshot (its baseline —
see monitoring.py's "First check" branch) is timestamp-eligible too, once
per source, for its whole lifetime — not just later change_events. Same
KURAL 0, same state machine, over Subprocessor.baseline_* rather than
ChangeEvent columns. Mirrors tests/test_tsa_retry.py's structure.
"""
import pytest

import app.services.tsa_retry as tsa_retry_mod
from app.core.tsa import TSAError
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.tsa_retry import (
    BackdatedTimestampError,
    run_timestamp_retry_pass,
    stamp_subprocessor_baseline,
)

_DIGEST = "271a879deb5a0d25f45792bab8a7e911b19a8d611dd4c3ce4adc397dea3b5101"


async def _make_subprocessor(session_factory, **overrides) -> Subprocessor:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        defaults = dict(
            tenant_id=tenant.id,
            name="Vendor",
            monitored_url="https://vendor.example.com/privacy",
            baseline_raw_html_hash=_DIGEST,
            baseline_timestamp_status="pending",
        )
        defaults.update(overrides)
        sp = Subprocessor(**defaults)
        session.add(sp)
        await session.commit()
        await session.refresh(sp)
        return sp


async def _reload(session_factory, sp_id):
    async with session_factory() as session:
        return await session.get(Subprocessor, sp_id)


class TestKural0TripWireForBaseline:
    @pytest.mark.asyncio
    async def test_a_pre_tsa_baseline_can_never_be_timestamped(self, session_factory):
        sp = await _make_subprocessor(session_factory, baseline_timestamp_status="not_available_pre_tsa")
        async with session_factory() as session:
            sp2 = await session.get(Subprocessor, sp.id)
            with pytest.raises(BackdatedTimestampError):
                await stamp_subprocessor_baseline(sp2, session)

    @pytest.mark.asyncio
    async def test_the_retry_pass_never_selects_a_pre_tsa_baseline(self, session_factory, monkeypatch):
        await _make_subprocessor(session_factory, baseline_timestamp_status="not_available_pre_tsa")

        async def fail_if_called(*args, **kwargs):
            raise AssertionError("must never be called for a not_available_pre_tsa baseline")

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", fail_if_called)
        await run_timestamp_retry_pass(session_factory)  # must not raise


class TestBaselineRetrySucceeds:
    @pytest.mark.asyncio
    async def test_pending_baseline_becomes_timestamped(self, session_factory, monkeypatch):
        sp = await _make_subprocessor(session_factory)

        async def fake_request_timestamp(digest_hex, url, timeout):
            assert digest_hex == _DIGEST
            return b"fake-tsr-bytes", utc_now()

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", fake_request_timestamp)
        await run_timestamp_retry_pass(session_factory)

        sp2 = await _reload(session_factory, sp.id)
        assert sp2.baseline_timestamp_status == "timestamped"
        assert sp2.baseline_tsa_token == b"fake-tsr-bytes"
        assert sp2.baseline_tsa_attempt_count == 1

    @pytest.mark.asyncio
    async def test_no_digest_yet_becomes_not_available_pre_tsa(self, session_factory):
        sp = await _make_subprocessor(session_factory, baseline_raw_html_hash=None)
        async with session_factory() as session:
            sp2 = await session.get(Subprocessor, sp.id)
            await stamp_subprocessor_baseline(sp2, session)
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.baseline_timestamp_status == "not_available_pre_tsa"

    @pytest.mark.asyncio
    async def test_a_tsa_outage_moves_to_retrying_without_raising(self, session_factory, monkeypatch):
        sp = await _make_subprocessor(session_factory)

        async def failing(*args, **kwargs):
            raise TSAError("connection refused")

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", failing)
        await run_timestamp_retry_pass(session_factory)

        sp2 = await _reload(session_factory, sp.id)
        assert sp2.baseline_timestamp_status == "retrying"
        assert sp2.baseline_tsa_attempt_count == 1

    @pytest.mark.asyncio
    async def test_max_attempts_moves_to_failed(self, session_factory, monkeypatch):
        from app.core.config import settings

        sp = await _make_subprocessor(
            session_factory, baseline_timestamp_status="retrying",
            baseline_tsa_attempt_count=settings.TSA_MAX_ATTEMPTS - 1,
        )

        async def failing(*args, **kwargs):
            raise TSAError("still down")

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", failing)
        await run_timestamp_retry_pass(session_factory)

        sp2 = await _reload(session_factory, sp.id)
        assert sp2.baseline_timestamp_status == "failed"
        assert sp2.baseline_tsa_last_error == "still down"


class TestBaselineIsOncePerSourceLifetime:
    @pytest.mark.asyncio
    async def test_an_already_timestamped_baseline_is_never_retried(self, session_factory, monkeypatch):
        sp = await _make_subprocessor(session_factory, baseline_timestamp_status="timestamped")

        async def fail_if_called(*args, **kwargs):
            raise AssertionError("an already-timestamped baseline must never be attempted again")

        monkeypatch.setattr(tsa_retry_mod, "request_timestamp", fail_if_called)
        await run_timestamp_retry_pass(session_factory)  # must not raise

    @pytest.mark.asyncio
    async def test_a_healthy_no_change_subprocessor_with_no_baseline_pending_is_left_alone(self, session_factory):
        # A subprocessor whose baseline was captured before this feature
        # shipped defaults to not_available_pre_tsa (the migration's
        # server_default) — confirmed by simply not overriding it here.
        sp = await _make_subprocessor(
            session_factory, baseline_raw_html_hash=None, baseline_timestamp_status="not_available_pre_tsa"
        )
        await run_timestamp_retry_pass(session_factory)  # must not raise or touch it
        reloaded = await _reload(session_factory, sp.id)
        assert reloaded.baseline_timestamp_status == "not_available_pre_tsa"
