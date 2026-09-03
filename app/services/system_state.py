"""Read/write helpers for the system_state heartbeat table.

Every write here is best-effort and self-contained: a heartbeat that fails
to record must never abort the sweep it is describing. A missing heartbeat
degrades the health probe, which is the correct, visible failure — a
raised exception here would take down the very cycle we are trying to
prove ran.
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.mixins import utc_now
from app.db.models.system_state import SystemState

logger = logging.getLogger(__name__)


async def get_state(session: AsyncSession, key: str) -> SystemState | None:
    result = await session.execute(select(SystemState).where(SystemState.key == key))
    return result.scalar_one_or_none()


async def set_state(
    session: AsyncSession,
    key: str,
    *,
    value: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    """Upsert one key. Caller commits.

    Read-then-write rather than a dialect-specific ON CONFLICT: the test
    suite runs on SQLite and production on Postgres, and there is exactly
    one writer (the sweep), so the race this gives up does not exist.
    """
    when = occurred_at or utc_now()
    existing = await get_state(session, key)
    if existing is None:
        session.add(SystemState(key=key, value=value, occurred_at=when))
    else:
        existing.value = value
        existing.occurred_at = when


async def record_state(
    session_factory: async_sessionmaker[AsyncSession],
    key: str,
    *,
    value: str | None = None,
) -> None:
    """Fire-and-forget write on its own session and transaction.

    Deliberately swallows everything: see the module docstring. The sweep
    must survive a database hiccup in its own bookkeeping.
    """
    try:
        async with session_factory() as session:
            await set_state(session, key, value=value)
            await session.commit()
    except Exception:
        logger.exception("system_state: failed to record %s", key)
