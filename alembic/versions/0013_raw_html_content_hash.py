"""raw_html_content_hash

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-02

0012 added the raw HTML itself. This adds its SHA-256 alongside it —
`old_hash`/`new_hash` on `change_events` are hashes of the *normalized* text
(what change detection compares), not of the HTML document a downloaded
evidence bundle actually carries. An auditor checking that before.html/
after.html were not altered after download needs a digest of the file they
are holding, not of a normalization step they cannot reproduce.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("subprocessors", sa.Column("last_raw_html_hash", sa.String(64), nullable=True))
    op.add_column("change_events", sa.Column("old_raw_html_hash", sa.String(64), nullable=True))
    op.add_column("change_events", sa.Column("new_raw_html_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("change_events", "new_raw_html_hash")
    op.drop_column("change_events", "old_raw_html_hash")
    op.drop_column("subprocessors", "last_raw_html_hash")
