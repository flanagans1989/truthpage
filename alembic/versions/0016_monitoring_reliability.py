"""monitoring_reliability

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-02

Resource-health tracking for Tier-2 monitoring. Edited in place (not a new
0017) — this migration had not yet run against production when review
caught the gaps below, so there is exactly one clean migration for this
feature rather than one that adds columns and a follow-up that reworks them.

  - subprocessors.consecutive_failure_count / monitoring_alert_sent_at /
    last_failure_reason — the failure-based "Monitoring Alert" badge +
    dedupe-window email, with the reason it fired.
  - subprocessors.staleness_alert_sent_at — the second, independent alarm:
    fires on elapsed time since the last successful check regardless of
    cause (a failure streak, a budget deferral, anything).
  - subprocessors.tier2_deferred — visibly marks a check skipped for lack of
    Tier-2 budget, so a deferred source is never just silently unscraped.
  - subprocessors.tier2_daily_count / tier2_daily_date — the per-SOURCE
    Tier-2 (Playwright) daily quota, the real cost control.
  - tenants.tier2_daily_count / tier2_daily_date — the tenant-wide pool,
    now a cost safety valve rather than a feature limit (see
    Tenant.tier2_daily_limit).

All columns are additive with safe defaults; every existing row backfills to
"healthy, budget untouched, never deferred" (0 / NULL / false) — no data
migration needed, since a pre-existing source has no failure history to
invent and no Tier-2 spend to credit or debit.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subprocessors",
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subprocessors",
        sa.Column("monitoring_alert_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subprocessors",
        sa.Column("last_failure_reason", sa.String(20), nullable=True),
    )
    op.add_column(
        "subprocessors",
        sa.Column("tier2_deferred", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "subprocessors",
        sa.Column("tier2_daily_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subprocessors",
        sa.Column("tier2_daily_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "subprocessors",
        sa.Column("staleness_alert_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("tier2_daily_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("tier2_daily_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "tier2_daily_date")
    op.drop_column("tenants", "tier2_daily_count")
    op.drop_column("subprocessors", "staleness_alert_sent_at")
    op.drop_column("subprocessors", "tier2_daily_date")
    op.drop_column("subprocessors", "tier2_daily_count")
    op.drop_column("subprocessors", "tier2_deferred")
    op.drop_column("subprocessors", "last_failure_reason")
    op.drop_column("subprocessors", "monitoring_alert_sent_at")
    op.drop_column("subprocessors", "consecutive_failure_count")
