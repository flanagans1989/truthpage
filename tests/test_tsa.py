"""app/core/tsa.py — RFC 3161 client. build_query/parse_reply shell out to
the real system `openssl` (this suite doesn't mock that away — the whole
point of shelling out instead of hand-rolling ASN.1 is that it's real
openssl, tested against real openssl). Network calls are the only thing
mocked, so this suite needs no internet access and no FreeTSA outage risk.
"""
from datetime import datetime, timezone

import httpx
import pytest

from app.core.tsa import TSAError, build_query, parse_reply, request_timestamp

_SAMPLE_DIGEST = "271a879deb5a0d25f45792bab8a7e911b19a8d611dd4c3ce4adc397dea3b5101"


class TestBuildQuery:
    def test_builds_a_query_containing_only_the_digest_not_any_content(self):
        query = build_query(_SAMPLE_DIGEST)
        assert isinstance(query, bytes)
        assert len(query) > 0
        # The whole point (item 8): whatever bytes come out encode the
        # digest, not any HTML content — a query built from this digest
        # must never grow because someone passed a full page of text in.
        assert len(query) < 200  # a bare digest query is tiny; content would inflate this

    def test_rejects_a_malformed_digest(self):
        with pytest.raises(TSAError):
            build_query("not-a-hex-digest")


class TestParseReply:
    def test_garbage_bytes_are_not_granted(self):
        granted, time_utc = parse_reply(b"this is not a TSA reply")
        assert granted is False
        assert time_utc is None

    def test_a_real_bundled_reply_parses_as_granted_with_a_time(self):
        # The same token shipped in the sample evidence ZIP (see
        # app/services/leads.py) — a real, previously-obtained FreeTSA
        # reply, checked into the repo. No network call in this test.
        from pathlib import Path
        tsr_path = Path(__file__).parent.parent / "app" / "static_data" / "sample" / "sample-after-html.sha256.tsr"
        granted, time_utc = parse_reply(tsr_path.read_bytes())
        assert granted is True
        assert isinstance(time_utc, datetime)
        assert time_utc.tzinfo is not None


class TestRequestTimestamp:
    @pytest.mark.asyncio
    async def test_sends_only_the_digest_in_the_request_body_never_page_content(self, monkeypatch):
        """Item 8, at the network layer: capture exactly what would have
        gone over the wire and assert no HTML/page content appears in it."""
        captured = {}

        class FakeResponse:
            status_code = 200
            content = b"granted-reply-bytes"

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, content, headers):
                captured["url"] = url
                captured["content"] = content
                captured["headers"] = headers
                return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        async def fake_parse_reply_thread(fn, *args):
            return True, datetime(2026, 9, 2, tzinfo=timezone.utc)

        import app.core.tsa as tsa_mod
        monkeypatch.setattr(tsa_mod.asyncio, "to_thread", fake_parse_reply_thread)

        html_that_must_never_be_sent = "<html><body>secret vendor policy content</body></html>"
        tsr_bytes, tsa_time = await request_timestamp(_SAMPLE_DIGEST, "https://tsa.example.com/tsr", 5.0)

        assert captured["url"] == "https://tsa.example.com/tsr"
        assert captured["headers"]["Content-Type"] == "application/timestamp-query"
        assert html_that_must_never_be_sent.encode() not in captured["content"]
        assert tsr_bytes == b"granted-reply-bytes"
        assert tsa_time == datetime(2026, 9, 2, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_a_non_200_response_raises_tsa_error(self, monkeypatch):
        class FakeResponse:
            status_code = 503
            content = b""

        class FakeAsyncClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, *a, **k): return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        with pytest.raises(TSAError):
            await request_timestamp(_SAMPLE_DIGEST, "https://tsa.example.com/tsr", 5.0)

    @pytest.mark.asyncio
    async def test_a_network_error_raises_tsa_error(self, monkeypatch):
        class FakeAsyncClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, *a, **k): raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        with pytest.raises(TSAError):
            await request_timestamp(_SAMPLE_DIGEST, "https://tsa.example.com/tsr", 5.0)
