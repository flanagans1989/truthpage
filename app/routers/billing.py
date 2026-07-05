import asyncio
import logging

import stripe
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.routers.deps import CurrentTenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/billing", tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/checkout")
async def checkout(tenant: CurrentTenant):
    if not settings.STRIPE_PRICE_GROWTH:
        raise HTTPException(status_code=503, detail="Billing not configured")

    create_kwargs: dict = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICE_GROWTH, "quantity": 1}],
        "client_reference_id": str(tenant.id),
        "success_url": f"{settings.APP_URL}/dashboard?checkout=success",
        "cancel_url": f"{settings.APP_URL}/dashboard",
        "allow_promotion_codes": True,
    }
    if tenant.stripe_customer_id:
        create_kwargs["customer"] = tenant.stripe_customer_id

    try:
        session = await asyncio.to_thread(
            stripe.checkout.Session.create, **create_kwargs
        )
    except stripe.StripeError:
        logger.exception("Stripe checkout session creation failed for tenant %s", tenant.id)
        raise HTTPException(status_code=502, detail="Could not create Stripe checkout session")

    logger.info("billing: checkout session created for tenant %s", tenant.id)
    return RedirectResponse(url=session.url, status_code=303)


@router.get("/portal")
async def billing_portal(tenant: CurrentTenant):
    """Stripe customer portal — manage payment method, invoices, cancellation."""
    if not tenant.stripe_customer_id:
        # No Stripe customer yet — nothing to manage, send them to checkout
        return RedirectResponse(url="/dashboard/billing/checkout", status_code=303)

    try:
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=tenant.stripe_customer_id,
            return_url=f"{settings.APP_URL}/dashboard",
        )
    except stripe.StripeError:
        logger.exception("Stripe portal session creation failed for tenant %s", tenant.id)
        raise HTTPException(status_code=502, detail="Could not open the billing portal")

    return RedirectResponse(url=session.url, status_code=303)
