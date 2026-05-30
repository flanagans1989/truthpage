"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-05-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("subscription_status", sa.String(20), server_default="trialing", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "subscription_status IN ('trialing', 'active', 'past_due', 'canceled', 'unpaid')",
            name="ck_tenants_subscription_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    op.create_table(
        "subprocessors",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("monitored_url", sa.String(2048), nullable=False),
        sa.Column("monitoring_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_content_hash", sa.String(64), nullable=True),
        sa.Column("last_content_text", sa.Text(), nullable=True),
        sa.Column("requires_browser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("check_interval_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subprocessors_tenant_id", "subprocessors", ["tenant_id"])

    op.create_table(
        "change_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("subprocessor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("old_hash", sa.String(64), nullable=False),
        sa.Column("new_hash", sa.String(64), nullable=False),
        sa.Column("raw_diff", sa.Text(), nullable=False),
        sa.Column("llm_summary", sa.Text(), nullable=True),
        sa.Column("llm_classification", sa.String(100), nullable=True),
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending_review", nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected', 'auto_published')",
            name="ck_change_events_status",
        ),
        sa.ForeignKeyConstraint(["subprocessor_id"], ["subprocessors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_change_events_subprocessor_id", "change_events", ["subprocessor_id"])

    op.create_table(
        "subscribers",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("confirmed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscribers_tenant_id", "subscribers", ["tenant_id"])
    op.create_index("ix_subscribers_email", "subscribers", ["email"])


def downgrade() -> None:
    op.drop_table("subscribers")
    op.drop_table("change_events")
    op.drop_table("subprocessors")
    op.drop_table("tenants")
