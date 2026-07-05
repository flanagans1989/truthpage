import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.routers.deps import CurrentTenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/billing", tags=["billing"])

_templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

_PADDLE_API_BASE = (
    "https://api.paddle.com"
    if settings.PADDLE_ENVIRONMENT == "production"
    else "https://sandbox-api.paddle.com"
)


@router.get("/checkout")
async def checkout(request: Request, tenant: CurrentTenant):
    if not settings.PADDLE_PRICE_ID_GROWTH or not settings.PADDLE_CLIENT_TOKEN:
        raise HTTPException(status_code=503, detail="Billing not configured")

    return _templates.TemplateResponse(
        request,
        "checkout.html",
        {
            "paddle_client_token": settings.PADDLE_CLIENT_TOKEN,
            "paddle_environment": settings.PADDLE_ENVIRONMENT,
            "price_id": settings.PADDLE_PRICE_ID_GROWTH,
            "tenant_id": str(tenant.id),
            "customer_email": tenant.email,
            "success_url": f"{settings.APP_URL}/dashboard?checkout=success",
        },
    )


@router.get("/portal")
async def billing_portal(tenant: CurrentTenant):
    """Paddle has no Stripe-style portal session API — redirect to the
    per-subscription management URL Paddle returns on the subscription itself."""
    if not tenant.paddle_subscription_id:
        # No active subscription yet — nothing to manage, send them to checkout
        return RedirectResponse(url="/dashboard/billing/checkout", status_code=303)

    try:
        async with httpx.AsyncClient(base_url=_PADDLE_API_BASE, timeout=10.0) as client:
            resp = await client.get(
                f"/subscriptions/{tenant.paddle_subscription_id}",
                headers={"Authorization": f"Bearer {settings.PADDLE_API_KEY}"},
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Paddle subscription lookup failed for tenant %s", tenant.id)
        raise HTTPException(status_code=502, detail="Could not open the billing portal")

    management_urls = resp.json().get("data", {}).get("management_urls") or {}
    update_url = management_urls.get("update_payment_method")
    if not update_url:
        raise HTTPException(status_code=502, detail="Could not open the billing portal")

    return RedirectResponse(url=update_url, status_code=303)
