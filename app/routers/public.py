import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.ratelimit import SlidingWindowLimiter, get_client_ip
from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.subscriber import Subscriber
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.services.mailer import mailer

logger = logging.getLogger(__name__)

_sub_limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)

router = APIRouter(tags=["public"])
_templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

_ALGORITHM = "HS256"
_SUBSCRIPTION_EXPIRE = timedelta(days=7)


def _make_subscription_token(subscriber_id: str) -> str:
    payload = {
        "sub": subscriber_id,
        "type": "subscription",
        "exp": datetime.now(UTC) + _SUBSCRIPTION_EXPIRE,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


# NOTE: static paths (verify-subscription, unsubscribe) MUST be defined before
# /{slug} — otherwise FastAPI would match them as slug values.
@router.get("/trust/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Subscriber).where(Subscriber.unsubscribe_token == token))
    subscriber = result.scalar_one_or_none()
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe link.")

    subscriber.is_active = False
    await db.commit()
    logger.info("unsubscribe: subscriber %s deactivated", subscriber.id)

    return _templates.TemplateResponse(request, "public_unsubscribed.html", {})


@router.get("/trust/verify-subscription", response_class=HTMLResponse)
async def verify_subscription(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
        subscriber_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if not subscriber_id_str or token_type != "subscription":
            raise HTTPException(status_code=400, detail="Invalid token")
        subscriber_id = UUID(subscriber_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Verification link has expired. Please subscribe again.")
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or malformed token.")

    result = await db.execute(select(Subscriber).where(Subscriber.id == subscriber_id))
    subscriber = result.scalar_one_or_none()
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found.")

    subscriber.confirmed = True
    await db.commit()
    logger.info("verify_subscription: subscriber %s confirmed", subscriber_id)

    return _templates.TemplateResponse(request, "public_confirmed.html", {})


@router.get("/trust/{slug}", response_class=HTMLResponse)
async def trust_page(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Trust page not found")

    sp_result = await db.execute(
        select(Subprocessor)
        .where(
            Subprocessor.tenant_id == tenant.id,
            Subprocessor.monitoring_enabled == True,  # noqa: E712
        )
        .order_by(Subprocessor.name)
    )
    subprocessors = list(sp_result.scalars().all())

    # Published change history: auto-published cosmetic changes and
    # manually approved material ones, newest first.
    ev_result = await db.execute(
        select(ChangeEvent)
        .join(ChangeEvent.subprocessor)
        .where(
            Subprocessor.tenant_id == tenant.id,
            ChangeEvent.status.in_(
                (ChangeStatus.approved.value, ChangeStatus.auto_published.value)
            ),
        )
        .options(selectinload(ChangeEvent.subprocessor))
        .order_by(ChangeEvent.created_at.desc())
        .limit(20)
    )
    change_events = list(ev_result.scalars().all())

    return _templates.TemplateResponse(
        request,
        "public_trust.html",
        {"tenant": tenant, "subprocessors": subprocessors, "change_events": change_events},
    )


@router.post("/trust/{slug}/subscribe", response_class=HTMLResponse)
async def subscribe(
    request: Request,
    slug: str,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    email = email.strip().lower()
    client_ip = get_client_ip(request)
    if not _sub_limiter.allow(f"ip:{client_ip}") or not _sub_limiter.allow(f"email:{email}"):
        logger.warning("subscribe: rate limit hit for email=%s ip=%s", email, client_ip)
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute.")

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Trust page not found")

    existing = await db.execute(
        select(Subscriber).where(
            Subscriber.tenant_id == tenant.id,
            Subscriber.email == email,
        )
    )
    subscriber = existing.scalar_one_or_none()

    if subscriber is not None and subscriber.confirmed:
        return _templates.TemplateResponse(
            request, "partials/subscribe_result.html", {"status": "already_confirmed"}
        )

    if subscriber is None:
        subscriber = Subscriber(tenant_id=tenant.id, email=email, confirmed=False)
        db.add(subscriber)
        await db.commit()
        logger.info("subscribe: new subscriber '%s' for tenant '%s'", email, slug)
    else:
        logger.info("subscribe: resending verification to '%s' for tenant '%s'", email, slug)

    token = _make_subscription_token(str(subscriber.id))
    verify_url = f"{settings.APP_URL}/trust/verify-subscription?token={token}"
    logger.info("[SUBSCRIPTION VERIFY] sent to %s for tenant '%s'", email, slug)
    await mailer.send_subscription_confirmation(
        email=email, link=verify_url, tenant_name=tenant.name
    )

    return _templates.TemplateResponse(
        request, "partials/subscribe_result.html", {"status": "sent"}
    )
