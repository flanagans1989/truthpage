"""tenant_email

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("email", sa.String(320), nullable=True))
    op.create_index("ix_tenants_email", "tenants", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenants_email", table_name="tenants")
    op.drop_column("tenants", "email")
