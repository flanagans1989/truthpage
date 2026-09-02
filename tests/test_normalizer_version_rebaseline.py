"""Changing how we read a page must not look like the page changing.

Every stored hash was produced by whichever normalizer was current at the
time. Bumping NORMALIZER_VERSION moves the hash of every unchanged page at
once — which, without this guard, would open a review for every source,
email every tenant that a change is waiting, and auto-publish whatever the
classifier called cosmetic. Real customers would be told their vendors
changed something that never changed.
"""
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.core.scraper.normalizer import NORMALIZER_VERSION
from app.db.models.change_event import ChangeEvent
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.monitoring import run_subprocessor_check

PAGE = (
    "<body><h1>Sub-processors</h1><table>"
    "<tr><td>AWS</td><td>Hosting</td></tr>"
    "<tr><td>Stripe</td><td>Payments</td></tr>"
    "</table><p>" + ("Filler sentence for content health. " * 40) + "</p></body>"
)


@pytest_asyncio.fixture
async def source(session_factory):
    async with session_factory() as session:
        tenant = Tenant(slug="acme", name="Acme", email="a@example.com")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(
            tenant_id=tenant.id,
            name="Vendor",
            monitored_url="https://vendor.example/subprocessors",
            check_interval_minutes=1440,
            monitoring_enabled=True,
            # A hash from the previous normalizer generation.
            last_content_hash="0" * 64,
            last_content_text="AWS Hosting Stripe Payments",
            content_format_version=NORMALIZER_VERSION - 1,
            last_checked_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        session.add(sp)
        await session.commit()
        return sp.id


@pytest.mark.asyncio
async def test_version_bump_rebaselines_without_a_change_event(
    source, session_factory, monkeypatch
):
    async def _fake_fetch(*_a, **_k):
        return PAGE

    monkeypatch.setattr("app.services.monitoring.fetch_raw_html", _fake_fetch)

    async def _explode(*_a, **_k):
        raise AssertionError(
            "a normalizer version bump must never reach the classifier — "
            "that is a fabricated change event and an email to real subscribers"
        )

    monkeypatch.setattr("app.services.monitoring._llm_analyzer.analyze", _explode)

    async with session_factory() as session:
        await run_subprocessor_check(source, session)

    async with session_factory() as session:
        sp = await session.get(Subprocessor, source)
        assert sp.content_format_version == NORMALIZER_VERSION
        # Re-baselined to the current reading...
        assert sp.last_content_hash != "0" * 64
        assert "\n" in (sp.last_content_text or "")
        # ...and nothing was reported to anyone.
        events = (await session.execute(ChangeEvent.__table__.select())).all()
        assert events == []
