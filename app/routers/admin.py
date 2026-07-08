import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.change_event import ChangeEvent
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.routers.deps import CurrentAdmin
from app.services.admin_stats import collect_admin_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


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
