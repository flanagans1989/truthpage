import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.templating import templates as _templates
from app.core.urlguard import validate_url
from app.db.models.subprocessor import Subprocessor
from app.db.session import get_db_session
from app.routers.deps import CurrentTenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/subprocessors", tags=["subprocessors"])


async def _load_subprocessors(tenant_id: UUID, db: AsyncSession) -> list[Subprocessor]:
    result = await db.execute(
        select(Subprocessor)
        .where(Subprocessor.tenant_id == tenant_id)
        .order_by(Subprocessor.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_class=HTMLResponse)
async def create_subprocessor(
    request: Request,
    tenant: CurrentTenant,
    name: str = Form(...),
    monitored_url: str = Form(...),
    check_interval_minutes: int = Form(1440, ge=60, le=43200),
    db: AsyncSession = Depends(get_db_session),
):
    count_result = await db.execute(
        select(func.count()).select_from(Subprocessor).where(Subprocessor.tenant_id == tenant.id)
    )
    limit = tenant.subprocessor_limit
    if count_result.scalar_one() >= limit:
        # 200, not 422: this is an htmx request whose hx-target is the table,
        # and a non-2xx response there swaps in nothing rather than showing
        # the tenant why nothing happened. The table re-renders unchanged and
        # the upgrade modal rides along as an out-of-band swap — see
        # partials/limit_reached.html.
        logger.info(
            "Subprocessor add blocked at plan limit (%d) for tenant %s", limit, tenant.id
        )
        rows = await _load_subprocessors(tenant.id, db)
        return _templates.TemplateResponse(
            request, "partials/limit_reached.html", {"rows": rows, "limit": limit}
        )

    await validate_url(monitored_url)
    subprocessor = Subprocessor(
        tenant_id=tenant.id,
        name=name,
        monitored_url=monitored_url,
        check_interval_minutes=check_interval_minutes,
    )
    db.add(subprocessor)
    await db.commit()
    logger.info("Created subprocessor '%s' for tenant %s", name, tenant.id)

    rows = await _load_subprocessors(tenant.id, db)
    return _templates.TemplateResponse(request, "partials/subprocessor_table.html", {"rows": rows})


@router.post("/{subprocessor_id}/toggle", response_class=HTMLResponse)
async def toggle_subprocessor(
    request: Request,
    subprocessor_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Subprocessor).where(
            Subprocessor.id == subprocessor_id,
            Subprocessor.tenant_id == tenant.id,
        )
    )
    sp = result.scalar_one_or_none()
    if sp is None:
        raise HTTPException(status_code=404, detail="Not found")

    sp.monitoring_enabled = not sp.monitoring_enabled
    await db.commit()
    logger.info(
        "Subprocessor %s monitoring_enabled set to %s", subprocessor_id, sp.monitoring_enabled
    )

    rows = await _load_subprocessors(tenant.id, db)
    return _templates.TemplateResponse(request, "partials/subprocessor_table.html", {"rows": rows})


@router.post("/{subprocessor_id}/delete", response_class=HTMLResponse)
async def delete_subprocessor(
    request: Request,
    subprocessor_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Subprocessor).where(
            Subprocessor.id == subprocessor_id,
            Subprocessor.tenant_id == tenant.id,
        )
    )
    sp = result.scalar_one_or_none()
    if sp is None:
        raise HTTPException(status_code=404, detail="Not found")

    await db.delete(sp)
    await db.commit()
    logger.info("Deleted subprocessor %s for tenant %s", subprocessor_id, tenant.id)

    rows = await _load_subprocessors(tenant.id, db)
    return _templates.TemplateResponse(request, "partials/subprocessor_table.html", {"rows": rows})
