"""Tier-1 must recognize a PDF response and read real text off it instead
of handing back raw bytes as "html" — see app/core/scraper/pdf_extract.py
and its 2026-09-06 note in vendor_seeds.py."""
import httpx
import pytest

from app.core.scraper import fetcher
from tests._pdf_fixtures import build_pdf

PUBLIC = "http://93.184.216.34/subprocessors.pdf"


def _client_factory(monkeypatch, handler):
    real = httpx.AsyncClient

    def _build(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", _build)


@pytest.mark.asyncio
async def test_a_pdf_content_type_is_extracted_not_returned_as_raw_bytes(monkeypatch):
    pdf = build_pdf("Amazon Web Services - hosting", "Twilio, Inc. - SMS")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})

    _client_factory(monkeypatch, handler)

    html, blocked = await fetcher._fetch_tier1(PUBLIC)
    assert blocked is False
    assert "Amazon Web Services - hosting" in html
    assert "Twilio, Inc. - SMS" in html
    assert "<p>" in html  # wrapped for the normalizer, not the raw PDF bytes


@pytest.mark.asyncio
async def test_a_pdf_reached_through_a_redirect_is_still_extracted(monkeypatch):
    """Slack's own subprocessors URL 301s to a Salesforce-hosted PDF — the
    real case this exists for."""
    pdf = build_pdf("Slack (Salesforce) - infra")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subprocessors.pdf":
            return httpx.Response(301, headers={"location": "/real-list.pdf"})
        return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})

    _client_factory(monkeypatch, handler)

    html, blocked = await fetcher._fetch_tier1(PUBLIC)
    assert blocked is False
    assert "Slack (Salesforce) - infra" in html


@pytest.mark.asyncio
async def test_a_404_on_a_pdf_url_still_raises_instead_of_extracting(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found", headers={"content-type": "text/plain"})

    _client_factory(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await fetcher._fetch_tier1(PUBLIC)


@pytest.mark.asyncio
async def test_a_mislabeled_pdf_is_still_caught_by_the_url_suffix(monkeypatch):
    """Seen in the wild: a compliance CDN serving a PDF as
    application/octet-stream."""
    pdf = build_pdf("Datadog, Inc. - monitoring")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pdf, headers={"content-type": "application/octet-stream"})

    _client_factory(monkeypatch, handler)

    html, blocked = await fetcher._fetch_tier1(PUBLIC)
    assert "Datadog, Inc. - monitoring" in html
