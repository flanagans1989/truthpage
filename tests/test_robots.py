"""We crawl the public directory on nobody's instruction but our own.

Selling compliance while ignoring the web's one machine-readable "please
don't" is not a position that survives a competitor pointing at it. The
tenant pipeline is deliberately out of scope: those URLs are fetched on a
customer's instruction under the Terms, and silently refusing to monitor a
page someone pays us to monitor would be the same silent failure this
codebase keeps closing.
"""
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio

from app.core.config import settings
from app.core.scraper import robots
from app.db.models.vendor import Vendor
from app.services.directory import run_vendor_check


@pytest.fixture(autouse=True)
def _clear_cache():
    robots._CACHE.clear()
    yield
    robots._CACHE.clear()


def _transport(monkeypatch, handler):
    real = httpx.AsyncClient

    def _build(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(robots.httpx, "AsyncClient", _build)


@pytest.mark.asyncio
async def test_a_disallowed_path_is_refused(monkeypatch):
    def handler(request):
        return httpx.Response(200, text="User-agent: TrustPagesBot\nDisallow: /legal/\n")

    _transport(monkeypatch, handler)
    assert await robots.is_allowed("https://vendor.example/legal/subprocessors") is False
    assert await robots.is_allowed("https://vendor.example/about") is True


@pytest.mark.asyncio
async def test_a_wildcard_disallow_applies_to_us_too(monkeypatch):
    def handler(request):
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    _transport(monkeypatch, handler)
    assert await robots.is_allowed("https://vendor.example/anything") is False


@pytest.mark.asyncio
async def test_a_rule_naming_us_specifically_can_allow_what_the_wildcard_refuses(monkeypatch):
    """Asking as TrustPagesBot is the point: a site owner can say yes to us
    in particular."""

    def handler(request):
        return httpx.Response(
            200,
            text="User-agent: *\nDisallow: /\n\nUser-agent: TrustPagesBot\nAllow: /legal/\nDisallow: /\n",
        )

    _transport(monkeypatch, handler)
    assert await robots.is_allowed("https://vendor.example/legal/subprocessors") is True


@pytest.mark.asyncio
async def test_missing_robots_txt_allows_everything(monkeypatch):
    def handler(request):
        return httpx.Response(404)

    _transport(monkeypatch, handler)
    assert await robots.is_allowed("https://vendor.example/legal/subprocessors") is True


@pytest.mark.asyncio
async def test_an_unreachable_robots_txt_does_not_silently_stop_monitoring(monkeypatch):
    """Allow-on-error, against the conservative reading of RFC 9309. A
    minute of 5xx must not become a monitored page that quietly stops being
    read — that is the exact failure mode this codebase keeps closing."""

    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    _transport(monkeypatch, handler)
    assert await robots.is_allowed("https://vendor.example/legal/subprocessors") is True

    def five_hundred(request):
        return httpx.Response(503)

    robots._CACHE.clear()
    _transport(monkeypatch, five_hundred)
    assert await robots.is_allowed("https://vendor.example/legal/subprocessors") is True


@pytest.mark.asyncio
async def test_robots_txt_is_fetched_once_per_host(monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")

    _transport(monkeypatch, handler)
    await robots.is_allowed("https://vendor.example/a")
    await robots.is_allowed("https://vendor.example/b")
    assert len(calls) == 1


@pytest_asyncio.fixture
async def vendor(session_factory):
    async with session_factory() as session:
        row = Vendor(
            slug="acme",
            name="Acme",
            monitored_url="https://acme.example/subprocessors",
            check_interval_minutes=1440,
            entries=[{"name": "AWS"}],
            is_published=True,
            last_checked_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        session.add(row)
        await session.commit()
        return row.id


@pytest.mark.asyncio
async def test_a_refusing_vendor_is_unpublished_rather_than_left_to_go_stale(
    vendor, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "RESPECT_ROBOTS_TXT", True)

    def handler(request):
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    _transport(monkeypatch, handler)

    async def _never(*_a, **_k):
        raise AssertionError("we must not fetch a page robots.txt refuses")

    monkeypatch.setattr("app.services.directory.fetch_raw_html", _never)

    async with session_factory() as session:
        await run_vendor_check(vendor, session)

    async with session_factory() as session:
        row = await session.get(Vendor, vendor)
        assert row.robots_blocked is True
        assert row.is_published is False
