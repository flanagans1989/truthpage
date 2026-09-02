import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.mixins import utc_now
from app.db.models.notification import DeliveryEventType, NotificationDeliveryEvent, NotificationRecipient
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.services.plans import move_tenant_to_free

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Paddle keeps a subscription "active" until a scheduled cancellation takes
# effect, so "canceled" here already means the paid period is over. It maps to
# the free plan rather than to a dead account: the same landing place as an
# expired trial, and the tenant's public trust page keeps working.
_SUBSCRIPTION_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "paused": "free",
    "canceled": "free",
}

# Statuses that mean "no paid subscription any more" and therefore need the
# free-plan page limit applied, not just a status write.
_ENDS_THE_SUBSCRIPTION = frozenset({"free"})


def _plan_from_items(items: list[dict] | None) -> str | None:
    """Which tier a transaction/subscription's line items paid for, by
    matching the actual Paddle price id — never trust plan off custom_data,
    which is client-supplied and unverified. None means "couldn't tell";
    the caller keeps whatever plan the tenant already had rather than
    guessing, since downgrading a paying customer by mistake is worse than
    leaving a stale value for one webhook cycle."""
    price_ids = {
        (item.get("price") or {}).get("id")
        for item in (items or [])
        if isinstance(item, dict)
    }
    if settings.PADDLE_PRICE_ID_STARTER and settings.PADDLE_PRICE_ID_STARTER in price_ids:
        return "starter"
    if settings.PADDLE_PRICE_ID_STARTER_YEARLY and settings.PADDLE_PRICE_ID_STARTER_YEARLY in price_ids:
        return "starter"
    if settings.PADDLE_PRICE_ID_GROWTH and settings.PADDLE_PRICE_ID_GROWTH in price_ids:
        return "growth"
    if settings.PADDLE_PRICE_ID_GROWTH_YEARLY and settings.PADDLE_PRICE_ID_GROWTH_YEARLY in price_ids:
        return "growth"
    return None


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
    plan = _plan_from_items(data.get("items"))
    if plan is not None:
        tenant.plan = plan
    tenant.subscription_status = "active"
    await db.commit()
    logger.info(
        "webhook transaction.completed: tenant %s activated (customer=%s, plan=%s)",
        tenant.id, paddle_customer_id, tenant.plan,
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

    plan = _plan_from_items(data.get("items"))
    if plan is not None:
        tenant.plan = plan

    if mapped_status in _ENDS_THE_SUBSCRIPTION:
        switched_off = await move_tenant_to_free(tenant, db)
        logger.info(
            "webhook subscription.updated: tenant %s → free plan, %d page(s) switched off",
            tenant.id, switched_off,
        )
    else:
        tenant.subscription_status = mapped_status
        logger.info(
            "webhook subscription.updated: tenant %s status → %s",
            tenant.id, mapped_status,
        )
    await db.commit()


async def _handle_subscription_canceled(data: dict, db: AsyncSession) -> None:
    paddle_customer_id: str = data.get("customer_id", "")

    tenant = await _find_tenant_by_customer(paddle_customer_id, db)
    if tenant is None:
        logger.warning(
            "webhook subscription.canceled: no tenant for customer %s", paddle_customer_id
        )
        return

    switched_off = await move_tenant_to_free(tenant, db)
    await db.commit()
    logger.info(
        "webhook subscription.canceled: tenant %s → free plan, %d page(s) switched off",
        tenant.id, switched_off,
    )


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


# Resend signs webhooks the same way Svix does (svix-id/svix-timestamp/
# svix-signature) — see docs/manifest_v2.md's Notification section. This is
# a from-scratch implementation of that standard scheme rather than a new
# dependency, since it's three lines of HMAC once the secret is decoded.
_RESEND_EVENT_TYPE_MAP = {
    "email.delivered": DeliveryEventType.delivered.value,
    "email.bounced": DeliveryEventType.bounced.value,
    "email.delivery_delayed": DeliveryEventType.deferred.value,
    "email.failed": DeliveryEventType.failed.value,
    # email.sent is already covered by a NotificationRecipient row simply
    # existing (see app/services/approval.py); email.complained (a spam
    # complaint) is a different signal than this delivery log scopes to —
    # both fall through to the "ignored, logged" branch below, deliberately.
}


def _verify_resend_signature(
    payload: bytes, svix_id: str, svix_timestamp: str, svix_signature: str, secret: str
) -> bool:
    if not (svix_id and svix_timestamp and svix_signature):
        return False
    try:
        if abs(time.time() - int(svix_timestamp)) > _SIGNATURE_MAX_AGE_SECONDS:
            return False
        secret_bytes = base64.b64decode(secret.removeprefix("whsec_"))
    except (ValueError, binascii.Error):
        return False

    signed_content = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + payload
    expected = base64.b64encode(hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()).decode()

    # svix-signature can carry multiple space-separated "v1,<sig>" pairs
    # (secret rotation) — any one matching is a valid signature.
    for part in svix_signature.split(" "):
        version, _, sig = part.partition(",")
        if version == "v1" and sig and hmac.compare_digest(sig, expected):
            return True
    return False


def _parse_resend_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _handle_resend_delivery_event(event: dict, webhook_event_id: str, db: AsyncSession) -> None:
    event_type = _RESEND_EVENT_TYPE_MAP.get(event.get("type", ""))
    if event_type is None:
        logger.debug("resend webhook: ignoring unhandled type %s", event.get("type"))
        return

    data: dict = event.get("data") or {}
    email_id = data.get("email_id")
    if not email_id:
        logger.warning("resend webhook: %s event with no data.email_id", event_type)
        return

    result = await db.execute(
        select(NotificationRecipient).where(NotificationRecipient.resend_message_id == email_id)
    )
    recipient = result.scalar_one_or_none()
    if recipient is None:
        # Expected for anything sent before this PR (send_change_notification
        # never stored a NotificationRecipient row), and harmless otherwise.
        logger.info("resend webhook: no recipient row for email_id %s (type=%s)", email_id, event_type)
        return

    db.add(
        NotificationDeliveryEvent(
            recipient_id=recipient.id,
            event_type=event_type,
            occurred_at=_parse_resend_timestamp(event.get("created_at")) or utc_now(),
            webhook_event_id=webhook_event_id,
            raw_type=event.get("type"),
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        # Same webhook delivery retried by Resend — webhook_event_id's
        # unique index is what actually enforces this; the row is simply
        # never inserted twice, never updated in place.
        await db.rollback()
        logger.info("resend webhook: duplicate delivery event %s ignored", webhook_event_id)


@router.post("/resend")
async def resend_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    payload = await request.body()
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    if not settings.RESEND_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    if not _verify_resend_signature(
        payload, svix_id, svix_timestamp, svix_signature, settings.RESEND_WEBHOOK_SECRET
    ):
        # 401, not 400 — this is specifically an authentication failure,
        # and nothing from an unverified request is ever written to the log.
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        event = json.loads(payload)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    await _handle_resend_delivery_event(event, svix_id, db)
    return {"received": True}
