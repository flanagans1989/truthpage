"""export_entitled

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-02

Downloadable evidence was gated on the tenant's CURRENT plan, so cancelling
Growth took away the ability to export records that were captured while
they were paying for exactly that. The records stayed in the database and
stayed visible on the dashboard — only the file they were sold was
withheld.

For a compliance product that is the wrong shape of gate: the thing a
customer needs an audit pack for is usually something that happened
months ago, and "we still have your evidence, you just cannot have it"
reads as hostage-taking to precisely the audience this product courts.

So entitlement is stamped on the record when it is captured, and stays
with it. Growth still buys evidence packs; it no longer un-buys the ones
already earned.

Backfill sets it TRUE for every existing change_event belonging to a
tenant that currently has Growth features — those are the records that
were captured under the entitlement and would otherwise be silently
downgraded by this very migration.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "change_events",
        sa.Column(
            "export_entitled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Mirrors Tenant.has_growth_features at the time this runs.
    op.execute(
        """
        UPDATE change_events
        SET export_entitled = true
        WHERE subprocessor_id IN (
            SELECT s.id
            FROM subprocessors s
            JOIN tenants t ON t.id = s.tenant_id
            WHERE t.subscription_status = 'trialing'
               OR (t.subscription_status <> 'free' AND t.plan <> 'starter')
        )
        """
    )


def downgrade() -> None:
    op.drop_column("change_events", "export_entitled")
