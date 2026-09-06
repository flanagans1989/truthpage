import hmac
import logging
import logging.config
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta

import sentry_sdk
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.ratelimit import SlidingWindowLimiter, get_client_ip
from app.db.models.mixins import as_utc, utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.system_state import (
    SWEEP_LAST_COMPLETED_AT,
    SWEEP_LAST_ERROR,
)
from app.db.session import AsyncSessionLocal, engine, get_db_session
from app.services.analytics import ANON_ID_COOKIE
from app.routers import (
    admin,
    auth,
    billing,
    dashboard,
    localized,
    onboarding,
    pages,
    public,
    subprocessors,
    tools,
    vendors,
    verify,
    webhooks,
)
from app.scheduler.jobs import run_sweep_cycle
from app.services.system_state import get_state

# ── Logging ──────────────────────────────────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    # Quieten noisy third-party loggers
    "loggers": {
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
        "apscheduler": {"level": "WARNING"},
    },
})

# ── Sentry ───────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.2,
        profiles_sample_rate=0.1,
        environment="production",
    )
    logging.getLogger(__name__).info("Sentry initialized (dsn configured)")

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()

# When this process came up. A fresh deploy has no completed sweep yet;
# without a grace window the monitoring probe would report degraded for
# the first few hours of every single deploy and teach us to ignore it.
_BOOT_AT = utc_now()

# /internal/sweep is authenticated, but a leaked secret should not also be
# an unmetered way to burn Neon compute hours — the exact failure that took
# the site down on 2026-08-24. Generous for a human retrying by hand,
# useless as a compute-drain amplifier.
_sweep_limiter = SlidingWindowLimiter(max_requests=4, window_seconds=3600)


def _paddle_required_vars() -> dict[str, str]:
    return {
        "PADDLE_API_KEY": settings.PADDLE_API_KEY,
        "PADDLE_CLIENT_TOKEN": settings.PADDLE_CLIENT_TOKEN,
        "PADDLE_WEBHOOK_SECRET": settings.PADDLE_WEBHOOK_SECRET,
        "PADDLE_PRICE_ID_GROWTH": settings.PADDLE_PRICE_ID_GROWTH,
    }


def billing_status() -> str:
    """"configured" | "misconfigured" — a blank or malformed Paddle price id
    used to fail silently at checkout time, with nothing to notice it had
    happened until a sale didn't. Sandbox is exempt: only a production
    misconfiguration is a real money problem."""
    if settings.PADDLE_ENVIRONMENT != "production":
        return "configured"
    if any(not value for value in _paddle_required_vars().values()):
        return "misconfigured"
    if not settings.PADDLE_PRICE_ID_GROWTH.startswith("pri_"):
        return "misconfigured"
    return "configured"


def _check_paddle_config() -> None:
    """Startup check only — logs, never raises. A silently-broken checkout
    should not also take the whole site down; it should be loud in the logs
    where an admin (or an alert on them) will actually see it."""
    if settings.PADDLE_ENVIRONMENT != "production":
        return
    for name, value in _paddle_required_vars().items():
        if not value:
            logger.critical("PADDLE CONFIG: %s is blank in production — checkout will fail silently", name)
    if settings.PADDLE_PRICE_ID_GROWTH and not settings.PADDLE_PRICE_ID_GROWTH.startswith("pri_"):
        logger.critical(
            "PADDLE CONFIG: PADDLE_PRICE_ID_GROWTH=%r does not look like a Paddle price id (expected 'pri_...')",
            settings.PADDLE_PRICE_ID_GROWTH,
        )


