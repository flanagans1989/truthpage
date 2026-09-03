"""The public directory used a weaker gate than the tenant pipeline.

monitoring.py refuses to store a snapshot unless content_health_issue()
says the page is real. directory.py — which drives the PUBLIC vendor
directory, the pages carrying other companies' names — only checked
whether the normalized text was completely empty. A Cloudflare or
Turnstile interstitial is a few hundred characters, not zero, so it passed:
hashed as content, published as a real change, and its "sub-processor
list" re-extracted from the challenge page.
"""
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.core.scraper.content_health import content_health_issue, is_bot_wall_body
from app.db.models.vendor import Vendor
from app.services.directory import run_vendor_check

CHALLENGE_PAGE = (
    "<html><head><title>Just a moment...</title></head><body>"
    "<div>Checking your browser before accessing the site.</div>"
    "<div>Enable JavaScript and cookies to continue</div>"
    "</body></html>"
)


def test_the_interstitial_this_regression_is_about_is_actually_detected():
    assert is_bot_wall_body(CHALLENGE_PAGE) is True
    # And, crucially, it is NOT empty — which is why the old
    # `if not canonical_text` check waved it through.
    from app.core.scraper.normalizer import HTMLNormalizer

    normalized = HTMLNormalizer().normalize(CHALLENGE_PAGE)
    assert normalized.strip() != ""
    assert content_health_issue(CHALLENGE_PAGE, normalized) == "bot_wall"


@pytest_asyncio.fixture
async def vendor(session_factory):
    async with session_factory() as session:
        row = Vendor(
            slug="acme",
            name="Acme",
            monitored_url="https://acme.example/subprocessors",
            check_interval_minutes=1440,
            last_content_hash="a" * 64,
            last_content_text="Acme uses AWS and Stripe as sub-processors. " * 40,
            entries=[{"name": "AWS"}, {"name": "Stripe"}],
            is_published=True,
            last_checked_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        session.add(row)
        await session.commit()
        return row.id


@pytest.mark.asyncio
async def test_bot_wall_never_becomes_a_published_directory_change(
    vendor, session_factory, monkeypatch
):
    async def _fake_fetch(*_args, **_kwargs):
        return CHALLENGE_PAGE

    monkeypatch.setattr("app.services.directory.fetch_raw_html", _fake_fetch)

    async def _explode(*_args, **_kwargs):
        raise AssertionError("a challenge page must never reach the LLM extractor")

    monkeypatch.setattr("app.services.directory._extractor.extract", _explode)
    monkeypatch.setattr("app.services.directory._analyzer.analyze", _explode)

    async with session_factory() as session:
        await run_vendor_check(vendor, session)

    async with session_factory() as session:
        row = await session.get(Vendor, vendor)
        # The published list is untouched, and the hash still points at the
        # last genuine capture — a bot wall is a failed check, not a change.
        assert row.last_content_hash == "a" * 64
        assert row.entries == [{"name": "AWS"}, {"name": "Stripe"}]
        # It is also not silently counted as "checked": last_checked_at is
        # left where it was so the staleness alarm can still fire.
        assert row.last_checked_at == datetime(2026, 9, 1, tzinfo=UTC).replace(tzinfo=None)
