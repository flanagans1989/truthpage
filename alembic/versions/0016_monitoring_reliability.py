"""monitoring_reliability

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-02

Resource-health tracking for Tier-2 monitoring:
  - subprocessors.consecutive_failure_count / monitoring_alert_sent_at — the
    "Monitoring Alert" badge + dedupe-window email.
  - tenants.tier2_daily_count / tier2_daily_date — the per-tenant, per-day
    Tier-2 (Playwright) run budget.

All four columns are additive with safe defaults; every existing row
backfills to "healthy, budget untouched" (0 / NULL) rather than needing a
data migration — a pre-existing source has no failure history to invent and
no Tier-2 spend to credit or debit.
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
    op.drop_column("subprocessors", "monitoring_alert_sent_at")
    op.drop_column("subprocessors", "consecutive_failure_count")
