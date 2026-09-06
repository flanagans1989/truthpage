"""funnel_events

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-06

The 30-day sales test needs the conversion funnel to be answerable by SQL,
not just trusted to GA4 — this table is written by app/services/analytics.py
alongside (never instead of) the existing GA4 gtag calls.

anon_id is a random cookie value only (see app/routers deps for the tp_aid
cookie) — no IP, no user-agent, nothing that makes this personal data.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "funnel_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("anon_id", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_funnel_events_event_name", "funnel_events", ["event_name"])
    op.create_index("ix_funnel_events_created_at", "funnel_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_funnel_events_created_at", table_name="funnel_events")
    op.drop_index("ix_funnel_events_event_name", table_name="funnel_events")
    op.drop_table("funnel_events")
