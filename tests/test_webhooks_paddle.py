import hashlib
import hmac
import time

from app.routers.webhooks import _SUBSCRIPTION_STATUS_MAP, _plan_from_items, _verify_signature

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
    # Both mean "no paid subscription any more", and that lands on the free
    # plan rather than on a switched-off account.
    assert _SUBSCRIPTION_STATUS_MAP["paused"] == "free"
    assert _SUBSCRIPTION_STATUS_MAP["canceled"] == "free"


def test_ending_statuses_are_the_ones_that_need_the_free_limit_applied():
    from app.routers.webhooks import _ENDS_THE_SUBSCRIPTION

    # A status write alone is not enough for these: the page limit has to be
    # applied too, or a former subscriber keeps 25 pages monitored for free.
    assert _ENDS_THE_SUBSCRIPTION == {"free"}
    ending = {v for v in _SUBSCRIPTION_STATUS_MAP.values() if v == "free"}
    assert ending <= _ENDS_THE_SUBSCRIPTION


def test_subscription_status_map_unknown_falls_back_to_past_due():
    assert _SUBSCRIPTION_STATUS_MAP.get("some_future_status", "past_due") == "past_due"


class TestPlanFromItems:
    def test_matches_growth_price_id(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "pri_growth")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_STARTER", "pri_starter")
        assert _plan_from_items([{"price": {"id": "pri_growth"}}]) == "growth"

    def test_matches_starter_price_id(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "pri_growth")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_STARTER", "pri_starter")
        assert _plan_from_items([{"price": {"id": "pri_starter"}}]) == "starter"

    def test_matches_yearly_price_ids_too(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH_YEARLY", "pri_growth_y")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_STARTER_YEARLY", "pri_starter_y")
        assert _plan_from_items([{"price": {"id": "pri_growth_y"}}]) == "growth"
        assert _plan_from_items([{"price": {"id": "pri_starter_y"}}]) == "starter"

    def test_unrecognised_price_id_returns_none_rather_than_guessing(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "pri_growth")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_STARTER", "pri_starter")
        assert _plan_from_items([{"price": {"id": "pri_something_else"}}]) is None

    def test_empty_or_missing_items_returns_none(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "pri_growth")
        assert _plan_from_items([]) is None
        assert _plan_from_items(None) is None

    def test_blank_configured_price_id_never_matches_a_blank_item(self, monkeypatch):
        """A tenant on a price Paddle hasn't set an id for (both blank) must
        never be misread as a match — that would silently plan="growth" for
        garbage input."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_STARTER", "")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_STARTER_YEARLY", "")
        monkeypatch.setattr(settings, "PADDLE_PRICE_ID_GROWTH", "pri_growth")
        assert _plan_from_items([{"price": {"id": ""}}]) is None
        assert _plan_from_items([{"price": {"id": None}}]) is None
