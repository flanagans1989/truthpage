"""The wizard a new tenant lands in: pick, import, publish.

Everything here is a step towards one thing — a public trust page that
exists sixty seconds after signing in. Each step commits on its own, so a
tenant who closes the tab after picking four providers keeps those four; the
wizard reopens where they left it rather than starting over.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.provider_library import PROVIDERS, grouped, normalise_name
from app.core.ratelimit import SlidingWindowLimiter
from app.core.templating import templates as _templates
from app.core.urlguard import validate_url
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.session import get_db_session
from app.routers.deps import CurrentTenant
from app.services.onboarding import add_providers, existing_keys, import_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Each import is a fetch plus a model call, both paid for by us and both
# triggerable from a form. Generous enough for a real onboarding session
# (policy, then a corrected URL, then a paste), tight enough to bound abuse.
_import_limiter = SlidingWindowLimiter(max_requests=6, window_seconds=300)


async def _tenant_rows(tenant_id, db: AsyncSession) -> list[Subprocessor]:
    return list(
        (
            await db.execute(
                select(Subprocessor)
                .where(Subprocessor.tenant_id == tenant_id)
                .order_by(Subprocessor.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def _state(request: Request, tenant, db: AsyncSession, **extra):
    """The shared context every wizard render needs."""
    rows = await _tenant_rows(tenant.id, db)
    added = await existing_keys(tenant.id, db)
    context = {
        "tenant": tenant,
        "rows": rows,
        # Slugs, not names: the picker needs to know which of *its own* cards
        # are already on the list, and a card is identified by its slug.
        "chosen": {p["slug"] for p in PROVIDERS if normalise_name(p["name"]) in added},
        "groups": grouped(),
        "limit": tenant.subprocessor_limit,
        "remaining": max(0, tenant.subprocessor_limit - len(rows)),
        "app_url": settings.APP_URL.rstrip("/"),
    }
    context.update(extra)
    return context


@router.get("", response_class=HTMLResponse)
async def wizard(
    request: Request,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    return _templates.TemplateResponse(
        request, "onboarding.html", await _state(request, tenant, db)
    )


@router.post("/library", response_class=HTMLResponse)
async def add_from_library(
    request: Request,
    tenant: CurrentTenant,
    slugs: list[str] = Form(default=[]),
    db: AsyncSession = Depends(get_db_session),
):
    """Checked boxes → monitored pages. Over-cap picks are reported, not fatal."""
    result = await add_providers(slugs, tenant, db)
    return _templates.TemplateResponse(
        request,
        "partials/onboarding_state.html",
        await _state(request, tenant, db, add_result=result),
    )


@router.post("/custom", response_class=HTMLResponse)
async def add_custom(
    request: Request,
    tenant: CurrentTenant,
    name: str = Form(...),
    monitored_url: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    """A vendor the library does not know — the tenant supplies the URL.

    This is also where an imported name that we could not match ends up, which
    is why it takes a name rather than a slug.
    """
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")

    rows = await _tenant_rows(tenant.id, db)
    if len(rows) >= tenant.subprocessor_limit:
        return _templates.TemplateResponse(
            request,
            "partials/onboarding_state.html",
            await _state(
                request, tenant, db,
                error=f"You are at your plan's limit of {tenant.subprocessor_limit} pages.",
            ),
        )

    if normalise_name(name) in await existing_keys(tenant.id, db):
        return _templates.TemplateResponse(
            request,
            "partials/onboarding_state.html",
            await _state(request, tenant, db, error=f"{name} is already on your list."),
        )

    await validate_url(monitored_url.strip())
    db.add(
        Subprocessor(
            tenant_id=tenant.id,
            name=name,
            monitored_url=monitored_url.strip(),
            check_interval_minutes=1440,
        )
    )
    await db.commit()
    logger.info("Onboarding: tenant %s added custom vendor '%s'", tenant.slug, name)
    return _templates.TemplateResponse(
        request,
        "partials/onboarding_state.html",
        await _state(request, tenant, db),
    )


@router.post("/import", response_class=HTMLResponse)
async def import_policy(
    request: Request,
    tenant: CurrentTenant,
    policy_url: str = Form(default=""),
    policy_text: str = Form(default=""),
    db: AsyncSession = Depends(get_db_session),
):
    """Read the tenant's own policy and offer what it names.

    Nothing is written here. The tenant sees what we found and decides — an
    importer that silently added rows would put vendors on a public page
    without anyone having read them.
    """
    if not _import_limiter.allow(f"tenant:{tenant.id}"):
        return _templates.TemplateResponse(
            request,
            "partials/onboarding_import.html",
            {"result": None, "error": "That's a lot of imports in a row — give it a minute."},
        )

    result = await import_candidates(
        url=policy_url, pasted=policy_text, tenant_id=tenant.id, db=db
    )
    return _templates.TemplateResponse(
        request,
        "partials/onboarding_import.html",
        {"result": result, "error": result.error},
    )


@router.post("/publish")
async def publish(
    tenant: CurrentTenant,
    company_name: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    """One click, and the page is public.

    Until this runs, /trust/{slug} answers 404: a list someone is still
    halfway through building is not something to hand to their customers or
    to a crawler. Publishing sets the timestamp that opens the page, and
    lands the tenant on it — seeing the live thing is the point of the step.
    """
    company_name = company_name.strip()
    if company_name:
        tenant.name = company_name[:255]
    tenant.onboarded_at = utc_now()
    await db.commit()
    logger.info("Onboarding: tenant %s published '%s'", tenant.slug, tenant.name)
    return RedirectResponse(url=f"/trust/{tenant.slug}", status_code=303)


@router.post("/remove/{subprocessor_id}", response_class=HTMLResponse)
async def remove(
    request: Request,
    subprocessor_id: UUID,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
):
    """Undo inside the wizard.

    The dashboard's delete returns the dashboard's table; the wizard needs
    the wizard's state back, which is the whole reason this exists.
    """
    row = (
        await db.execute(
            select(Subprocessor).where(
                Subprocessor.id == subprocessor_id,
                Subprocessor.tenant_id == tenant.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")

    await db.delete(row)
    await db.commit()
    logger.info("Onboarding: tenant %s removed '%s'", tenant.slug, row.name)
    return _templates.TemplateResponse(
        request, "partials/onboarding_state.html", await _state(request, tenant, db)
    )