class AnonIdMiddleware(BaseHTTPMiddleware):
    """Stamps every visitor with a random tp_aid cookie (1 year, SameSite=Lax,
    not httponly — it's read by nothing client-side today, but it carries no
    secret either) so funnel_events rows across an anonymous visit can be
    tied together. Deliberately just a uuid4: no IP, no user-agent — nothing
    that would make this cookie personal data.
    """

    async def dispatch(self, request: Request, call_next):
        anon_id = request.cookies.get(ANON_ID_COOKIE)
        is_new = anon_id is None
        if is_new:
            anon_id = str(uuid.uuid4())
        request.state.anon_id = anon_id
        response = await call_next(request)
        if is_new:
            response.set_cookie(
                key=ANON_ID_COOKIE,
                value=anon_id,
                max_age=60 * 60 * 24 * 365,
                httponly=False,
                samesite="lax",
                secure=settings.APP_URL.startswith("https"),
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    _check_paddle_config()
    # Every sweep wakes the Neon compute, which then stays up for its 5-minute
    # scale-to-zero window whether or not anything was due. At 30-minute ticks
    # that is 48 wake-ups a day, roughly 4 compute-hours daily and ~124 a month
    # — structurally over the 100-hour free-tier allowance, which is what
    # exhausted the quota on 2026-08-24 and took the site down for a week.
    # Subprocessors default to check_interval_minutes=1440 (daily), so a
    # 3-hour tick loses nothing real: 8 wake-ups a day, ~20 compute-hours a
    # month. The trade-off is that a subprocessor configured at the 60-minute
    # minimum can now be checked up to 3 hours late.
    _scheduler.add_job(
        run_sweep_cycle,
        trigger="interval",
        hours=3,
        args=[AsyncSessionLocal],
        id="sweep_cycle",
        replace_existing=True,
        max_instances=1,  # never overlap; one sweep at a time
    )
    _scheduler.start()
    logger.info("Zamanlayıcı tetiklendi — sweep job her 3 saatte bir çalışacak")

    yield

    # --- shutdown ---
    _scheduler.shutdown(wait=False)
    logger.info("Zamanlayıcı durduruldu")
    await engine.dispose()


app = FastAPI(title="TrustPages", version="0.1.0", lifespan=lifespan)
app.add_middleware(AnonIdMiddleware)


class RevalidatedStaticFiles(StaticFiles):
    """Static assets change on deploy without versioned filenames; force
    revalidation so browsers pick up new CSS/JS via ETag (304 when unchanged)
    instead of serving heuristically-cached stale copies."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", RevalidatedStaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(subprocessors.router)
app.include_router(onboarding.router)
app.include_router(billing.router)
app.include_router(webhooks.router)
app.include_router(public.router)
app.include_router(vendors.router)
app.include_router(admin.router)
app.include_router(tools.router)
app.include_router(verify.router)


@app.get("/healthz")
async def healthz():
    """Liveness only — is this process up and can it reach the database.

    Deliberately narrow: Render polls this path and will restart or fail a
    deploy on a non-200, so business-logic health must never be able to
    take the service down. That lives at /healthz/monitoring below.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable", "billing": billing_status()}


@app.get("/healthz/monitoring")
async def healthz_monitoring(session: AsyncSession = Depends(get_db_session)):
    """Is the product actually doing its job — for an external uptime probe.

    The monitor runs in-process (APScheduler, see lifespan above). If the
    scheduler dies, or Render spins the free-plan service down and nothing
    wakes it, no sweep runs: no page is fetched, no change is detected, and
    — because every existing alarm is itself produced by a sweep tick — no
    alarm fires either. /healthz stays green throughout, because the
    process and the database are both perfectly fine.

    This endpoint is the one place that can say otherwise. It returns 503
    when the last COMPLETED cycle is older than SWEEP_MAX_AGE_HOURS, so a
    free external uptime monitor pointed here becomes the dead-man's switch
    the system otherwise lacks. No secret: it exposes only ages and counts,
    and a probe that needs a credential is a probe that stops being set up.
    """
    now = utc_now()
    completed = await get_state(session, SWEEP_LAST_COMPLETED_AT)
    last_error = await get_state(session, SWEEP_LAST_ERROR)
    stale_cutoff = now - timedelta(days=settings.STALENESS_ALERT_DAYS)
    stale_sources = await session.scalar(
        select(func.count())
        .select_from(Subprocessor)
        .where(
            Subprocessor.monitoring_enabled == True,  # noqa: E712
            (Subprocessor.last_checked_at == None)  # noqa: E711
            | (Subprocessor.last_checked_at < stale_cutoff),
        )
    )

    last_completed_at = as_utc(completed.occurred_at) if completed else None
    age_seconds = (
        (now - last_completed_at).total_seconds() if last_completed_at else None
    )
    booting = (now - _BOOT_AT) < timedelta(minutes=settings.SWEEP_BOOT_GRACE_MINUTES)

    if age_seconds is None:
        # No cycle has ever completed. Only an alarm once the boot grace
        # window has passed — otherwise every deploy starts red.
        degraded = not booting
        reason = None if booting else "no sweep cycle has completed"
    else:
        degraded = age_seconds > settings.SWEEP_MAX_AGE_HOURS * 3600
        reason = f"last sweep completed {age_seconds / 3600:.1f}h ago" if degraded else None

    body = {
        "status": "degraded" if degraded else "ok",
        "reason": reason,
        "last_sweep_completed_at": (
            last_completed_at.isoformat() if last_completed_at else None
        ),
        "sweep_age_seconds": int(age_seconds) if age_seconds is not None else None,
        "max_age_seconds": int(settings.SWEEP_MAX_AGE_HOURS * 3600),
        "last_sweep_error": last_error.value if last_error else None,
        "stale_sources": int(stale_sources or 0),
        "staleness_threshold_days": settings.STALENESS_ALERT_DAYS,
    }
    return JSONResponse(body, status_code=503 if degraded else 200)


@app.post("/internal/sweep")
async def trigger_sweep(request: Request, x_admin_secret: str = Header(...)):
    # Blank means "not configured" — refuse rather than fall back to
    # JWT_SECRET. See Settings.SWEEP_SECRET for why the two must not be
    # the same key.
    if not settings.SWEEP_SECRET:
        raise HTTPException(status_code=503, detail="Sweep endpoint not configured")
    if not hmac.compare_digest(x_admin_secret, settings.SWEEP_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not _sweep_limiter.allow(get_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many sweep triggers")
    await run_sweep_cycle(AsyncSessionLocal)
    return {"status": "sweep triggered"}


# Registered after every other route, including the @app.get ones above: the
# localized router's paths begin with /{lang}, which would otherwise match
# any single-segment URL — /healthz included, which is what Render polls.
# See app/routers/localized.py.
app.include_router(localized.router)
