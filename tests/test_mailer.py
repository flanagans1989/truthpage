"""app/services/mailer.py — the Resend send call itself. Two things this
PR must get right forever: no per-request payload ever includes a
tracking-enabling key (open/click tracking is a domain-level Resend setting,
off by default and never turned on for our domain — see
docs/manifest_v2.md), and send_notice returns a Resend message id per
recipient so the caller can persist a NotificationRecipient row.
"""
import json

import httpx
import pytest

from app.services.mailer import MailerService

_TRACKING_KEYS = {"tags", "tracking", "open_tracking", "click_tracking"}


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_body: dict | None = None):
        self.status_code = status_code
        self._json = json_body or {"id": "msg-123"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Captures every POST body so tests can assert on it, without a real
    network call. Mirrors the tiny subset of httpx.AsyncClient this
    codebase actually uses (async context manager + .post)."""
    calls: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, *, headers=None, json=None):
        type(self).calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse()


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    _FakeAsyncClient.calls = []
    monkeypatch.setattr("app.services.mailer.httpx.AsyncClient", _FakeAsyncClient)
    yield


class TestNoTrackingEver:
    @pytest.mark.asyncio
    async def test_send_tracked_payload_has_no_tracking_key(self):
        mailer = MailerService()
        await mailer._send_tracked(to="a@example.com", subject="Hi", html="<p>hi</p>")
        payload = _FakeAsyncClient.calls[0]["json"]
        assert _TRACKING_KEYS.isdisjoint(payload.keys())

    @pytest.mark.asyncio
    async def test_send_notice_payload_has_no_tracking_key(self):
        mailer = MailerService()
        await mailer.send_notice(
            recipients=[("a@example.com", "https://app/unsub")],
            tenant_name="Acme",
            reply_to="owner@acme.com",
            subject="Notice",
            body="Body text",
        )
        payload = _FakeAsyncClient.calls[0]["json"]
        assert _TRACKING_KEYS.isdisjoint(payload.keys())


class TestSendNotice:
    @pytest.mark.asyncio
    async def test_returns_resend_message_id_per_recipient(self):
        mailer = MailerService()
        results = await mailer.send_notice(
            recipients=[("a@example.com", "u1"), ("b@example.com", "u2")],
            tenant_name="Acme",
            reply_to="owner@acme.com",
            subject="Notice",
            body="Body",
        )
        assert {r["email"] for r in results} == {"a@example.com", "b@example.com"}
        assert all(r["resend_message_id"] == "msg-123" and r["error"] is None for r in results)

    @pytest.mark.asyncio
    async def test_reply_to_and_from_name_carry_the_tenant(self):
        mailer = MailerService()
        await mailer.send_notice(
            recipients=[("a@example.com", "u1")],
            tenant_name="Acme Inc",
            reply_to="owner@acme.com",
            subject="Notice",
            body="Body",
        )
        payload = _FakeAsyncClient.calls[0]["json"]
        assert payload["reply_to"] == "owner@acme.com"
        assert "Acme Inc" in payload["from"]

    @pytest.mark.asyncio
    async def test_one_recipient_failing_does_not_stop_the_others(self, monkeypatch):
        calls = {"n": 0}

        class _FlakyClient(_FakeAsyncClient):
            async def post(self, url, *, headers=None, json=None):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise httpx.ConnectError("boom")
                return await super().post(url, headers=headers, json=json)

        monkeypatch.setattr("app.services.mailer.httpx.AsyncClient", _FlakyClient)
        mailer = MailerService()
        results = await mailer.send_notice(
            recipients=[("a@example.com", "u1"), ("b@example.com", "u2")],
            tenant_name="Acme",
            reply_to="owner@acme.com",
            subject="Notice",
            body="Body",
        )
        by_email = {r["email"]: r for r in results}
        assert by_email["a@example.com"]["error"] is not None
        assert by_email["a@example.com"]["resend_message_id"] is None
        assert by_email["b@example.com"]["error"] is None
        assert by_email["b@example.com"]["resend_message_id"] == "msg-123"
