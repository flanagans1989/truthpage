"""RFC 3161 timestamping pass — runs at the start of every existing sweep
tick (see app/scheduler/jobs.py), never a separate worker/queue/broker.
Fully independent of the scraping pass in the same cycle: a TSA outage
never blocks, slows, or fails a monitoring check.

KURAL 0 (absolute): no code path here may ever attach a timestamp to a
change_event whose timestamp_status is not_available_pre_tsa. That status
is terminal — see docs/manifest_v2.md and TimestampStatus's docstring.
stamp_change_event() enforces this as a hard trip-wire, not a soft check
the caller could bypass.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.tsa import TSAError, request_timestamp
from app.db.models.change_event import ChangeEvent, TimestampStatus
from app.db.models.mixins import utc_now

logger = logging.getLogger(__name__)

_DUE_STATUSES = (TimestampStatus.pending.value, TimestampStatus.retrying.value)


class BackdatedTimestampError(RuntimeError):
    """Refused: a pre-TSA record must never receive a timestamp token —
    doing so would assert a document existed at a time it did not."""


async def stamp_change_event(event: ChangeEvent, session: AsyncSession) -> None:
    """Attempts exactly one timestamp round for `event`: primary TSA, then
    the fallback if one is configured. Commits the resulting state
    (timestamped / retrying / failed) itself."""
    if event.timestamp_status == TimestampStatus.not_available_pre_tsa.value:
        raise BackdatedTimestampError(
            f"refusing to timestamp change_event {event.id}: its status is "
            "not_available_pre_tsa (recorded before independent timestamping "
            "existed) — backdated timestamping is never allowed"
        )

    if event.new_raw_html_hash is None:
        # Nothing to stamp (an event from before raw-HTML hashing existed).
        # Same terminal status as pre-TSA — there is no digest to ever send.
        event.timestamp_status = TimestampStatus.not_available_pre_tsa.value
        await session.commit()
        return

    attempt = event.tsa_attempt_count + 1
    urls = [settings.TSA_PRIMARY_URL]
    if settings.TSA_FALLBACK_URL:
        urls.append(settings.TSA_FALLBACK_URL)

    last_error: str | None = None
    for url in urls:
        try:
            tsr_bytes, tsa_time = await request_timestamp(
                event.new_raw_html_hash, url, settings.TSA_TIMEOUT_SECONDS
            )
        except TSAError as exc:
            last_error = str(exc)
            logger.warning("TSA request to %s failed for change_event %s: %s", url, event.id, exc)
            continue

        event.timestamp_status = TimestampStatus.timestamped.value
        event.tsa_token = tsr_bytes
        event.tsa_authority_url = url
        event.tsa_time_utc = tsa_time
        event.tsa_attempt_count = attempt
        event.tsa_last_error = None
        await session.commit()
        logger.info("Timestamped change_event %s via %s (attempt %d)", event.id, url, attempt)
        return

    # Every configured TSA failed this attempt.
    event.tsa_attempt_count = attempt
    event.tsa_last_error = last_error
    if attempt >= settings.TSA_MAX_ATTEMPTS:
        event.timestamp_status = TimestampStatus.failed.value
        logger.warning(
            "Timestamping failed permanently for change_event %s after %d attempts: %s",
            event.id, attempt, last_error,
        )
    else:
        event.timestamp_status = TimestampStatus.retrying.value
    await session.commit()


async def run_timestamp_retry_pass(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Finds every change_event due for a timestamp attempt (`pending` or
    `retrying`) and gives each exactly one attempt this tick. One event's
    failure never aborts the pass for the rest."""
    async with session_factory() as session:
        result = await session.execute(
            select(ChangeEvent).where(ChangeEvent.timestamp_status.in_(_DUE_STATUSES))
        )
        due_ids = [row.id for row in result.scalars().all()]

    if not due_ids:
        logger.debug("TSA retry pass: nothing due at %s", utc_now().isoformat())
        return

    logger.info("TSA retry pass: %d change event(s) due", len(due_ids))
    for event_id in due_ids:
        async with session_factory() as session:
            event = await session.get(ChangeEvent, event_id)
            if event is None:
                continue
            try:
                await stamp_change_event(event, session)
            except Exception:
                logger.exception("TSA retry pass: unhandled error for change_event %s", event_id)
