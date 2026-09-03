"""content_format_version

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-02

The normalizer's output shape changed (one line per block element instead
of the whole document on one line — see app/core/scraper/normalizer.py's
NORMALIZER_VERSION). Every stored content hash was computed under the old
shape, so on the first sweep after deploy every single monitored page
would hash differently and look changed.

On the tenant side that is not a cosmetic problem: it would create a
change_event per source, email every tenant that a review is waiting, and
auto-publish whatever the classifier called COSMETIC — telling real
customers about changes their vendors never made. On the directory side it
would publish a fabricated "change" for every vendor page.

So each source records which normalizer version its stored hash was
produced by. A mismatch means "we changed how we read pages", not "the
page changed", and the sweep re-baselines silently.

server_default="1" backfills existing rows as pre-change, which is what
they are. New rows are written with the current version by the app.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("subprocessors", "vendors"):
        op.add_column(
            table,
            sa.Column(
                "content_format_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )


def downgrade() -> None:
    for table in ("subprocessors", "vendors"):
        op.drop_column(table, "content_format_version")
