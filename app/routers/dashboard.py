import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.templating import templates as _templates
from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.session import get_db_session
from app.routers.deps import CurrentTenant
from app.core.llm.notice import ArticleNoticeDrafter
from app.services.approval import approve_change_event, reject_change_event
from app.services.evidence import evidence_csv, evidence_zip

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

_notice_drafter = ArticleNoticeDrafter()



@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Subprocessor)
        .where(Subprocessor.tenant_id == tenant.id)
        .order_by(Subprocessor.created_at.desc())
    )
    rows = list(result.scalars().all())

    trial_days_left: int | None = None
    if tenant.subscription_status == "trialing" and tenant.trial_ends_at is not None:
        trial_days_left = max(0, (tenant.trial_ends_at - utc_now()).days)

    return _templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "tenant": tenant,
            "rows": rows,
            "trial_days_left": trial_days_left,
            "subprocessor_limit": tenant.subprocessor_limit,
            "free_limit": settings.FREE_TIER_MAX_SUBPROCESSORS,
            "app_url": settings.APP_URL.rstrip("/"),
            "is_admin": bool(tenant.email) and tenant.email.lower() in settings.admin_email_set,
        },
    )


@router.get("/dashboard/queue", response_class=HTMLResponse)
async def queue(
    request: Request,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(
            ChangeEvent.status == ChangeStatus.pending_review.value,
            Subprocessor.tenant_id == tenant.id,
        )
        .options(selectinload(ChangeEvent.subprocessor))
        .order_by(ChangeEvent.created_at.desc())
    )
    events = list(result.scalars().all())
    return _templates.TemplateResponse(
        request, "queue.html", {"tenant": tenant, "events": events}
    )


@router.post("/dashboard/queue/{event_id}/approve", response_class=HTMLResponse)
async def approve_event(
    request: Request,
    event_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    ownership = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(ChangeEvent.id == event_id, Subprocessor.tenant_id == tenant.id)
    )
    if ownership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404)

    await approve_change_event(event_id, approved_by_user=tenant.slug, session=db)
    logger.info("Queue: event %s approved by tenant %s", event_id, tenant.slug)
    return _templates.TemplateResponse(
        request, "partials/change_event_done.html", {"action": "approved"}
    )


@router.post("/dashboard/queue/{event_id}/reject", response_class=HTMLResponse)
async def reject_event(
    request: Request,
    event_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    ownership = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(ChangeEvent.id == event_id, Subprocessor.tenant_id == tenant.id)
    )
    if ownership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404)

    await reject_change_event(event_id, rejected_by_user=tenant.slug, session=db)
    logger.info("Queue: event %s rejected by tenant %s", event_id, tenant.slug)
    return _templates.TemplateResponse(
        request, "partials/change_event_done.html", {"action": "rejected"}
    )


