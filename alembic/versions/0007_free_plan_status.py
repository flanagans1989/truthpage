"""free_plan_status

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-01

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_tenants_subscription_status"
_OLD = ("trialing", "active", "past_due", "canceled", "unpaid")
_NEW = _OLD + ("free",)


def _recreate(values: tuple[str, ...]) -> None:
    op.drop_constraint(_CONSTRAINT, "tenants", type_="check")
    op.create_check_constraint(_CONSTRAINT, "tenants", f"subscription_status IN {values}")


def upgrade() -> None:
    _recreate(_NEW)


def downgrade() -> None:
    # Free tenants have no billing state to fall back to; park them as
    # cancelled so the narrower constraint can be restored.
    op.execute("UPDATE tenants SET subscription_status = 'canceled' WHERE subscription_status = 'free'")
    _recreate(_OLD)
