"""rfc3161_timestamp

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-02

RFC 3161 independent timestamping for change_events.new_raw_html_hash —
see app/core/tsa.py, app/services/tsa_retry.py, and docs/manifest_v2.md.

KURAL 0 (absolute, non-negotiable): every existing row backfills to
`not_available_pre_tsa` via server_default — a TERMINAL state no code path
may ever move a row out of (see TimestampStatus in
app/db/models/change_event.py). A pre-existing capture must never become
eligible for a timestamp after the fact; doing so would have this product
assert a document existed at a time it did not.

All six columns are additive with safe defaults — no data migration beyond
that server_default backfill.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP_STATUS_VALUES = ("pending", "retrying", "timestamped", "failed", "not_available_pre_tsa")


def upgrade() -> None:
    op.add_column(
        "change_events",
        sa.Column(
            "timestamp_status",
            sa.String(30),
            nullable=False,
            server_default="not_available_pre_tsa",
        ),
    )
    op.create_check_constraint(
        "ck_change_events_timestamp_status",
        "change_events",
        f"timestamp_status IN {_TIMESTAMP_STATUS_VALUES}",
    )
    op.add_column("change_events", sa.Column("tsa_token", sa.LargeBinary(), nullable=True))
    op.add_column("change_events", sa.Column("tsa_authority_url", sa.String(500), nullable=True))
    op.add_column("change_events", sa.Column("tsa_time_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "change_events",
        sa.Column("tsa_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("change_events", sa.Column("tsa_last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("change_events", "tsa_last_error")
    op.drop_column("change_events", "tsa_attempt_count")
    op.drop_column("change_events", "tsa_time_utc")
    op.drop_column("change_events", "tsa_authority_url")
    op.drop_column("change_events", "tsa_token")
    op.drop_constraint("ck_change_events_timestamp_status", "change_events", type_="check")
    op.drop_column("change_events", "timestamp_status")
