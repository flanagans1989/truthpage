"""system_state

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-02

One key/value table holding operational heartbeats — currently only the
sweep cycle's. See app/db/models/system_state.py for why this has to live
in the database rather than in process memory: the thing being watched is
the process itself, so its own memory is exactly the wrong place to keep
the evidence that it is alive.

Purely additive, no data migration. An empty table reads as "the sweep has
never reported in", which is the correct state on a fresh deploy and is
handled explicitly by GET /healthz/monitoring's boot grace window.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_state",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("system_state")
