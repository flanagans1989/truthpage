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
from app.services.approval import approve_change_event, reject_change_event
from app.services.evidence import evidence_csv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])



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
    result = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(ChangeEvent.id == event_id, Subprocessor.tenant_id == tenant.id)
        .options(selectinload(ChangeEvent.subprocessor))
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404)

    return _templates.TemplateResponse(
        request, "evidence.html", {"tenant": tenant, "event": event}
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
    """
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