@router.get("/dashboard/events/{event_id}", response_class=HTMLResponse)
async def evidence_record(
    request: Request,
    event_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    """The auditable record for one detected change.

    The queue shows a diff, which answers "what moved". An auditor asks the
    other question — "what did the page actually say, and when" — so this
    page serves the stored before/after documents with their hashes and the
    decision trail.
    """
    event = await _event_for_tenant(event_id, tenant, db)
    return _templates.TemplateResponse(
        request, "evidence.html", {"tenant": tenant, "event": event}
    )


@router.get("/dashboard/events/{event_id}/evidence.zip")
async def evidence_bundle(
    event_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    """One change, as a downloadable audit pack: before/after HTML and text,
    the diff, and the decision/notice trail in a manifest — the file a
    tenant hands to their own auditor or an enterprise customer's security
    review, rather than a screenshot that only proves what the page said
    the week someone thought to capture it.

    Growth-tier only — Free and Starter still see the same record on the
    dashboard page itself, just not the exportable file.
    """
    if not tenant.may_export_evidence:
        raise HTTPException(
            status_code=402,
            detail="Downloadable audit evidence is part of the Growth plan.",
        )
    event = await _event_for_tenant(event_id, tenant, db)
    zip_bytes = evidence_zip(event, settings.APP_URL, tenant)

    filename = f"trustpages-audit-{event.subprocessor.name.lower().replace(' ', '-')}-{str(event.id)[:8]}.zip"
    logger.info("Evidence ZIP downloaded: event %s, tenant %s", event_id, tenant.slug)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/dashboard/evidence.csv")
async def evidence_export(
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    """Every recorded change as one CSV row — the file that goes to the audit.

    Page bodies are deliberately left out: they run to tens of thousands of
    characters and would make the file unreadable in a spreadsheet. The row
    carries both hashes and the record URL, which is what a reviewer follows
    to see the documents themselves.

    Growth-tier only, same reasoning as the ZIP endpoint above.
    """
    if not tenant.may_export_evidence:
        raise HTTPException(
            status_code=402,
            detail="CSV export is part of the Growth plan.",
        )
    result = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(Subprocessor.tenant_id == tenant.id)
        .options(selectinload(ChangeEvent.subprocessor))
        .order_by(ChangeEvent.created_at.desc())
    )
    events = list(result.scalars().all())

    csv_text = evidence_csv(events, settings.APP_URL)

    filename = f"trustpages-evidence-{tenant.slug}-{utc_now().strftime('%Y-%m-%d')}.csv"
    logger.info("Evidence export: %d rows for tenant %s", len(events), tenant.slug)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _event_for_tenant(event_id: UUID, tenant, db: AsyncSession) -> ChangeEvent:
    result = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(ChangeEvent.id == event_id, Subprocessor.tenant_id == tenant.id)
        .options(selectinload(ChangeEvent.subprocessor))
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404)
    return event


@router.get("/dashboard/events/{event_id}/notice", response_class=HTMLResponse)
async def notice_draft(
    request: Request,
    event_id: UUID,
    tenant: CurrentTenant,
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db_session),
):
    """The Article 28(2) notice the tenant owes their own customers.

    Detecting the change is only half the obligation — the DPA promises the
    customer a heads-up, and writing that from scratch is the part that gets
    skipped. Drafted once and stored: a notice that quietly rewords itself
    between views is worse than no notice, because the tenant may already
    have sent the earlier wording.
    """
    event = await _event_for_tenant(event_id, tenant, db)

    error: str | None = None
    # Drafting costs a model call, so it stays on the paid plan. An already
    # drafted notice remains readable after a downgrade — it may have been
    # sent, and taking it away would leave the tenant without their own record.
    if tenant.is_free_plan and event.notice_body is None:
        return _templates.TemplateResponse(
            request,
            "notice.html",
            {"tenant": tenant, "event": event, "error": None, "upgrade_required": True},
        )

    if event.notice_body is None or regenerate:
        try:
            draft = await _notice_drafter.draft(
                company=tenant.name,
                vendor=event.subprocessor.name,
                vendor_url=event.subprocessor.monitored_url,
                detected_on=event.created_at.strftime("%d %B %Y"),
                summary=event.llm_summary or "A change was detected on the vendor's page.",
                raw_diff=event.raw_diff[:12_000],
            )
            event.notice_subject = draft.subject
            event.notice_body = draft.body
            await db.commit()
            logger.info("Notice draft generated for event %s (tenant %s)", event_id, tenant.slug)
        except Exception:
            logger.exception("Notice draft failed for event %s", event_id)
            await db.rollback()
            # Deliberately not filled with placeholder prose — the tenant would
            # send it. An empty page with an error is the honest outcome.
            error = "The draft could not be generated. Try again in a moment."

    return _templates.TemplateResponse(
        request,
        "notice.html",
        {"tenant": tenant, "event": event, "error": error, "upgrade_required": False},
    )


@router.post("/dashboard/settings/badge", response_class=HTMLResponse)
async def toggle_badge(
    request: Request,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    """White-label switch for the trust page badge.

    Gated at write time as well as at render time: a free tenant who posts
    here directly gets a 402 rather than a silently ignored setting.
    """
    if not tenant.may_hide_badge:
        raise HTTPException(
            status_code=402,
            detail="Removing the TrustPages badge is part of the Growth plan.",
        )

    tenant.hide_powered_by = not tenant.hide_powered_by
    await db.commit()
    logger.info(
        "Badge setting: tenant %s hide_powered_by=%s", tenant.slug, tenant.hide_powered_by
    )
    return _templates.TemplateResponse(
        request, "partials/badge_setting.html", {"tenant": tenant}
    )
