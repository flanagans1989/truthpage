"""change_event_notice_draft

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("change_events", sa.Column("notice_subject", sa.String(500), nullable=True))
    op.add_column("change_events", sa.Column("notice_body", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("change_events", "notice_body")
    op.drop_column("change_events", "notice_subject")
