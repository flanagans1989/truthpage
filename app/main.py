import hmac
import logging
import logging.config
from contextlib import asynccontextmanager

import sentry_sdk
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.routers import auth, billing, dashboard, pages, public, subprocessors, webhooks
from app.scheduler.jobs import sweep_due_subprocessors

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    _scheduler.add_job(
        sweep_due_subprocessors,
        trigger="interval",
        minutes=5,
        args=[AsyncSessionLocal],
        id="sweep_due_subprocessors",
        replace_existing=True,
        max_instances=1,  # never overlap; one sweep at a time
    )
    _scheduler.start()
    logger.info("Zamanlayıcı tetiklendi — sweep job her 5 dakikada bir çalışacak")

    yield

    # --- shutdown ---
    _scheduler.shutdown(wait=False)
    logger.info("Zamanlayıcı durduruldu")
    await engine.dispose()


app = FastAPI(title="TrustPages", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(subprocessors.router)
app.include_router(billing.router)
app.include_router(webhooks.router)
app.include_router(public.router)


@app.get("/healthz")
async def healthz():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}


@app.post("/internal/sweep")
async def trigger_sweep(x_admin_secret: str = Header(...)):
    if not hmac.compare_digest(x_admin_secret, settings.JWT_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    await sweep_due_subprocessors(AsyncSessionLocal)
    return {"status": "sweep triggered"}
