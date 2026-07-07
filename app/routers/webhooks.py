import hashlib
import hmac
import json
import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.tenant import Tenant
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_SUBSCRIPTION_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "paused": "canceled",  # treat paused as canceled for gating purposes
    "canceled": "canceled",
}


# Reject webhooks whose signature timestamp is too old — otherwise a captured
# payload (e.g. an old transaction.completed) could be replayed to re-activate
# a canceled subscription. Paddle recommends a 5-second window; we allow more
# slack for clock drift and retries, which Paddle sends with a fresh signature.
_SIGNATURE_MAX_AGE_SECONDS = 300


def _verify_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    parts = dict(p.split("=", 1) for p in sig_header.split(";") if "=" in p)
    ts, h1 = parts.get("ts"), parts.get("h1")
    if not ts or not h1:
        return False
    try:
        if abs(time.time() - int(ts)) > _SIGNATURE_MAX_AGE_SECONDS:
            return False
        decoded = payload.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    signed_payload = f"{ts}:{decoded}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, h1)


async def _find_tenant_by_id(tenant_id_str: str, db: AsyncSession) -> Tenant | None:
    try:
        tenant_id = UUID(tenant_id_str)
    except ValueError:
        return None
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def _find_tenant_by_customer(paddle_customer_id: str, db: AsyncSession) -> Tenant | None:
    result = await db.execute(
        select(Tenant).where(Tenant.paddle_customer_id == paddle_customer_id)
    )
    return result.scalar_one_or_none()


async def _handle_transaction_completed(data: dict, db: AsyncSession) -> None:
    tenant_id_str = (data.get("custom_data") or {}).get("tenant_id")
    paddle_customer_id = data.get("customer_id")
    paddle_subscription_id = data.get("subscription_id")

    tenant: Tenant | None = None
    if tenant_id_str:
        tenant = await _find_tenant_by_id(tenant_id_str, db)
    if tenant is None and paddle_customer_id:
        tenant = await _find_tenant_by_customer(paddle_customer_id, db)

    if tenant is None:
        logger.warning("webhook transaction.completed: no tenant found (ref=%s)", tenant_id_str)
        return

    if paddle_customer_id:
        tenant.paddle_customer_id = paddle_customer_id
    if paddle_subscription_id:
        tenant.paddle_subscription_id = paddle_subscription_id
    tenant.subscription_status = "active"
    await db.commit()
    logger.info(
        "webhook transaction.completed: tenant %s activated (customer=%s)",
        tenant.id, paddle_customer_id,
    )


async def _handle_subscription_updated(data: dict, db: AsyncSession) -> None:
    paddle_customer_id: str = data.get("customer_id", "")
    paddle_subscription_id: str = data.get("id", "")
    raw_status: str = data.get("status", "")
    mapped_status = _SUBSCRIPTION_STATUS_MAP.get(raw_status, "past_due")

    tenant = await _find_tenant_by_customer(paddle_customer_id, db)
    if tenant is None:
        logger.warning(
            "webhook subscription.updated: no tenant for customer %s", paddle_customer_id
        )
        return

    if paddle_subscription_id:
        tenant.paddle_subscription_id = paddle_subscription_id
    tenant.subscription_status = mapped_status
    await db.commit()
    logger.info(
        "webhook subscription.updated: tenant %s status → %s",
        tenant.id, mapped_status,
    )


async def _handle_subscription_canceled(data: dict, db: AsyncSession) -> None:
    paddle_customer_id: str = data.get("customer_id", "")

    tenant = await _find_tenant_by_customer(paddle_customer_id, db)
    if tenant is None:
        logger.warning(
            "webhook subscription.canceled: no tenant for customer %s", paddle_customer_id
        )
        return

    tenant.subscription_status = "canceled"
    await db.commit()
    logger.info("webhook subscription.canceled: tenant %s canceled", tenant.id)


@router.post("/paddle")
async def paddle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    payload = await request.body()
    sig_header = request.headers.get("paddle-signature", "")

    if not settings.PADDLE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    if not _verify_signature(payload, sig_header, settings.PADDLE_WEBHOOK_SECRET):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(payload)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type: str = event.get("event_type", "")
    data: dict = event.get("data", {})

    logger.info("webhook: received event type=%s id=%s", event_type, event.get("event_id"))

    if event_type == "transaction.completed":
        await _handle_transaction_completed(data, db)
    elif event_type == "subscription.updated" or event_type == "subscription.activated":
        await _handle_subscription_updated(data, db)
    elif event_type == "subscription.canceled":
        await _handle_subscription_canceled(data, db)
    else:
        logger.debug("webhook: unhandled event type %s — ignoring", event_type)

    return {"received": True}
