import logging
import random
import re
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.services.mailer import mailer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_ALGORITHM = "HS256"
_MAGIC_EXPIRE = timedelta(minutes=15)
_SESSION_EXPIRE = timedelta(days=30)

# ── In-memory rate limiter ────────────────────────────────────────────────────
# Keyed by "ip:<addr>" or "email:<addr>"; value = deque of UNIX timestamps.
# Safe in single-worker asyncio: no concurrent writes from multiple threads.
_rl_store: dict[str, deque] = defaultdict(deque)
_RL_MAX = 3       # max requests
_RL_WINDOW = 60   # per N seconds


def _get_client_ip(request: Request) -> str:
    # Fly.io injects the real client IP in this header
    fly_ip = request.headers.get("Fly-Client-IP")
    if fly_ip:
        return fly_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_check(key: str) -> bool:
    """Return True if the request is allowed; False if the limit is exceeded."""
    now = datetime.now(UTC).timestamp()
    cutoff = now - _RL_WINDOW
    dq = _rl_store[key]
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= _RL_MAX:
        return False
    dq.append(now)
    return True


def _make_magic_token(email: str) -> str:
    payload = {"sub": email, "type": "magic", "exp": datetime.now(UTC) + _MAGIC_EXPIRE}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def _make_session_token(tenant_id: str) -> str:
    payload = {"sub": tenant_id, "type": "session", "exp": datetime.now(UTC) + _SESSION_EXPIRE}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def _email_to_slug(email: str) -> str:
    username, domain = email.split("@", 1)
    base = domain.split(".")[0]
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or re.sub(r"[^a-z0-9]+", "-", username.lower()).strip("-")


def _email_to_company_name(email: str) -> str:
    domain = email.split("@", 1)[1]
    return domain.split(".")[0].capitalize()


async def _get_unique_slug(base_slug: str, email: str, db: AsyncSession) -> str:
    """
    Return `base_slug` if it is unclaimed. Otherwise try domain-part suffixes
    (e.g. amazon.co.uk → amazon-co-uk), then random 3-digit suffixes until a
    free slot is found.
    """
    async def _is_free(candidate: str) -> bool:
        r = await db.execute(select(Tenant.id).where(Tenant.slug == candidate))
        return r.scalar_one_or_none() is None

    if await _is_free(base_slug):
        return base_slug

    # Try sub-domain parts: amazon.co.uk → try "amazon-co", "amazon-uk", "amazon-co-uk"
    _, domain = email.split("@", 1)
    parts = domain.split(".")  # e.g. ["amazon", "co", "uk"]
    for i in range(1, len(parts)):
        suffix = "-".join(re.sub(r"[^a-z0-9]+", "-", p.lower()) for p in parts[i:])
        candidate = f"{base_slug}-{suffix}"
        if await _is_free(candidate):
            return candidate

    # Fall back to random 3-digit suffix (collision probability: ~0.1% after 10 tries)
    for _ in range(10):
        candidate = f"{base_slug}-{random.randint(100, 999)}"
        if await _is_free(candidate):
            return candidate

    raise RuntimeError(f"Could not generate a unique slug for base '{base_slug}'")


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrustPages — Sign In</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center">
    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 w-full max-w-md">
        <div class="mb-8">
            <span class="text-blue-600 font-bold text-xl">TrustPages</span>
            <h1 class="text-2xl font-bold text-slate-900 mt-4 mb-1">Sign in</h1>
            <p class="text-slate-500 text-sm">Enter your work email and we'll send you a magic link.</p>
        </div>
        <form method="post" action="/auth/request">
            <input type="email" name="email" required autofocus
                class="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
                placeholder="you@company.com">
            <button type="submit"
                class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg text-sm transition">
                Send Magic Link
            </button>
        </form>
    </div>
</body>
</html>"""


@router.post("/request", response_class=HTMLResponse)
async def request_magic_link(request: Request, email: str = Form(...)):
    client_ip = _get_client_ip(request)
    if not _rate_limit_check(f"ip:{client_ip}") or not _rate_limit_check(f"email:{email}"):
        logger.warning("rate_limit: magic link blocked for email=%s ip=%s", email, client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute before trying again.",
        )

    token = _make_magic_token(email)
    magic_url = f"{settings.APP_URL}/auth/verify?token={token}"
    if settings.APP_URL.startswith("http://localhost"):
        print(f"[LOCAL ONLY] Magic Link URL: {magic_url}", flush=True)
    logger.info("[MAGIC LINK] sent to %s (token_prefix=%s...)", email, token[:8])
    await mailer.send_magic_link(email=email, link=magic_url)
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TrustPages — Check your inbox</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center">
    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 w-full max-w-md text-center">
        <div class="text-4xl mb-4">📬</div>
        <h1 class="text-xl font-bold text-slate-900 mb-2">Magic link sent!</h1>
        <p class="text-slate-500 text-sm mb-6">In development, copy the link from the server terminal.</p>
        <a href="/auth/login" class="text-blue-600 text-sm hover:underline">← Back to sign in</a>
    </div>
</body>
</html>"""


@router.get("/verify")
async def verify_magic_link(
    token: str,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if not email or token_type != "magic":
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Magic link has expired. Please request a new one.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")

    base_slug = _email_to_slug(email)

    # Look up by base slug first — if found, this email domain already has a tenant
    result = await db.execute(select(Tenant).where(Tenant.slug == base_slug))
    tenant = result.scalar_one_or_none()

    if tenant is None:
        # New domain: resolve a unique slug before inserting
        slug = await _get_unique_slug(base_slug, email, db)
        tenant = Tenant(name=_email_to_company_name(email), slug=slug)
        db.add(tenant)
        await db.commit()
        logger.info("verify_magic_link: new tenant created slug='%s' for email='%s'", slug, email)
    else:
        logger.info("verify_magic_link: existing tenant slug='%s' for email='%s'", tenant.slug, email)

    session_token = _make_session_token(str(tenant.id))
    redirect = RedirectResponse(url="/dashboard", status_code=303)
    redirect.set_cookie(
        key="session",
        value=session_token,
        max_age=int(_SESSION_EXPIRE.total_seconds()),
        httponly=True,
        secure=settings.APP_URL.startswith("https"),
        samesite="lax",
    )
    return redirect


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie("session")
    return response
