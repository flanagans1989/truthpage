"""change_event_content_snapshots

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("change_events", sa.Column("old_content_text", sa.Text(), nullable=True))
    op.add_column("change_events", sa.Column("new_content_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("change_events", "new_content_text")
    op.drop_column("change_events", "old_content_text")
