"""notification_delivery

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-02

Delivery-record and objection-window evidence — see docs/manifest_v2.md's
[REVIEW]/[NOTIFICATION]/[OBJECTION WINDOW] sections and
app/services/approval.py.

KURAL 0 for this PR: once a notice is sent, its frozen text, recipient
list, reviewer identity, and objection-window dates never change again.
Concretely:

  - change_events gains reviewer identity (reviewed_by_name/email/at,
    review_action), a frozen copy of the notice actually sent
    (notice_frozen_subject/body/at — separate from the editable
    notice_subject/body, which may still be redrafted for reference after
    the fact without touching what was already sent), the recipient-list
    size at send time (recipient_count), and the objection window opened
    for that send (window_days, window_closes_at — window_opened_at is
    not a new column, it reuses the existing notified_at/"sent_at").
  - notification_recipients is the frozen recipient-list snapshot itself,
    one row per address the notice actually went to.
  - notification_delivery_events is an APPEND-ONLY log of Resend webhook
    deliveries against those recipients — current status is derived from
    it (see app/services/notifications.py), never overwritten in place.
  - objections holds manually-recorded objections (email/phone, entered by
    a human), each attributed to whoever entered it.
  - tenants.objection_window_days is the per-tenant configurable window
    length (default 30) the DPA promises — never hardcoded.

All columns/tables are additive with safe defaults. Every existing
change_event backfills to NULL/not_available across the board: no past
approval is retroactively assigned a reviewer, a sent notice, or an
objection window it never actually had.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_ACTION_VALUES = ("notice_released_by_reviewer", "auto_published_cosmetic")
_DELIVERY_EVENT_TYPES = ("delivered", "bounced", "deferred", "failed")


def upgrade() -> None:
    op.add_column("change_events", sa.Column("reviewed_by_name", sa.String(255), nullable=True))
    op.add_column("change_events", sa.Column("reviewed_by_email", sa.String(320), nullable=True))
    op.add_column("change_events", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("change_events", sa.Column("review_action", sa.String(50), nullable=True))
    op.create_check_constraint(
        "ck_change_events_review_action",
        "change_events",
        f"review_action IS NULL OR review_action IN {_REVIEW_ACTION_VALUES}",
    )
    op.add_column("change_events", sa.Column("notice_frozen_subject", sa.Text(), nullable=True))
    op.add_column("change_events", sa.Column("notice_frozen_body", sa.Text(), nullable=True))
    op.add_column("change_events", sa.Column("notice_frozen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("change_events", sa.Column("recipient_count", sa.Integer(), nullable=True))
    op.add_column("change_events", sa.Column("window_days", sa.Integer(), nullable=True))
    op.add_column("change_events", sa.Column("window_closes_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "tenants",
        sa.Column("objection_window_days", sa.Integer(), nullable=False, server_default="30"),
    )

    op.create_table(
        "notification_recipients",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "change_event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("change_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        # Latest Resend message id for this recipient — updated on a manual
        # resend (see last_manual_resend_at below). The append-only event
        # log below is the evidence trail; this column is just "where do
        # webhook events for the CURRENT attempt correlate to".
        sa.Column("resend_message_id", sa.String(255), nullable=True),
        sa.Column("send_error", sa.Text(), nullable=True),
        sa.Column("last_manual_resend_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_manual_resend_by", sa.String(320), nullable=True),
        sa.Column("manually_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manually_resolved_by", sa.String(320), nullable=True),
        sa.Column("manually_resolved_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_notification_recipients_change_event_id", "notification_recipients", ["change_event_id"]
    )
    op.create_index(
        "ix_notification_recipients_resend_message_id",
        "notification_recipients",
        ["resend_message_id"],
    )

    op.create_table(
        "notification_delivery_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "recipient_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("notification_recipients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        # Resend/Svix's own event id (the svix-id header) — the idempotency
        # key. Nullable-unique: Postgres does not treat multiple NULLs as
        # colliding, so this still enforces "never insert the same webhook
        # delivery twice" without needing a value for every row.
        sa.Column("webhook_event_id", sa.String(255), nullable=True),
        sa.Column("raw_type", sa.String(50), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "ck_notification_delivery_events_type",
        "notification_delivery_events",
        f"event_type IN {_DELIVERY_EVENT_TYPES}",
    )
    op.create_index(
        "ix_notification_delivery_events_recipient_id",
        "notification_delivery_events",
        ["recipient_id"],
    )
    op.create_index(
        "ix_notification_delivery_events_webhook_event_id",
        "notification_delivery_events",
        ["webhook_event_id"],
        unique=True,
    )

    op.create_table(
        "objections",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "change_event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("change_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("objector_name", sa.String(255), nullable=False),
        sa.Column("objected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by_email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_objections_change_event_id", "objections", ["change_event_id"])


def downgrade() -> None:
    op.drop_index("ix_objections_change_event_id", table_name="objections")
    op.drop_table("objections")

    op.drop_index("ix_notification_delivery_events_webhook_event_id", table_name="notification_delivery_events")
    op.drop_index("ix_notification_delivery_events_recipient_id", table_name="notification_delivery_events")
    op.drop_constraint("ck_notification_delivery_events_type", "notification_delivery_events", type_="check")
    op.drop_table("notification_delivery_events")

    op.drop_index("ix_notification_recipients_resend_message_id", table_name="notification_recipients")
    op.drop_index("ix_notification_recipients_change_event_id", table_name="notification_recipients")
    op.drop_table("notification_recipients")

    op.drop_column("tenants", "objection_window_days")

    op.drop_column("change_events", "window_closes_at")
    op.drop_column("change_events", "window_days")
    op.drop_column("change_events", "recipient_count")
    op.drop_column("change_events", "notice_frozen_at")
    op.drop_column("change_events", "notice_frozen_body")
    op.drop_column("change_events", "notice_frozen_subject")
    op.drop_constraint("ck_change_events_review_action", "change_events", type_="check")
    op.drop_column("change_events", "review_action")
    op.drop_column("change_events", "reviewed_at")
    op.drop_column("change_events", "reviewed_by_email")
    op.drop_column("change_events", "reviewed_by_name")
