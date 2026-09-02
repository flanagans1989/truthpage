"""Item 2: a change landing in the tenant's own approval queue must always
produce a tenant-facing notification — otherwise a pending_review record
sits invisible until someone happens to open the dashboard. This already
existed before this PR (mailer.send_review_needed, called from
monitoring.py whenever a change is NOT auto-published) and was untouched
by removing the old subscriber-facing "change detected" email — this test
makes that guarantee explicit rather than only implicit in other tests'
mocking of it as a no-op.
"""
import pytest

from app.db.models.change_event import ChangeEvent
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.core.scraper.normalizer import NORMALIZER_VERSION
from app.services.monitoring import run_subprocessor_check


async def _make_tenant_and_subprocessor(session_factory, last_content_hash=None):
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(
            tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com/privacy",
            last_content_hash=last_content_hash,
            # An existing hash implies it was produced by the CURRENT
            # normalizer; leaving this at the default would send the
            # source down the silent re-baseline path instead
            # (app/services/monitoring.py, migration 0021).
            content_format_version=NORMALIZER_VERSION,
        )
        session.add(sp)
        await session.commit()
        await session.refresh(sp)
        return sp


class TestPendingReviewAlwaysNotifiesTheTenant:
    @pytest.mark.asyncio
    async def test_a_material_change_calls_send_review_needed(self, session_factory, monkeypatch):
        import app.services.monitoring as monitoring_mod
        from app.core.scraper.hasher import ContentHasher
        from app.core.scraper.normalizer import HTMLNormalizer

        old_html = "<html><body>" + ("Old policy text. " * 30) + "</body></html>"
        new_html = "<html><body>" + ("New policy text with a real change. " * 30) + "</body></html>"
        old_normalized = HTMLNormalizer().normalize(old_html)
        old_hash = ContentHasher().hash(old_normalized)

        sp = await _make_tenant_and_subprocessor(session_factory, last_content_hash=old_hash)
        async with session_factory() as session:
            sp_reload = await session.get(Subprocessor, sp.id)
            sp_reload.last_content_text = old_normalized
            await session.commit()

        async def fake_fetch(*args, **kwargs):
            return new_html

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        async def fake_analyze(diff_text):
            from app.core.llm.schemas import DiffAnalysis
            return DiffAnalysis(summary="material change", classification="MATERIAL", confidence=0.9)

        monkeypatch.setattr(monitoring_mod._llm_analyzer, "analyze", fake_analyze)

        calls = []

        async def spy_review_needed(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(monitoring_mod.mailer, "send_review_needed", spy_review_needed)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)

        assert len(calls) == 1
        assert calls[0]["email"] == "owner@acme.com"
        assert calls[0]["subprocessor_name"] == "Vendor"

    @pytest.mark.asyncio
    async def test_a_cosmetic_auto_published_change_does_not_call_it(self, session_factory, monkeypatch):
        import app.services.monitoring as monitoring_mod
        from app.core.scraper.hasher import ContentHasher
        from app.core.scraper.normalizer import HTMLNormalizer

        old_html = "<html><body>" + ("Old policy text. " * 30) + "</body></html>"
        new_html = "<html><body>" + ("Old policy text, with a typo fixed. " * 30) + "</body></html>"
        old_normalized = HTMLNormalizer().normalize(old_html)
        old_hash = ContentHasher().hash(old_normalized)

        sp = await _make_tenant_and_subprocessor(session_factory, last_content_hash=old_hash)
        async with session_factory() as session:
            sp_reload = await session.get(Subprocessor, sp.id)
            sp_reload.last_content_text = old_normalized
            await session.commit()

        async def fake_fetch(*args, **kwargs):
            return new_html

        monkeypatch.setattr(monitoring_mod, "fetch_raw_html", fake_fetch)

        async def fake_analyze(diff_text):
            from app.core.llm.schemas import DiffAnalysis
            return DiffAnalysis(summary="cosmetic fix", classification="COSMETIC", confidence=0.99)

        monkeypatch.setattr(monitoring_mod._llm_analyzer, "analyze", fake_analyze)

        async def fail_if_called(**kwargs):
            raise AssertionError("send_review_needed must never fire for an auto-published cosmetic change")

        monkeypatch.setattr(monitoring_mod.mailer, "send_review_needed", fail_if_called)

        async with session_factory() as session:
            await run_subprocessor_check(sp.id, session)  # must not raise
