"""tenant_onboarded_at

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-02

Records the moment a tenant pressed Publish in the onboarding wizard. NULL
means the wizard has not been finished, which is what routes a fresh signup
into it. Existing tenants are backfilled to their creation time — they built
their list before the wizard existed and must not be sent back through it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE tenants SET onboarded_at = created_at WHERE onboarded_at IS NULL")


def downgrade() -> None:
    op.drop_column("tenants", "onboarded_at")
