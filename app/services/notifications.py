"""Derives a per-recipient delivery status, and the [NOTIFICATION]/
[OBJECTION WINDOW] manifest values, from data already stored elsewhere.

Kept out of app/services/evidence.py (which only renders) and out of the
dashboard router (which only handles requests) so the actual rule — how an
out-of-order or repeated webhook event resolves to one status — lives in
one place and can be tested without a database or an HTTP request.
"""
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.db.models.mixins import utc_now

# A bounce/failure is sticky: once a recipient has one, it stays the
# reported status even if a later event (a stale retried "delivered", a
# delayed provider report) arrives after it — Resend's own timing means a
# late-arriving positive event is noise, not a correction. Only a human
# marking it manually resolved moves a recipient off this state; nothing
# automatic does. See docs/manifest_v2.md, PR 4's section 2e.
_STICKY_NEGATIVE = frozenset({"bounced", "failed"})


def derive_recipient_status(recipient: Any) -> str:
    """One status word for a NotificationRecipient, from its (already
    loaded) `delivery_events`: 'bounced' | 'failed' | 'resolved' (a bounce
    or failure a human has since marked manually resolved) | 'delivered' |
    'deferred' | 'queued' (sent, no webhook event yet) | 'send_failed' (the
    Resend API call itself never succeeded — recipient.send_error is set,
    there is no message id and so no webhook can ever arrive for it).

    A manual resend (last_manual_resend_at) starts a new attempt: only
    events from that moment on count toward the CURRENT status — an old
    bounce from before the resend must not keep a genuinely-now-delivered
    recipient stuck reading "bounced" forever. Events from before the
    resend stay in the log (still visible in the CSV's last_event_at_utc)
    but stop being authoritative for "what's true right now".
    """
    if recipient.resend_message_id is None and recipient.send_error:
        return "send_failed"

    events = recipient.delivery_events
    if recipient.last_manual_resend_at is not None:
        events = [e for e in events if e.occurred_at >= recipient.last_manual_resend_at]
    types_seen = {e.event_type for e in events}
    negative = types_seen & _STICKY_NEGATIVE
    if negative:
        if recipient.manually_resolved_at is not None:
            return "resolved"
        return "bounced" if "bounced" in negative else "failed"
    if "delivered" in types_seen:
        return "delivered"
    if "deferred" in types_seen:
        return "deferred"
    return "queued"


# Statuses that count as a real compliance gap for bounced_count / the
# dashboard alert banner — a resolved one still counts (a human annotated
# it, they did not undo the fact that the notice never arrived).
_GAP_STATUSES = frozenset({"bounced", "failed", "resolved", "send_failed"})


def summarize_recipients(recipients: Iterable[Any]) -> dict[str, int]:
    """[NOTIFICATION]'s delivered_count/bounced_count — computed fresh from
    the current log every time (never stored), so these two numbers can
    never drift out of sync with the event log they're derived from."""
    delivered = 0
    gap = 0
    for recipient in recipients:
        status = derive_recipient_status(recipient)
        if status == "delivered":
            delivered += 1
        elif status in _GAP_STATUSES:
            gap += 1
    return {"delivered_count": delivered, "bounced_count": gap}


def compute_objection_status(event: Any) -> str:
    """One of validate_objection_status()'s four permitted forms.

    Precedence: a recorded objection is the most important fact and wins
    regardless of whether the window is still open; otherwise an open
    window reports as open; otherwise (window closed, nothing recorded)
    reports a clean negative — with the "as of" timestamp evaluated now,
    the same way delivered_count/bounced_count are, since this is a
    statement about the state of the record at read time, not something
    frozen at send time.
    """
    if not getattr(event, "recipient_count", None):
        return "not_available"

    objections = getattr(event, "objections", None) or []
    if objections:
        return f"{len(objections)} objection(s) recorded"

    closes_at: datetime | None = getattr(event, "window_closes_at", None)
    if closes_at is not None and utc_now() < closes_at:
        return f"Window open (closes {_iso_utc(closes_at)})"

    return f"No objection recorded via TrustPages as of {_iso_utc(utc_now())}"


def _iso_utc(value: datetime) -> str:
    """Same format as app.services.evidence.iso_utc — duplicated rather
    than imported to avoid a cross-import (evidence.py calls into this
    module), not because the rule differs."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
