import logging

from sqlalchemy import nullsfirst, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.system_state import (
    SWEEP_LAST_COMPLETED_AT,
    SWEEP_LAST_ERROR,
    SWEEP_LAST_STARTED_AT,
)
from app.db.models.tenant import MONITORED_STATUSES, Tenant
from app.services.directory import sweep_due_vendors
from app.services.monitoring import run_subprocessor_check
from app.services.plans import move_tenant_to_free
from app.services.system_state import record_state
from app.services.tsa_retry import run_timestamp_retry_pass

logger = logging.getLogger(__name__)



async def downgrade_expired_trials(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Move trials that have run out onto the permanent free plan.

    Runs before the sweep so a tenant who expired overnight is charged no
    scrapes beyond their free allowance in the same tick. Pages above the
    free limit are switched off rather than deleted — upgrading turns them
    back on with their history intact.
    """
    now = utc_now()
    async with session_factory() as session:
        result = await session.execute(
            select(Tenant)
            .where(
                Tenant.subscription_status == "trialing",
                Tenant.trial_ends_at != None,  # noqa: E711
                Tenant.trial_ends_at <= now,
            )
        )
        expired = list(result.scalars().all())
        if not expired:
            return

        for tenant in expired:
            # The operator's own tenant is the showcase trust page, not a
            # customer on a trial. Downgrading it would switch off half the
            # vendors on the page we hand to prospects.
            if tenant.email and tenant.email.lower() in settings.admin_email_set:
                logger.info("Trial expiry: skipping admin tenant %s", tenant.slug)
                continue
            switched_off = await move_tenant_to_free(tenant, session)
            logger.info(
                "Trial expired for tenant %s — moved to free plan, %d page(s) switched off",
                tenant.slug,
                switched_off,
            )

        await session.commit()


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
                Tenant.subscription_status.in_(MONITORED_STATUSES),
                or_(
                    Tenant.subscription_status != "trialing",
                    # Legacy rows without a trial end keep working until claimed;
                    # a lapsed trial is moved to "free" by downgrade_expired_trials
                    # before this query runs.
                    (Tenant.trial_ends_at == None) | (Tenant.trial_ends_at > now),  # noqa: E711
                ),
                (Subprocessor.next_check_at <= now) | (Subprocessor.next_check_at == None),  # noqa: E711
            )
            .options(selectinload(Subprocessor.tenant))
            # Least-recently-checked first — makes starvation structurally
            # impossible: whatever eats the day's Tier-2 budget first is,
            # by construction, whatever has gone longest without a look.
            .order_by(nullsfirst(Subprocessor.last_checked_at))
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


async def run_sweep_cycle(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """One tick of the monitor: settle plan transitions, retry any pending
    RFC 3161 timestamps, then check what is due.

    Order matters — a trial that lapsed since the last tick must land on the
    free plan first, or this tick would still scrape its whole vendor list.
    Customers come before the public directory: if the tick runs long, the
    pages someone is paying for are the ones already done. The timestamp
    retry pass runs early and is fully independent of everything after it —
    a slow or unreachable TSA never delays or breaks the scrape itself.
    """
    started = utc_now()
    await record_state(session_factory, SWEEP_LAST_STARTED_AT)

    try:
        await downgrade_expired_trials(session_factory)
        await run_timestamp_retry_pass(session_factory)
        await sweep_due_subprocessors(session_factory)
        await sweep_due_vendors(session_factory)
    except Exception as exc:
        # Individual source failures are already contained inside each pass;
        # reaching here means the cycle itself broke. Record why, then
        # re-raise so APScheduler and Sentry both see it. The completion
        # heartbeat is deliberately NOT written: /healthz/monitoring must
        # go degraded rather than report a cycle that did not finish.
        await record_state(session_factory, SWEEP_LAST_ERROR, value=repr(exc)[:2000])
        raise

    duration = (utc_now() - started).total_seconds()
    await record_state(
        session_factory, SWEEP_LAST_COMPLETED_AT, value=f"{duration:.1f}s"
    )
    # Cleared only on a clean cycle, so a stale error never lingers as a
    # false alarm once the underlying problem is gone.
    await record_state(session_factory, SWEEP_LAST_ERROR, value=None)
    logger.info("Sweep cycle completed in %.1fs", duration)
