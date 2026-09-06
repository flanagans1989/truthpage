import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.templating import templates as _templates
from app.db.session import get_db_session
from app.routers.deps import CurrentTenant
from app.services.analytics import anon_id_from, track

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/billing", tags=["billing"])

_PADDLE_API_BASE = (
    "https://api.paddle.com"
    if settings.PADDLE_ENVIRONMENT == "production"
    else "https://sandbox-api.paddle.com"
)

# plan/interval → price id. A blank id means "not configured yet in Paddle"
# rather than a code change waiting to happen — the pricing page can
# describe a tier before anyone can actually buy it (see Starter).
_PRICE_IDS = {
    ("starter", "monthly"): settings.PADDLE_PRICE_ID_STARTER,
    ("starter", "yearly"): settings.PADDLE_PRICE_ID_STARTER_YEARLY,
    ("growth", "monthly"): settings.PADDLE_PRICE_ID_GROWTH,
    ("growth", "yearly"): settings.PADDLE_PRICE_ID_GROWTH_YEARLY,
}


_MISCONFIGURED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TrustPages — Checkout unavailable</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="/static/tailwind.css">
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center">
    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 w-full max-w-md text-center">
        <span class="text-blue-600 font-bold text-xl">TrustPages</span>
        <h1 class="text-2xl font-bold text-slate-900 mt-4 mb-1">Checkout is temporarily unavailable</h1>
        <p class="text-slate-500 text-sm">Billing isn't configured for this plan yet. We've been notified —
        please try again shortly, or reach out if this keeps happening.</p>
        <a href="/dashboard" class="text-blue-600 text-sm hover:underline mt-6 inline-block">← Back to dashboard</a>
    </div>
</body>
</html>"""


@router.get("/checkout")
async def checkout(
    request: Request,
    tenant: CurrentTenant,
    plan: str = "growth",
    interval: str = "monthly",
    db: AsyncSession = Depends(get_db_session),
):
    if plan not in ("starter", "growth") or interval not in ("monthly", "yearly"):
        raise HTTPException(status_code=404)

    price_id = _PRICE_IDS[(plan, interval)]
    if not price_id or not settings.PADDLE_CLIENT_TOKEN:
        logger.error(
            "Checkout blocked: billing misconfigured for plan=%s interval=%s "
            "(price_id set=%s, client_token set=%s)",
            plan, interval, bool(price_id), bool(settings.PADDLE_CLIENT_TOKEN),
        )
        return HTMLResponse(content=_MISCONFIGURED_HTML, status_code=503)

    await track(
        db, "checkout_opened",
        tenant_id=tenant.id, anon_id=anon_id_from(request), meta={"plan": plan, "interval": interval},
    )
    return _templates.TemplateResponse(
        request,
        "checkout.html",
        {
            "paddle_client_token": settings.PADDLE_CLIENT_TOKEN,
            "paddle_environment": settings.PADDLE_ENVIRONMENT,
            "price_id": price_id,
            "plan": plan,
            "tenant_id": str(tenant.id),
            "customer_email": tenant.email,
            "success_url": f"{settings.APP_URL}/dashboard?checkout=success",
            "ga_events": [{"name": "checkout_opened", "params": {"plan": plan, "interval": interval}}],
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
