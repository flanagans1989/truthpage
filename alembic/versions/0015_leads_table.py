"""leads_table

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-02

Growth tools (the audit grader, the sample-evidence-pack download) capture
an email before a tenant account exists. `leads` holds those — never a
Tenant with no password, which would give an email address every dashboard
privilege a real signup earns.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("context", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leads_email", "leads", ["email"])


def downgrade() -> None:
    op.drop_index("ix_leads_email", table_name="leads")
    op.drop_table("leads")
