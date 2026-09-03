"""vendor_robots_blocked

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-02

The public vendor directory now honours robots.txt (see
app/core/scraper/robots.py). A vendor whose robots.txt refuses us has to
say so on its own page rather than simply stopping at a frozen date —
that would be the same silent-staleness failure the staleness badge was
added to prevent, just with a different cause.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vendors",
        sa.Column(
            "robots_blocked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("vendors", "robots_blocked")
