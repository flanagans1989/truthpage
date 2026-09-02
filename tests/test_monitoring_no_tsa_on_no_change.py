"""PR 3 test item 7: a scan that finds no change never creates a
ChangeEvent, so it never becomes eligible for a TSA call. Needs
app.services.monitoring (pulls in HTMLNormalizer/selectolax) — like every
other such test in this repo, confirmed via CI on this branch; see the PR
description's note on this environment's local DLL-block issue.
"""
import pytest

from app.db.models.change_event import ChangeEvent, TimestampStatus
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.monitoring import run_subprocessor_check


async def _make_tenant_and_subprocessor(session_factory, last_content_hash=None, **sp_overrides):
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(
            tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com/privacy",
            last_content_hash=last_content_hash,
            **sp_overrides,
        )
        session.add(sp)
        await session.commit()
        await session.refresh(sp)
        return sp


class TestNoChangeMeansNoTSACandidate:
    @pytest.mark.asyncio
    async def test_an_unchanged_page_creates_no_change_event_and_calls_no_tsa(
        self, session_factory, monkeypatch
    ):
        import app.services.monitoring as monitoring_mod

        healthy_html = "<html><body>" + ("Our sub-processors are listed here. " * 20) + "</body></html>"
        # Pre-seed the baseline hash so this run is a genuine "no change" tick.
        from app.core.scraper.hasher import ContentHasher
        from app.core.scraper.normalizer import HTMLNormalizer

        normalized = HTMLNormalizer().normalize(healthy_html)
        baseline_hash = ContentHasher().hash(normalized)

        sp = await _make_tenant_and_subprocessor(session_factory, last_content_hash=baseline_hash)

        async def fake_fetch(*args, **kwargs):
            return healthy_html

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        tsa_called = {"n": 0}

        async def fake_request_timestamp(*args, **kwargs):
            tsa_called["n"] += 1
            raise AssertionError("TSA must never be called for a no-change scan")

        import app.core.tsa as tsa_mod
        monkeypatch.setattr(tsa_mod, "request_timestamp", fake_request_timestamp)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(ChangeEvent))
            events = list(result.scalars().all())

        assert events == []
        assert tsa_called["n"] == 0

    @pytest.mark.asyncio
    async def test_a_real_change_creates_a_pending_change_event(self, session_factory, monkeypatch):
        import app.services.monitoring as monitoring_mod

        old_html = "<html><body>" + ("Old policy text. " * 30) + "</body></html>"
        new_html = "<html><body>" + ("New policy text with a change. " * 30) + "</body></html>"
        from app.core.scraper.hasher import ContentHasher
        from app.core.scraper.normalizer import HTMLNormalizer

        old_normalized = HTMLNormalizer().normalize(old_html)
        old_hash = ContentHasher().hash(old_normalized)

        sp = await _make_tenant_and_subprocessor(
            session_factory, last_content_hash=old_hash, last_content_text=old_normalized,
        )

        async def fake_fetch(*args, **kwargs):
            return new_html

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        async def fake_analyze(diff_text):
            from app.core.llm.schemas import DiffAnalysis
            return DiffAnalysis(summary="material change", classification="MATERIAL", confidence=0.9)

        monkeypatch.setattr(monitoring_mod._llm_analyzer, "analyze", fake_analyze)

        async def noop(*args, **kwargs):
            return None

        monkeypatch.setattr(monitoring_mod.mailer, "send_review_needed", noop)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(ChangeEvent))
            events = list(result.scalars().all())

        assert len(events) == 1
        assert events[0].timestamp_status == TimestampStatus.pending.value
