"""app/services/notifications.py — deriving a status from an append-only
event log, and the [OBJECTION WINDOW]/[NOTIFICATION] manifest values from
it. Pure logic, no database — lightweight stand-ins for the ORM objects are
enough since only attribute access is used.
"""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.services.notifications import (
    compute_objection_status,
    derive_recipient_status,
    summarize_recipients,
)


@dataclass
class _Event:
    event_type: str
    occurred_at: datetime


@dataclass
class _Recipient:
    resend_message_id: str | None = "msg-1"
    send_error: str | None = None
    manually_resolved_at: datetime | None = None
    last_manual_resend_at: datetime | None = None
    delivery_events: list = field(default_factory=list)


_T0 = datetime(2026, 9, 1, tzinfo=UTC)


class TestDeriveRecipientStatus:
    def test_no_events_yet_is_queued(self):
        assert derive_recipient_status(_Recipient(delivery_events=[])) == "queued"

    def test_send_call_itself_failed(self):
        r = _Recipient(resend_message_id=None, send_error="connection refused")
        assert derive_recipient_status(r) == "send_failed"

    def test_delivered_event(self):
        r = _Recipient(delivery_events=[_Event("delivered", _T0)])
        assert derive_recipient_status(r) == "delivered"

    def test_deferred_event(self):
        r = _Recipient(delivery_events=[_Event("deferred", _T0)])
        assert derive_recipient_status(r) == "deferred"

    def test_bounced_event(self):
        r = _Recipient(delivery_events=[_Event("bounced", _T0)])
        assert derive_recipient_status(r) == "bounced"

    def test_out_of_order_late_delivered_does_not_override_a_bounce(self):
        r = _Recipient(delivery_events=[
            _Event("bounced", _T0),
            _Event("delivered", _T0 + timedelta(hours=1)),  # arrives later, still noise
        ])
        assert derive_recipient_status(r) == "bounced"

    def test_manually_resolved_bounce_reads_as_resolved(self):
        r = _Recipient(
            delivery_events=[_Event("bounced", _T0)],
            manually_resolved_at=_T0 + timedelta(hours=2),
        )
        assert derive_recipient_status(r) == "resolved"

    def test_resend_after_a_bounce_lets_a_fresh_delivered_win(self):
        resend_at = _T0 + timedelta(hours=1)
        r = _Recipient(
            delivery_events=[
                _Event("bounced", _T0),  # before the resend — no longer authoritative
                _Event("delivered", resend_at + timedelta(minutes=5)),
            ],
            last_manual_resend_at=resend_at,
        )
        assert derive_recipient_status(r) == "delivered"

    def test_resend_with_no_new_events_yet_is_queued_not_stale_bounced(self):
        resend_at = _T0 + timedelta(hours=1)
        r = _Recipient(delivery_events=[_Event("bounced", _T0)], last_manual_resend_at=resend_at)
        assert derive_recipient_status(r) == "queued"


class TestSummarizeRecipients:
    def test_counts_delivered_and_gap_separately(self):
        recipients = [
            _Recipient(delivery_events=[_Event("delivered", _T0)]),
            _Recipient(delivery_events=[_Event("bounced", _T0)]),
            _Recipient(delivery_events=[_Event("delivered", _T0)]),
            _Recipient(delivery_events=[]),  # queued — counts toward neither
        ]
        counts = summarize_recipients(recipients)
        assert counts == {"delivered_count": 2, "bounced_count": 1}

    def test_a_resolved_bounce_still_counts_as_a_gap(self):
        recipients = [
            _Recipient(delivery_events=[_Event("bounced", _T0)], manually_resolved_at=_T0),
        ]
        assert summarize_recipients(recipients)["bounced_count"] == 1


@dataclass
class _ChangeEvent:
    recipient_count: int | None
    objections: list = field(default_factory=list)
    window_closes_at: datetime | None = None


@dataclass
class _Objection:
    pass


class TestComputeObjectionStatus:
    def test_no_recipients_is_not_available(self):
        event = _ChangeEvent(recipient_count=0)
        assert compute_objection_status(event) == "not_available"

    def test_recorded_objection_wins_regardless_of_window_state(self):
        event = _ChangeEvent(
            recipient_count=3,
            objections=[_Objection(), _Objection()],
            window_closes_at=datetime.now(UTC) + timedelta(days=10),  # still open
        )
        assert compute_objection_status(event) == "2 objection(s) recorded"

    def test_open_window_with_no_objections(self):
        event = _ChangeEvent(recipient_count=3, window_closes_at=datetime.now(UTC) + timedelta(days=5))
        status = compute_objection_status(event)
        assert status.startswith("Window open (closes ")

    def test_closed_window_with_no_objections(self):
        event = _ChangeEvent(recipient_count=3, window_closes_at=datetime.now(UTC) - timedelta(days=1))
        status = compute_objection_status(event)
        assert status.startswith("No objection recorded via TrustPages as of ")
