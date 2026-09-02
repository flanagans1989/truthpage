"""privacy_contact_and_baseline_tsa

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-02

Two independent, additive follow-ups to PR 4's review:

- `tenants.privacy_contact_email` — the address the [OBJECTION WINDOW]
  notice's `[CONTACT]` placeholder resolves to. Nullable: `Tenant.
  objection_contact_email` falls back to the account email when unset, so
  no data backfill is needed and an existing tenant's behavior is
  unchanged until they explicitly set one.

- `subprocessors.baseline_*` — RFC 3161 timestamping for a source's very
  FIRST captured snapshot. Before this, only a `change_event` (a real
  detected change) was ever timestamp-eligible; the baseline snapshot
  taken on a subprocessor's first check was never itself a change_event
  (there is nothing to diff against yet — see monitoring.py), so it never
  got a chance to be timestamped at all. That baseline becomes the
  `before.html` of a source's first real change_event later — leaving it
  permanently un-timestamped otherwise, even though it is a perfectly
  real, current capture with nothing pre-TSA about it.

  Mirrors ChangeEvent's TSA columns and KURAL 0 exactly:
  baseline_timestamp_status defaults to `not_available_pre_tsa`
  (server_default — the safe, terminal state) for every EXISTING
  subprocessor row (its baseline predates this feature and must never be
  backdated); monitoring.py explicitly sets it to `pending` at the moment
  a NEW baseline is captured, same pattern as ChangeEvent.
  baseline_raw_html_hash freezes which digest was actually offered for
  stamping — subprocessors.last_raw_html_hash keeps moving with every
  later check, so the baseline's own hash has to be copied separately or
  it would drift out from under an in-flight stamping attempt.

All columns are additive with safe defaults. No data migration beyond the
server_default backfill — a pre-existing baseline is not retroactively
assigned a digest it was never actually captured alongside a timestamp
for.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP_STATUS_VALUES = ("pending", "retrying", "timestamped", "failed", "not_available_pre_tsa")


def upgrade() -> None:
    op.add_column("tenants", sa.Column("privacy_contact_email", sa.String(320), nullable=True))

    op.add_column("subprocessors", sa.Column("baseline_raw_html_hash", sa.String(64), nullable=True))
    op.add_column(
        "subprocessors",
        sa.Column(
            "baseline_timestamp_status",
            sa.String(30),
            nullable=False,
            server_default="not_available_pre_tsa",
        ),
    )
    op.create_check_constraint(
        "ck_subprocessors_baseline_timestamp_status",
        "subprocessors",
        f"baseline_timestamp_status IN {_TIMESTAMP_STATUS_VALUES}",
    )
    op.add_column("subprocessors", sa.Column("baseline_tsa_token", sa.LargeBinary(), nullable=True))
    op.add_column("subprocessors", sa.Column("baseline_tsa_authority_url", sa.String(500), nullable=True))
    op.add_column("subprocessors", sa.Column("baseline_tsa_time_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "subprocessors",
        sa.Column("baseline_tsa_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("subprocessors", sa.Column("baseline_tsa_last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("subprocessors", "baseline_tsa_last_error")
    op.drop_column("subprocessors", "baseline_tsa_attempt_count")
    op.drop_column("subprocessors", "baseline_tsa_time_utc")
    op.drop_column("subprocessors", "baseline_tsa_authority_url")
    op.drop_column("subprocessors", "baseline_tsa_token")
    op.drop_constraint("ck_subprocessors_baseline_timestamp_status", "subprocessors", type_="check")
    op.drop_column("subprocessors", "baseline_timestamp_status")
    op.drop_column("subprocessors", "baseline_raw_html_hash")

    op.drop_column("tenants", "privacy_contact_email")
