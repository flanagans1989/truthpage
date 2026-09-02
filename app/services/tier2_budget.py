"""Atomic Tier-2 (Playwright) daily budget accounting.

Two independent pools, both rolled over and spent in a single UPDATE
statement rather than an ORM read-modify-write: a lazy day-rollover plus a
plain "+1 and commit" is a classic read-modify-write race under concurrent
workers (two workers reading the same stale count, each writing back +1,
one increment lost — or each rolling over the day independently and
re-zeroing what the other just wrote). The CASE expression below does the
rollover-or-increment decision and the write in the one round trip Postgres
sees as a single statement.

  - Per-source (`Subprocessor.tier2_daily_count/date`, cap
    `TIER2_DAILY_PER_SOURCE`): the real cost control. Every source gets its
    own quota, so one misbehaving page retrying all day cannot starve every
    other source on the tenant out of Tier-2 for the day.
  - Per-tenant (`Tenant.tier2_daily_count/date`, cap `Tenant.tier2_daily_limit`):
    a safety valve, not a feature limit — sized well above what per-source
    quotas should ever add up to. Tripping it is abnormal and logged/alerted
    as such; see monitoring.py.

Both increments happen unconditionally (with rollover) and the caller then
checks the returned count against the limit — under a genuine race the
count can occasionally read one unit over its limit for that day rather
than losing an increment, which is the conservative failure mode for a cost
cap (tighter, never looser).
"""
from datetime import date

from sqlalchemy import case, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant


async def _atomic_spend(model, row_id, today: date, session: AsyncSession) -> int:
    stmt = (
        update(model)
        .where(model.id == row_id)
        .values(
            tier2_daily_count=case(
                (
                    or_(model.tier2_daily_date.is_(None), model.tier2_daily_date != today),
                    1,
                ),
                else_=model.tier2_daily_count + 1,
            ),
            tier2_daily_date=today,
        )
        .returning(model.tier2_daily_count)
    )
    result = await session.execute(stmt)
    new_count = result.scalar_one()
    await session.commit()
    return new_count


async def try_spend_source_budget(subprocessor: Subprocessor, today: date, session: AsyncSession) -> bool:
    """Atomically rolls the day over if needed and spends one Tier-2 run
    against this source's own quota. Returns whether the spend was within
    budget — a caller reading False must still treat the attempt as spent
    for the day (the conservative choice under a rare race) and queue the
    check for later, never skip it silently."""
    from app.core.config import settings

    new_count = await _atomic_spend(Subprocessor, subprocessor.id, today, session)
    subprocessor.tier2_daily_count = new_count
    subprocessor.tier2_daily_date = today
    return new_count <= settings.TIER2_DAILY_PER_SOURCE


async def try_spend_tenant_budget(tenant: Tenant, today: date, session: AsyncSession) -> bool:
    """Same, against the tenant-wide safety-valve pool."""
    new_count = await _atomic_spend(Tenant, tenant.id, today, session)
    tenant.tier2_daily_count = new_count
    tenant.tier2_daily_date = today
    return new_count <= tenant.tier2_daily_limit
