"""app/routers/webhooks.py's Resend delivery webhook — signature
verification (Svix scheme) and the append-only, deduplicated event log.
Tests the handler function directly against the throwaway SQLite database,
the same way test_webhooks_paddle.py tests _verify_signature directly —
no HTTP layer, no app.main import needed.
"""
import base64
import hashlib
import hmac
import time

import pytest

from app.db.models.change_event import ChangeEvent
from app.db.models.notification import NotificationDeliveryEvent, NotificationRecipient
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.routers.webhooks import (
    _handle_resend_delivery_event,
    _parse_resend_timestamp,
    _verify_resend_signature,
)

_SECRET_RAW = b"0123456789abcdef0123456789abcdef"
_SECRET = "whsec_" + base64.b64encode(_SECRET_RAW).decode()


def _sign(payload: bytes, svix_id: str = "msg_1", ts: str | None = None) -> tuple[str, str, str]:
    ts = ts if ts is not None else str(int(time.time()))
    signed_content = f"{svix_id}.{ts}.".encode("utf-8") + payload
    sig = base64.b64encode(hmac.new(_SECRET_RAW, signed_content, hashlib.sha256).digest()).decode()
    return svix_id, ts, f"v1,{sig}"


class TestVerifyResendSignature:
    def test_accepts_a_valid_signature(self):
        payload = b'{"type": "email.delivered"}'
        svix_id, ts, sig = _sign(payload)
        assert _verify_resend_signature(payload, svix_id, ts, sig, _SECRET) is True

    def test_rejects_a_tampered_payload(self):
        payload = b'{"type": "email.delivered"}'
        svix_id, ts, sig = _sign(payload)
        assert _verify_resend_signature(b'{"type": "email.bounced"}', svix_id, ts, sig, _SECRET) is False

    def test_rejects_wrong_secret(self):
        payload = b'{"type": "email.delivered"}'
        svix_id, ts, sig = _sign(payload)
        other_secret = "whsec_" + base64.b64encode(b"f" * 32).decode()
        assert _verify_resend_signature(payload, svix_id, ts, sig, other_secret) is False

    def test_rejects_missing_headers(self):
        assert _verify_resend_signature(b"{}", "", "123", "v1,x", _SECRET) is False
        assert _verify_resend_signature(b"{}", "id", "", "v1,x", _SECRET) is False
        assert _verify_resend_signature(b"{}", "id", "123", "", _SECRET) is False

    def test_rejects_stale_timestamp(self):
        payload = b'{"type": "email.delivered"}'
        stale = str(int(time.time()) - 3600)
        svix_id, ts, sig = _sign(payload, ts=stale)
        assert _verify_resend_signature(payload, svix_id, ts, sig, _SECRET) is False

    def test_accepts_one_of_several_space_separated_signatures(self):
        payload = b'{"type": "email.delivered"}'
        svix_id, ts, sig = _sign(payload)
        combined = f"v1,not-the-right-one {sig}"
        assert _verify_resend_signature(payload, svix_id, ts, combined, _SECRET) is True


class TestParseResendTimestamp:
    def test_parses_a_z_suffixed_iso_timestamp(self):
        result = _parse_resend_timestamp("2026-02-22T23:41:12.126Z")
        assert result is not None
        assert result.year == 2026 and result.month == 2

    def test_none_for_missing_or_malformed(self):
        assert _parse_resend_timestamp(None) is None
        assert _parse_resend_timestamp("not-a-date") is None


async def _make_recipient(session_factory, message_id: str = "email-abc") -> tuple:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com")
        session.add(sp)
        await session.flush()
        event = ChangeEvent(subprocessor_id=sp.id, old_hash="a" * 64, new_hash="b" * 64, raw_diff="d")
        session.add(event)
        await session.flush()
        recipient = NotificationRecipient(
            change_event_id=event.id, recipient_email="sub@example.com", resend_message_id=message_id
        )
        session.add(recipient)
        await session.commit()
        return recipient.id, event.id


class TestHandleResendDeliveryEvent:
    @pytest.mark.asyncio
    async def test_delivered_event_creates_a_log_row(self, session_factory):
        recipient_id, _ = await _make_recipient(session_factory)
        payload = {
            "type": "email.delivered",
            "created_at": "2026-09-02T10:00:00.000Z",
            "data": {"email_id": "email-abc"},
        }
        async with session_factory() as session:
            await _handle_resend_delivery_event(payload, "svix-evt-1", session)

        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(NotificationDeliveryEvent).where(NotificationDeliveryEvent.recipient_id == recipient_id)
            )
            rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].event_type == "delivered"
        assert rows[0].webhook_event_id == "svix-evt-1"

    @pytest.mark.asyncio
    async def test_same_webhook_event_id_is_never_inserted_twice(self, session_factory):
        await _make_recipient(session_factory)
        payload = {"type": "email.bounced", "created_at": "2026-09-02T10:00:00.000Z", "data": {"email_id": "email-abc"}}

        async with session_factory() as session:
            await _handle_resend_delivery_event(payload, "svix-evt-dup", session)
        async with session_factory() as session:
            await _handle_resend_delivery_event(payload, "svix-evt-dup", session)  # retried by Resend

        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(select(NotificationDeliveryEvent))
            rows = result.scalars().all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_unrecognized_type_is_ignored_not_an_error(self, session_factory):
        await _make_recipient(session_factory)
        payload = {"type": "email.opened", "created_at": "2026-09-02T10:00:00.000Z", "data": {"email_id": "email-abc"}}
        async with session_factory() as session:
            await _handle_resend_delivery_event(payload, "svix-evt-2", session)  # must not raise

        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(select(NotificationDeliveryEvent))
            assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_unknown_email_id_is_ignored_not_an_error(self, session_factory):
        await _make_recipient(session_factory)
        payload = {"type": "email.delivered", "created_at": "2026-09-02T10:00:00.000Z", "data": {"email_id": "no-such-id"}}
        async with session_factory() as session:
            await _handle_resend_delivery_event(payload, "svix-evt-3", session)  # must not raise
