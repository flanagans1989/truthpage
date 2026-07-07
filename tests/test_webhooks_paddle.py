import hashlib
import hmac
import time

from app.routers.webhooks import _SUBSCRIPTION_STATUS_MAP, _verify_signature

_SECRET = "test-webhook-secret"


def _sign(payload: bytes, ts: str | None = None) -> str:
    ts = ts if ts is not None else str(int(time.time()))
    signed_payload = f"{ts}:{payload.decode('utf-8')}".encode("utf-8")
    h1 = hmac.new(_SECRET.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def test_verify_signature_accepts_valid_signature():
    payload = b'{"event_type": "subscription.updated"}'
    header = _sign(payload)
    assert _verify_signature(payload, header, _SECRET) is True


def test_verify_signature_rejects_tampered_payload():
    payload = b'{"event_type": "subscription.updated"}'
    header = _sign(payload)
    assert _verify_signature(b'{"event_type": "subscription.canceled"}', header, _SECRET) is False


def test_verify_signature_rejects_wrong_secret():
    payload = b'{"event_type": "subscription.updated"}'
    header = _sign(payload)
    assert _verify_signature(payload, header, "wrong-secret") is False


def test_verify_signature_rejects_malformed_header():
    payload = b'{"event_type": "subscription.updated"}'
    assert _verify_signature(payload, "not-a-valid-header", _SECRET) is False
    assert _verify_signature(payload, "", _SECRET) is False


def test_verify_signature_rejects_stale_timestamp():
    payload = b'{"event_type": "transaction.completed"}'
    stale = str(int(time.time()) - 3600)
    header = _sign(payload, ts=stale)
    assert _verify_signature(payload, header, _SECRET) is False


def test_verify_signature_rejects_non_numeric_timestamp():
    payload = b'{"event_type": "subscription.updated"}'
    header = _sign(payload, ts="not-a-number")
    assert _verify_signature(payload, header, _SECRET) is False


def test_verify_signature_rejects_invalid_utf8_payload():
    payload = b"\xff\xfe invalid"
    header = f"ts={int(time.time())};h1=deadbeef"
    assert _verify_signature(payload, header, _SECRET) is False


def test_subscription_status_map_known_values():
    assert _SUBSCRIPTION_STATUS_MAP["active"] == "active"
    assert _SUBSCRIPTION_STATUS_MAP["trialing"] == "trialing"
    assert _SUBSCRIPTION_STATUS_MAP["past_due"] == "past_due"
    assert _SUBSCRIPTION_STATUS_MAP["paused"] == "canceled"
    assert _SUBSCRIPTION_STATUS_MAP["canceled"] == "canceled"


def test_subscription_status_map_unknown_falls_back_to_past_due():
    assert _SUBSCRIPTION_STATUS_MAP.get("some_future_status", "past_due") == "past_due"
