import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class DeliveryEventType(str, enum.Enum):
    """The four states Resend's webhooks report for one send attempt —
    see docs/manifest_v2.md's [NOTIFICATION] section. `email.sent` and
    `email.complained` are deliberately not modeled here: `sent` is already
    covered by a NotificationRecipient row simply existing, and a spam
    complaint is a different signal than the delivery-log this PR scopes
    to (unhandled webhook types are logged and ignored, never an error)."""
    delivered = "delivered"
    bounced = "bounced"
    deferred = "deferred"
    failed = "failed"


_DELIVERY_EVENT_TYPE_VALUES = tuple(t.value for t in DeliveryEventType)


class NotificationRecipient(TimestampMixin, Base):
    """One address the frozen notice actually went to — the recipient-list
    snapshot itself (KURAL 0: this list, once written at send time, never
    changes; ChangeEvent.recipient_count is just its row count). Resend's
    webhooks correlate back to a row here by resend_message_id, and the
    append-only NotificationDeliveryEvent log below is what actually
    records delivery outcomes — this row is the recipient, not the log."""
    __tablename__ = "notification_recipients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("change_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # The Resend message id for the CURRENT send attempt — updated in place
    # on a manual resend (last_manual_resend_at/_by record that it happened
    # and by whom). This pointer being mutable does not weaken the evidence:
    # the evidence is the append-only event log below, keyed by Resend's own
    # webhook_event_id, never this column.
    resend_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Set only if the Resend API call itself raised (network error, 4xx) —
    # distinct from a bounce/failure Resend reports later via webhook after
    # accepting the send.
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_manual_resend_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_manual_resend_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    manually_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manually_resolved_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    manually_resolved_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    change_event: Mapped["ChangeEvent"] = relationship(  # noqa: F821
        "ChangeEvent",
        back_populates="notification_recipients",
        lazy="raise",
    )
    delivery_events: Mapped[list["NotificationDeliveryEvent"]] = relationship(
        "NotificationDeliveryEvent",
        back_populates="recipient",
        lazy="raise",
        cascade="all, delete-orphan",
        order_by="NotificationDeliveryEvent.occurred_at",
    )


class NotificationDeliveryEvent(Base):
    """APPEND-ONLY. One row per Resend webhook delivery, never updated or
    deleted — a row here is a fact TrustPages was told, not a current
    status (see app/services/notifications.py for how "current status" is
    derived from this log, out of order arrivals included). Deduplicated on
    webhook_event_id (Resend/Svix's own delivery id): a retried webhook
    delivery must never become a second row."""
    __tablename__ = "notification_delivery_events"
    __table_args__ = (
        CheckConstraint(
            f"event_type IN {_DELIVERY_EVENT_TYPE_VALUES}",
            name="ck_notification_delivery_events_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notification_recipients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # From the webhook payload's own created_at — when Resend says the
    # event happened, not when we happened to receive it (see received_at).
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    webhook_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    raw_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )

    recipient: Mapped["NotificationRecipient"] = relationship(
        "NotificationRecipient",
        back_populates="delivery_events",
        lazy="raise",
    )
