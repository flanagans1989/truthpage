"""Funnel instrumentation for the 30-day sales test.

Writes alongside (never instead of) the GA4 gtag calls fired client-side —
see base.html/checkout.html's `ga_events` — so the kill/continue call can be
answered with SQL against funnel_events rather than trusted to GA4 alone.

track() must never break the request it's called from: a bad DB connection
or a bug here is not a reason to fail a signup, a checkout render, or a
webhook. Same shape as MailerService — log and swallow.
"""
import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.funnel_event import FunnelEvent

logger = logging.getLogger(__name__)

# Set by AnonIdMiddleware (app/main.py) on every request, new or returning.
# Never an IP or user-agent — just a random id, so this cookie carries no
# personal data.
ANON_ID_COOKIE = "tp_aid"


def anon_id_from(request: Request) -> str | None:
    """The visitor's tp_aid, however the request got it (fresh from the
    middleware this tick, or an existing cookie)."""
    return getattr(request.state, "anon_id", None) or request.cookies.get(ANON_ID_COOKIE)


def source_from(request: Request) -> str | None:
    """utm_source wins; ?ref=... is the fallback for links that don't carry
    full UTM params (e.g. a one-off DM or a forum post)."""
    return request.query_params.get("utm_source") or request.query_params.get("ref")


async def track(
    session: AsyncSession,
    event_name: str,
    *,
    tenant_id: uuid.UUID | None = None,
    anon_id: str | None = None,
    source: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    try:
        session.add(
            FunnelEvent(
                event_name=event_name,
                tenant_id=tenant_id,
                anon_id=anon_id,
                source=source,
                meta=meta,
            )
        )
        await session.commit()
    except Exception:
        logger.exception("analytics.track failed for event '%s'", event_name)
        try:
            await session.rollback()
        except Exception:
            logger.exception("analytics.track: rollback also failed for event '%s'", event_name)
