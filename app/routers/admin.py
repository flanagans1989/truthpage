import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.llm.outreach import OutreachDrafter
from app.core.templating import templates as _templates
from app.db.models.change_event import ChangeEvent
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.routers.deps import CurrentAdmin
from app.services.admin_stats import collect_admin_stats

logger = logging.getLogger(__name__)

_outreach_drafter = OutreachDrafter()

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def admin_overview(
    request: Request,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db_session),
):
    stats = await collect_admin_stats(db)
    return _templates.TemplateResponse(
        request, "admin.html", {"admin": admin, **stats}
    )


@router.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def admin_tenant_detail(
    request: Request,
    tenant_id: UUID,
    admin: CurrentAdmin,
    db: AsyncSession = Depends(get_db_session),
):
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404)

    subprocessors = list((await db.execute(
        select(Subprocessor)
        .where(Subprocessor.tenant_id == tenant_id)
        .order_by(Subprocessor.created_at.desc())
    )).scalars().all())

    events = list((await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(Subprocessor.tenant_id == tenant_id)
        .options(selectinload(ChangeEvent.subprocessor))
        .order_by(ChangeEvent.created_at.desc())
        .limit(20)
    )).scalars().all())

    subscribers = list((await db.execute(
        select(Subscriber)
        .where(Subscriber.tenant_id == tenant_id)
        .order_by(Subscriber.created_at.desc())
    )).scalars().all())

    return _templates.TemplateResponse(
        request,
        "admin_tenant.html",
        {
            "admin": admin,
            "tenant": tenant,
            "subprocessors": subprocessors,
            "events": events,
            "subscribers": subscribers,
        },
    )


@router.get("/outreach", response_class=HTMLResponse)
async def outreach_form(request: Request, admin: CurrentAdmin):
    return _templates.TemplateResponse(
        request, "admin_outreach.html", {"admin": admin, "draft": None, "error": None}
    )


@router.post("/outreach", response_class=HTMLResponse)
async def outreach_generate(
    request: Request,
    admin: CurrentAdmin,
    company: str = Form(...),
    founder: str = Form(...),
    vendor1: str = Form(...),
    vendor2: str = Form(...),
):
    """Drafts three cold-outreach angles, in English and German, for a
    named prospect. Never sends anything — the admin reads, edits and
    sends each one by hand from their own LinkedIn/email account."""
    form = {"company": company, "founder": founder, "vendor1": vendor1, "vendor2": vendor2}
    try:
        draft = await _outreach_drafter.draft(
            company=company, founder=founder, vendor1=vendor1, vendor2=vendor2
        )
    except Exception:
        logger.exception("Outreach draft failed for target '%s'", company)
        return _templates.TemplateResponse(
            request,
            "admin_outreach.html",
            {"admin": admin, "draft": None, "error": "Draft failed — try again in a moment.", "form": form},
        )

    logger.info("Outreach drafted by admin %s for target '%s'", admin.slug, company)
    return _templates.TemplateResponse(
        request,
        "admin_outreach.html",
        {"admin": admin, "draft": draft, "error": None, "form": form},
    )
