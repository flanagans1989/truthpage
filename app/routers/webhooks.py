import asyncio
import logging
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.tenant import Tenant
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

stripe.api_key = settings.STRIPE_SECRET_KEY

_SUBSCRIPTION_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "canceled": "canceled",
    "unpaid": "unpaid",
    "paused": "canceled",  # treat paused as canceled for gating purposes
    "incomplete": "past_due",
    "incomplete_expired": "canceled",
}


async def _find_tenant_by_id(tenant_id_str: str, db: AsyncSession) -> Tenant | None:
    try:
        tenant_id = UUID(tenant_id_str)
    except ValueError:
        return None
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def _find_tenant_by_customer(stripe_customer_id: str, db: AsyncSession) -> Tenant | None:
    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == stripe_customer_id)
    )
    return result.scalar_one_or_none()


async def _handle_checkout_completed(session: dict, db: AsyncSession) -> None:
    client_ref = session.get("client_reference_id")
    stripe_customer_id = session.get("customer")

    tenant: Tenant | None = None
    if client_ref:
        tenant = await _find_tenant_by_id(client_ref, db)
    if tenant is None and stripe_customer_id:
        tenant = await _find_tenant_by_customer(stripe_customer_id, db)

    if tenant is None:
        logger.warning("webhook checkout.session.completed: no tenant found (ref=%s)", client_ref)
        return

    if stripe_customer_id:
        tenant.stripe_customer_id = stripe_customer_id
    tenant.subscription_status = "active"
    await db.commit()
    logger.info(
        "webhook checkout.session.completed: tenant %s activated (customer=%s)",
        tenant.id, stripe_customer_id,
    )


async def _handle_subscription_updated(subscription: dict, db: AsyncSession) -> None:
    stripe_customer_id: str = subscription.get("customer", "")
    raw_status: str = subscription.get("status", "")
    mapped_status = _SUBSCRIPTION_STATUS_MAP.get(raw_status, "past_due")

    tenant = await _find_tenant_by_customer(stripe_customer_id, db)
    if tenant is None:
        logger.warning(
            "webhook customer.subscription.updated: no tenant for customer %s", stripe_customer_id
        )
        return

    tenant.subscription_status = mapped_status
    await db.commit()
    logger.info(
        "webhook customer.subscription.updated: tenant %s status → %s",
        tenant.id, mapped_status,
    )


async def _handle_subscription_deleted(subscription: dict, db: AsyncSession) -> None:
    stripe_customer_id: str = subscription.get("customer", "")

    tenant = await _find_tenant_by_customer(stripe_customer_id, db)
    if tenant is None:
        logger.warning(
            "webhook customer.subscription.deleted: no tenant for customer %s", stripe_customer_id
        )
        return

    tenant.subscription_status = "canceled"
    await db.commit()
    logger.info(
        "webhook customer.subscription.deleted: tenant %s canceled", tenant.id
    )


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    try:
        event = await asyncio.to_thread(
            stripe.Webhook.construct_event,
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type: str = event["type"]
    data_object: dict = event["data"]["object"]

    logger.info("webhook: received event type=%s id=%s", event_type, event["id"])

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data_object, db)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data_object, db)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data_object, db)
    else:
        logger.debug("webhook: unhandled event type %s — ignoring", event_type)

    return {"received": True}
