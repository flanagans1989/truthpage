import asyncio
import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.subprocessor import Subprocessor
from app.db.session import get_db_session
from app.routers.deps import CurrentTenant

_RESERVED_HOSTNAMES = frozenset({"localhost", "metadata.google.internal"})


def _is_forbidden_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return addr.is_private or addr.is_link_local or addr.is_loopback or addr.is_reserved


def _validate_monitored_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="Only http/https URLs are allowed")
    host = parsed.hostname or ""
    if not host:
        raise HTTPException(status_code=422, detail="Invalid URL: missing host")
    if host in _RESERVED_HOSTNAMES:
        raise HTTPException(status_code=422, detail="Reserved hostname not allowed")
    try:
        addr = ipaddress.ip_address(host)
        if _is_forbidden_ip(addr):
            raise HTTPException(status_code=422, detail="Private/reserved IP addresses are not allowed")
        return
    except ValueError:
        pass  # hostname, not a raw IP — resolve it below

    # Resolve the hostname so e.g. 169.254.169.254.nip.io can't reach cloud
    # metadata. Not airtight against DNS rebinding, but blocks the easy path.
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise HTTPException(status_code=422, detail="Hostname could not be resolved")
    for info in infos:
        resolved = ipaddress.ip_address(info[4][0])
        if _is_forbidden_ip(resolved):
            raise HTTPException(status_code=422, detail="Hostname resolves to a private/reserved address")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/subprocessors", tags=["subprocessors"])
_templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


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
    if count_result.scalar_one() >= settings.MAX_SUBPROCESSORS_PER_TENANT:
        raise HTTPException(
            status_code=422,
            detail=f"Plan limit reached ({settings.MAX_SUBPROCESSORS_PER_TENANT} monitored URLs). "
            "Contact support to increase it.",
        )

    # DNS resolution inside is blocking — run off the event loop
    await asyncio.to_thread(_validate_monitored_url, monitored_url)
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
