"""Plan transitions.

Two ways a paid plan ends: a trial runs out, or a subscription is cancelled.
Both land on the permanent free plan with a few pages still watched rather
than switching the account off — a dead account tells the tenant nothing, and
a trust page that stops updating is worse for their customers than for us.
Both paths go through `move_tenant_to_free` so they cannot drift apart.
"""
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.subprocessor import Subprocessor


def free_plan_split(
    subprocessors: Iterable[Any], limit: int
) -> tuple[list[Any], list[Any]]:
    """Split a tenant's pages into (kept, dropped) for the free plan.

    Oldest first: the pages added at the very beginning are the ones the
    tenant chose most deliberately, and keeping the newest would silently
    drop whatever they set up on day one. Rows already switched off by the
    tenant are counted as dropped without touching them, so a tenant who
    curated their own list keeps that choice.
    """
    ordered: Sequence[Any] = sorted(
        subprocessors, key=lambda sp: (sp.created_at, str(sp.id))
    )
    kept: list[Any] = []
    dropped: list[Any] = []
    for sp in ordered:
        if not sp.monitoring_enabled:
            dropped.append(sp)
        elif len(kept) < limit:
            kept.append(sp)
        else:
            dropped.append(sp)
    return kept, dropped


async def move_tenant_to_free(tenant: Any, session: AsyncSession) -> int:
    """Put a tenant on the free plan and switch off the pages above its limit.

    Loads the tenant's pages itself so callers do not have to remember an
    eager load — the webhook path has no reason to have them. Does not
    commit: the caller owns the transaction.

    Returns the number of pages switched off.
    """
    rows = (
        await session.execute(
            select(Subprocessor).where(Subprocessor.tenant_id == tenant.id)
        )
    ).scalars().all()

    tenant.subscription_status = "free"
    _, dropped = free_plan_split(rows, settings.FREE_TIER_MAX_SUBPROCESSORS)
    switched_off = 0
    for sp in dropped:
        if sp.monitoring_enabled:
            sp.monitoring_enabled = False
            switched_off += 1
    return switched_off
