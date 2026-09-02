"""raw_html_snapshots

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-02

0006 stored the normalized *text* either side of a change — enough for a
human to read, not enough for an auditor who wants the document as it
actually rendered (markup, structure, the exact bytes the vendor published).
This adds the raw HTML alongside it, both on `subprocessors` (so the next
check has a "before" to carry into the event) and on `change_events` (the
permanent record). Nullable for the same reason 0006 was: history recorded
before this migration kept only the normalized text.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("subprocessors", sa.Column("last_raw_html", sa.Text(), nullable=True))
    op.add_column("change_events", sa.Column("old_raw_html", sa.Text(), nullable=True))
    op.add_column("change_events", sa.Column("new_raw_html", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("change_events", "new_raw_html")
    op.drop_column("change_events", "old_raw_html")
    op.drop_column("subprocessors", "last_raw_html")
