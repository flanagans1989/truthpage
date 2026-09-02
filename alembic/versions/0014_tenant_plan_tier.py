"""tenant_plan_tier

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-02

`subscription_status` says whether billing is in good standing (trialing /
active / past_due / free); it never said *which paid tier* a tenant bought.
Adding Starter as a second paid tier needs that distinction. Existing paying
tenants backfill to "growth" — the only paid tier that existed before this
migration, so nobody's limits or features change on deploy.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("plan", sa.String(20), nullable=False, server_default="growth"),
    )
    op.create_check_constraint(
        "ck_tenants_plan", "tenants", "plan IN ('starter', 'growth')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenants_plan", "tenants", type_="check")
    op.drop_column("tenants", "plan")
