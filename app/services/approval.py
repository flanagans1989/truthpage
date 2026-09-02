import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.llm.notice import ArticleNoticeDrafter, resolve_notice_placeholders
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
    reviewer_name: str,
    reviewer_email: str,
    session: AsyncSession,
) -> str | None:
    """Approves a material change and, in the same action, releases and
    sends its Article 28(2) notice — see docs/manifest_v2.md's [REVIEW]/
    [NOTIFICATION]/[OBJECTION WINDOW] sections for what this freezes and
    why. Returns an error string if the notice couldn't be drafted (the
    approval itself still goes through — a tenant should not be stuck
    unable to record a decision because a model call failed; they can
    retry from /dashboard/events/{id}/notice, which the queue links to).
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
        logger.warning("approve_change_event: ChangeEvent %s not found", change_event_id)
        return None

    if event.status in _TERMINAL_STATUSES:
        logger.info(
            "approve_change_event: ChangeEvent %s already in terminal status '%s', skipping",
            change_event_id,
            event.status,
        )
        return None

    now = utc_now()
    event.status = ChangeStatus.approved.value
    event.approved_by = approved_by_user
    event.approved_at = now
    event.reviewed_by_name = reviewer_name
    event.reviewed_by_email = reviewer_email
    event.reviewed_at = now

    # NOTE: subprocessor.last_content_hash is already advanced by the
    # monitoring cycle at detection time. Re-writing it here from an older
    # event would roll the baseline backwards and re-trigger the same diff.
    subprocessor = event.subprocessor
    tenant = subprocessor.tenant

    if event.notice_body is None:
        try:
            draft = await _notice_drafter.draft(
                company=tenant.name,
                vendor=subprocessor.name,
                vendor_url=subprocessor.monitored_url,
                detected_on=event.created_at.strftime("%d %B %Y"),
                summary=event.llm_summary or "A change was detected on the vendor's page.",
                raw_diff=event.raw_diff[:12_000],
            )
            event.notice_subject = draft.subject
            event.notice_body = draft.body
        except Exception:
            logger.exception(
                "approve_change_event: notice draft failed for %s — approval recorded, "
                "no notice released",
                change_event_id,
            )
            await session.commit()
            return (
                "Approved, but the customer notice could not be drafted — no notice was "
                "sent. Draft and release it from the notice page."
            )

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

    event.review_action = REVIEW_ACTION_NOTICE_RELEASED
    resolved_subject, resolved_body = resolve_notice_placeholders(
        subject=event.notice_subject,
        body=event.notice_body,
        window_days=tenant.objection_window_days,
        contact_email=tenant.email or "",
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
        "approve_change_event: ChangeEvent %s approved by '%s', reviewed by %s",
        change_event_id,
        approved_by_user,
        reviewer_email,
    )

    if recipients:
        send_results = await mailer.send_notice(
            recipients=recipients,
            tenant_name=tenant.name,
            reply_to=tenant.email or "",
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
            "approve_change_event: notice sent %d/%d for ChangeEvent %s",
            sent,
            len(send_results),
            change_event_id,
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
