"""vendor_directory

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("monitored_url", sa.String(2048), nullable=False),
        sa.Column("homepage_url", sa.String(2048), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entries", sa.JSON(), nullable=True),
        sa.Column("entries_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_content_hash", sa.String(64), nullable=True),
        sa.Column("last_content_text", sa.Text(), nullable=True),
        sa.Column("requires_browser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vendors_slug", "vendors", ["slug"], unique=True)
    op.create_index("ix_vendors_is_published", "vendors", ["is_published"])

    op.create_table(
        "vendor_changes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_hash", sa.String(64), nullable=False),
        sa.Column("new_hash", sa.String(64), nullable=False),
        sa.Column("raw_diff", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("added", sa.JSON(), nullable=True),
        sa.Column("removed", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vendor_changes_vendor_id", "vendor_changes", ["vendor_id"])


def downgrade() -> None:
    op.drop_table("vendor_changes")
    op.drop_index("ix_vendors_is_published", table_name="vendors")
    op.drop_index("ix_vendors_slug", table_name="vendors")
    op.drop_table("vendors")
