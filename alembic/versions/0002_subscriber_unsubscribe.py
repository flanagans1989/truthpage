"""subscriber_unsubscribe

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("subscribers", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("subscribers", sa.Column("unsubscribe_token", sa.String(64), nullable=True))
    op.execute(
        "UPDATE subscribers "
        "SET unsubscribe_token = md5(random()::text || clock_timestamp()::text || id::text) "
        "WHERE unsubscribe_token IS NULL"
    )
    op.alter_column("subscribers", "unsubscribe_token", nullable=False)
    op.create_index("ix_subscribers_unsubscribe_token", "subscribers", ["unsubscribe_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_subscribers_unsubscribe_token", table_name="subscribers")
    op.drop_column("subscribers", "unsubscribe_token")
    op.drop_column("subscribers", "is_active")
