"""Redirects are the SSRF hole that a one-time URL check cannot close.

Until 2026-09-02 the guard ran once, when a URL was first submitted, and
httpx was then told to follow redirects. A validated, genuinely public page
could therefore 302 to 127.0.0.1 or 169.254.169.254 and be fetched, with
the guard none the wiser — and the public audit-grader tool made that
reachable with no account at all.
"""
import httpx
import pytest

from app.core.scraper import fetcher
from app.core.urlguard import UnsafeUrlError

# Raw public IP: exercises the real guard without needing DNS in the
# sandbox the tests run in.
PUBLIC = "http://93.184.216.34/subprocessors"


def _client_factory(monkeypatch, handler):
    """Force every AsyncClient built inside the fetcher onto a mock transport."""
    real = httpx.AsyncClient

    def _build(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", _build)


@pytest.mark.asyncio
async def test_redirect_to_loopback_is_refused(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/admin"})
        raise AssertionError(f"guard let the request through to {request.url}")

    _client_factory(monkeypatch, handler)

    with pytest.raises(UnsafeUrlError):
        await fetcher._fetch_tier1(PUBLIC)


@pytest.mark.asyncio
async def test_redirect_to_cloud_metadata_is_refused(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.216.34":
            return httpx.Response(
                301, headers={"location": "http://169.254.169.254/latest/meta-data/"}
            )
        raise AssertionError(f"guard let the request through to {request.url}")

    _client_factory(monkeypatch, handler)

    with pytest.raises(UnsafeUrlError):
        await fetcher._fetch_tier1(PUBLIC)


@pytest.mark.asyncio
async def test_ordinary_public_redirect_is_still_followed(monkeypatch):
    """The guard must not break http→https or trailing-slash redirects,
    which is what nearly every real vendor page does."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subprocessors":
            return httpx.Response(301, headers={"location": "/legal/subprocessors"})
        return httpx.Response(200, text="<html><body>real policy</body></html>")

    _client_factory(monkeypatch, handler)

    html, blocked = await fetcher._fetch_tier1(PUBLIC)
    assert "real policy" in html
    assert blocked is False


@pytest.mark.asyncio
async def test_relative_redirect_resolves_against_the_hop_it_came_from(monkeypatch):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if len(seen) == 1:
            return httpx.Response(302, headers={"location": "../legal/list"})
        return httpx.Response(200, text="<html>ok</html>")

    _client_factory(monkeypatch, handler)

    await fetcher._fetch_tier1(PUBLIC)
    assert seen[1] == "http://93.184.216.34/legal/list"


@pytest.mark.asyncio
async def test_redirect_loop_is_capped(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/round-and-round"})

    _client_factory(monkeypatch, handler)

    with pytest.raises(httpx.TooManyRedirects):
        await fetcher._fetch_tier1(PUBLIC)


@pytest.mark.asyncio
async def test_initial_url_is_validated_before_any_request(monkeypatch):
    """Re-validated on EVERY fetch, not just at submission — a hostname
    repointed at an internal address after signup must stop being fetched
    the next time the sweep comes round (DNS rebinding with no time
    pressure)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"request should never have been made: {request.url}")

    _client_factory(monkeypatch, handler)

    with pytest.raises(UnsafeUrlError):
        await fetcher._fetch_tier1("http://169.254.169.254/latest/meta-data/")
