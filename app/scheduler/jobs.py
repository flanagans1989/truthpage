import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.services.monitoring import run_subprocessor_check

logger = logging.getLogger(__name__)

_BILLABLE_STATUSES = ("active", "trialing")


async def sweep_due_subprocessors(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """
    Sweeper job: finds all subprocessors whose check window has elapsed
    and dispatches a monitoring cycle for each. One subprocessor failure
    never aborts the whole sweep.
    """
    now = utc_now()

    async with session_factory() as session:
        result = await session.execute(
            select(Subprocessor)
            .join(Subprocessor.tenant)
            .where(
                Subprocessor.monitoring_enabled == True,  # noqa: E712
                Tenant.subscription_status.in_(_BILLABLE_STATUSES),
                (Subprocessor.next_check_at <= now) | (Subprocessor.next_check_at == None),  # noqa: E711
            )
            .options(selectinload(Subprocessor.tenant))
        )
        due: list[Subprocessor] = list(result.scalars().all())

    if not due:
        logger.debug("Sweep: no subprocessors due at %s", now.isoformat())
        return

    logger.info("Sweep: %d subprocessor(s) due — starting checks", len(due))

    for subprocessor in due:
        async with session_factory() as session:
            try:
                await run_subprocessor_check(subprocessor.id, session)
                logger.info("Sweep: completed check for subprocessor %s", subprocessor.id)
            except Exception:
                logger.exception(
                    "Sweep: unhandled error for subprocessor %s — skipping", subprocessor.id
                )
