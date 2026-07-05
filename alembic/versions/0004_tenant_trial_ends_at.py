"""tenant_trial_ends_at

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    # Existing trialing tenants get a fresh 14-day window from this deploy
    op.execute(
        "UPDATE tenants SET trial_ends_at = now() + interval '14 days' "
        "WHERE subscription_status = 'trialing' AND trial_ends_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("tenants", "trial_ends_at")
