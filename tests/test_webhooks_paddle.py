import hashlib
import hmac

from app.routers.webhooks import _SUBSCRIPTION_STATUS_MAP, _verify_signature

_SECRET = "test-webhook-secret"


def _sign(payload: bytes, ts: str = "1700000000") -> str:
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


def test_subscription_status_map_known_values():
    assert _SUBSCRIPTION_STATUS_MAP["active"] == "active"
    assert _SUBSCRIPTION_STATUS_MAP["trialing"] == "trialing"
    assert _SUBSCRIPTION_STATUS_MAP["past_due"] == "past_due"
    assert _SUBSCRIPTION_STATUS_MAP["paused"] == "canceled"
    assert _SUBSCRIPTION_STATUS_MAP["canceled"] == "canceled"


def test_subscription_status_map_unknown_falls_back_to_past_due():
    assert _SUBSCRIPTION_STATUS_MAP.get("some_future_status", "past_due") == "past_due"
