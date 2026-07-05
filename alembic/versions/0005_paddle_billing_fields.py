"""paddle_billing_fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("tenants", "stripe_customer_id", new_column_name="paddle_customer_id")
    op.add_column("tenants", sa.Column("paddle_subscription_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "paddle_subscription_id")
    op.alter_column("tenants", "paddle_customer_id", new_column_name="stripe_customer_id")
