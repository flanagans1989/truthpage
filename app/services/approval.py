import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.llm.notice import ArticleNoticeDrafter, notice_preview_token, resolve_notice_placeholders
from app.db.models.change_event import (
    REVIEW_ACTION_NOTICE_RELEASED,
    ChangeEvent,
    ChangeStatus,
)
from app.db.models.mixins import utc_now
from app.db.models.notification import NotificationRecipient
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.services.mailer import mailer

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {ChangeStatus.approved.value, ChangeStatus.rejected.value}

_notice_drafter = ArticleNoticeDrafter()


async def approve_change_event(
    change_event_id: UUID,
    approved_by_user: str,
    session: AsyncSession,
) -> None:
    """Records the decision that this change is real and should be
    published — nothing more. Releasing and sending its customer notice is
    a separate, later, explicit act (see release_notice below): approving
    a change is not the same claim as "a human read the final notice text
    and the recipient count, and chose to send it".
    """
    result = await session.execute(
        select(ChangeEvent)
        .where(ChangeEvent.id == change_event_id)
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

    await session.commit()
    logger.info("approve_change_event: ChangeEvent %s approved by '%s'", change_event_id, approved_by_user)


async def confirmed_recipients(tenant_id, session: AsyncSession) -> list[tuple[str, str]]:
    """(email, unsubscribe_url) for every confirmed, active subscriber of
    a tenant — the same query release_notice actually sends to, so a
    preview showing "this will reach N people" is never a different query
    than the one that fires."""
    sub_result = await session.execute(
        select(Subscriber.email, Subscriber.unsubscribe_token).where(
            Subscriber.tenant_id == tenant_id,
            Subscriber.confirmed == True,  # noqa: E712
            Subscriber.is_active == True,  # noqa: E712
        )
    )
    return [
        (row[0], f"{settings.APP_URL}/trust/unsubscribe?token={row[1]}")
        for row in sub_result.all()
    ]


async def release_notice(
    change_event_id: UUID,
    reviewer_name: str,
    reviewer_email: str,
    notice_body_preview_token: str,
    session: AsyncSession,
) -> str | None:
    """The explicit, separate "send" action — freezes the notice, records
    who released it, and sends it to every confirmed active subscriber.
    Returns an error string (not raised) if it couldn't proceed; None on
    success.

    `notice_body_preview_token` must equal notice_preview_token(event.
    notice_body) at the moment this is called — the hash of the EXACT
    text the reviewer's page rendered. This is what makes "you cannot send
    without having seen the final text" a real, server-enforced guarantee
    rather than a UI convention: a stale page (or a hand-crafted request
    that never loaded the current draft) is refused, not silently sent
    against whatever text happens to be in the database right now.
    """
    result = await session.execute(
        select(ChangeEvent)
        .where(ChangeEvent.id == change_event_id)
        .options(
            selectinload(ChangeEvent.subprocessor).selectinload(Subprocessor.tenant)
        )
    )
    event: ChangeEvent | None = result.scalar_one_or_none()

    if event is None:
        return "This change no longer exists."
    if event.status != ChangeStatus.approved.value:
        return "Approve this change before releasing its notice."
    if event.review_action is not None:
        return "This notice has already been released — it cannot be sent again."
    if event.notice_body is None:
        return "Draft the notice before releasing it."
    if notice_preview_token(event.notice_body) != notice_body_preview_token:
        return (
            "The notice text has changed since you loaded this page — "
            "reload it and try again."
        )

    now = utc_now()
    subprocessor = event.subprocessor
    tenant = subprocessor.tenant

    recipients = await confirmed_recipients(subprocessor.tenant_id, session)

    event.reviewed_by_name = reviewer_name
    event.reviewed_by_email = reviewer_email
    event.reviewed_at = now
    event.review_action = REVIEW_ACTION_NOTICE_RELEASED
    resolved_subject, resolved_body = resolve_notice_placeholders(
        subject=event.notice_subject,
        body=event.notice_body,
        window_days=tenant.objection_window_days,
        contact_email=tenant.objection_contact_email,
    )
    event.notice_frozen_subject = resolved_subject
    event.notice_frozen_body = resolved_body
    event.notice_frozen_at = now
    event.recipient_count = len(recipients)

    if recipients:
        # sent_at (manifest) and window_opened_at (objection window) are
        # both this same instant — reusing notified_at rather than adding
        # a second column for the same value.
        event.notified_at = now
        event.window_days = tenant.objection_window_days
        event.window_closes_at = now + timedelta(days=tenant.objection_window_days)

    await session.commit()
    logger.info(
        "release_notice: ChangeEvent %s released by %s (%d recipient(s))",
        change_event_id, reviewer_email, len(recipients),
    )

    if recipients:
        send_results = await mailer.send_notice(
            recipients=recipients,
            tenant_name=tenant.name,
            reply_to=tenant.objection_contact_email,
            subject=resolved_subject,
            body=resolved_body,
        )
        for result_row in send_results:
            session.add(
                NotificationRecipient(
                    change_event_id=event.id,
                    recipient_email=result_row["email"],
                    resend_message_id=result_row["resend_message_id"],
                    send_error=result_row["error"],
                )
            )
        await session.commit()
        sent = sum(1 for r in send_results if r["error"] is None)
        logger.info(
            "release_notice: notice sent %d/%d for ChangeEvent %s", sent, len(send_results), change_event_id,
        )

    return None


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
