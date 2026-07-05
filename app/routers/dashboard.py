import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.session import get_db_session
from app.routers.deps import CurrentTenant
from app.services.approval import approve_change_event, reject_change_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

_templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


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
        {"tenant": tenant, "rows": rows, "trial_days_left": trial_days_left},
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
