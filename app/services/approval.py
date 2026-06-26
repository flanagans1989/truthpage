import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.services.mailer import mailer

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {ChangeStatus.approved.value, ChangeStatus.rejected.value}


async def approve_change_event(
    change_event_id: UUID,
    approved_by_user: str,
    session: AsyncSession,
) -> None:
    result = await session.execute(
        select(ChangeEvent)
        .where(ChangeEvent.id == change_event_id)
        .options(
            selectinload(ChangeEvent.subprocessor).selectinload(Subprocessor.tenant)
        )
    )
    event: ChangeEvent | None = result.scalar_one_or_none()

    if event is None:
        logger.warning("approve_change_event: ChangeEvent %s not found", change_event_id)
        return

    if event.status in _TERMINAL_STATUSES:
        logger.info(
            "approve_change_event: ChangeEvent %s already in terminal status '%s', skipping",
            change_event_id,
            event.status,
        )
        return

    now = utc_now()
    event.status = ChangeStatus.approved.value
    event.approved_by = approved_by_user
    event.approved_at = now

    subprocessor = event.subprocessor
    if subprocessor.last_content_hash != event.new_hash:
        subprocessor.last_content_hash = event.new_hash

    # Collect active confirmed subscribers before committing (session still open)
    sub_result = await session.execute(
        select(Subscriber.email, Subscriber.unsubscribe_token).where(
            Subscriber.tenant_id == subprocessor.tenant_id,
            Subscriber.confirmed == True,  # noqa: E712
            Subscriber.is_active == True,  # noqa: E712
        )
    )
    recipients: list[tuple[str, str]] = [
        (row[0], f"{settings.APP_URL}/trust/unsubscribe?token={row[1]}")
        for row in sub_result.all()
    ]

    if recipients:
        event.notified_at = now

    await session.commit()
    logger.info(
        "approve_change_event: ChangeEvent %s approved by '%s'",
        change_event_id,
        approved_by_user,
    )

    if recipients:
        asyncio.create_task(
            mailer.send_change_notification(
                recipients=recipients,
                tenant_name=subprocessor.tenant.name,
                subprocessor_name=subprocessor.name,
                summary=event.llm_summary or "A change was detected in the privacy policy.",
            )
        )
        logger.info(
            "approve_change_event: queued change_notification for %d subscriber(s)",
            len(recipients),
        )


async def reject_change_event(
    change_event_id: UUID,
    rejected_by_user: str,
    session: AsyncSession,
) -> None:
    result = await session.execute(
        select(ChangeEvent)
        .where(ChangeEvent.id == change_event_id)
    )
    event: ChangeEvent | None = result.scalar_one_or_none()

    if event is None:
        logger.warning("reject_change_event: ChangeEvent %s not found", change_event_id)
        return

    if event.status in _TERMINAL_STATUSES:
        logger.info(
            "reject_change_event: ChangeEvent %s already in terminal status '%s', skipping",
            change_event_id,
            event.status,
        )
        return

    now = utc_now()
    event.status = ChangeStatus.rejected.value
    event.approved_by = rejected_by_user
    event.approved_at = now

    await session.commit()
    logger.info(
        "reject_change_event: ChangeEvent %s rejected by '%s'",
        change_event_id,
        rejected_by_user,
    )
