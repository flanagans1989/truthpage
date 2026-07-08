"""Aggregate queries for the platform admin panel (/admin).

Everything here is read-only and cross-tenant; only reachable behind
the CurrentAdmin dependency.
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.db.models.tenant import Tenant

CHART_DAYS = 30

# Display order + palette slots for stacked event chart (validated categorical order)
EVENT_STATUS_SERIES = [
    (ChangeStatus.auto_published.value, "Otomatik yayın", "#2a78d6"),
    (ChangeStatus.approved.value, "Onaylandı", "#1baf7a"),
    (ChangeStatus.pending_review.value, "İncelemede", "#eda100"),
    (ChangeStatus.rejected.value, "Reddedildi", "#e34948"),
]


def _day_window() -> list[date]:
    today = utc_now().date()
    return [today - timedelta(days=i) for i in range(CHART_DAYS - 1, -1, -1)]


async def collect_admin_stats(db: AsyncSession) -> dict[str, Any]:
    now = utc_now()
    days = _day_window()
    window_start = days[0]

    # ── KPI counts ────────────────────────────────────────────────────────
    tenants_by_status = dict(
        (await db.execute(
            select(Tenant.subscription_status, func.count()).group_by(Tenant.subscription_status)
        )).all()
    )
    expired_trials = (await db.execute(
        select(func.count()).select_from(Tenant).where(
            Tenant.subscription_status == "trialing",
            Tenant.trial_ends_at.is_not(None),
            Tenant.trial_ends_at <= now,
        )
    )).scalar_one()

    sub_total, sub_enabled, sub_browser, sub_overdue = (await db.execute(
        select(
            func.count(),
            func.count().filter(Subprocessor.monitoring_enabled.is_(True)),
            func.count().filter(Subprocessor.requires_browser.is_(True)),
            func.count().filter(
                Subprocessor.monitoring_enabled.is_(True),
                Subprocessor.next_check_at.is_not(None),
                Subprocessor.next_check_at < now,
            ),
        ).select_from(Subprocessor)
    )).one()

    subs_total, subs_confirmed = (await db.execute(
        select(
            func.count(),
            func.count().filter(Subscriber.confirmed.is_(True), Subscriber.is_active.is_(True)),
        ).select_from(Subscriber)
    )).one()

    events_by_status = dict(
        (await db.execute(
            select(ChangeEvent.status, func.count()).group_by(ChangeEvent.status)
        )).all()
    )
    events_24h = (await db.execute(
        select(func.count()).select_from(ChangeEvent).where(
            ChangeEvent.created_at >= now - timedelta(hours=24)
        )
    )).scalar_one()

    classification_counts = dict(
        (await db.execute(
            select(
                func.coalesce(ChangeEvent.llm_classification, "UNCLASSIFIED"),
                func.count(),
            ).group_by(ChangeEvent.llm_classification)
        )).all()
    )

    # ── Daily series (last CHART_DAYS days) ───────────────────────────────
    signup_rows = (await db.execute(
        select(func.date(Tenant.created_at), func.count())
        .where(func.date(Tenant.created_at) >= window_start)
        .group_by(func.date(Tenant.created_at))
    )).all()
    signups_by_day = {d: n for d, n in signup_rows}

    event_rows = (await db.execute(
        select(func.date(ChangeEvent.created_at), ChangeEvent.status, func.count())
        .where(func.date(ChangeEvent.created_at) >= window_start)
        .group_by(func.date(ChangeEvent.created_at), ChangeEvent.status)
    )).all()
    events_by_day: dict[date, dict[str, int]] = {}
    for d, status_value, n in event_rows:
        events_by_day.setdefault(d, {})[status_value] = n

    signups_chart = build_column_chart(days, signups_by_day)
    events_chart = build_stacked_chart(days, events_by_day)

    # ── Tenants table ─────────────────────────────────────────────────────
    sub_counts = (
        select(Subprocessor.tenant_id, func.count().label("n"))
        .group_by(Subprocessor.tenant_id)
        .subquery()
    )
    subscriber_counts = (
        select(Subscriber.tenant_id, func.count().label("n"))
        .where(Subscriber.confirmed.is_(True), Subscriber.is_active.is_(True))
        .group_by(Subscriber.tenant_id)
        .subquery()
    )
    pending_counts = (
        select(Subprocessor.tenant_id, func.count().label("n"))
        .join(ChangeEvent, ChangeEvent.subprocessor_id == Subprocessor.id)
        .where(ChangeEvent.status == ChangeStatus.pending_review.value)
        .group_by(Subprocessor.tenant_id)
        .subquery()
    )
    tenant_rows = (await db.execute(
        select(
            Tenant,
            func.coalesce(sub_counts.c.n, 0),
            func.coalesce(subscriber_counts.c.n, 0),
            func.coalesce(pending_counts.c.n, 0),
        )
        .outerjoin(sub_counts, sub_counts.c.tenant_id == Tenant.id)
        .outerjoin(subscriber_counts, subscriber_counts.c.tenant_id == Tenant.id)
        .outerjoin(pending_counts, pending_counts.c.tenant_id == Tenant.id)
        .order_by(Tenant.created_at.desc())
    )).all()

    # ── Recent change events across all tenants ──────────────────────────
    recent_events = list((await db.execute(
        select(ChangeEvent)
        .options(
            selectinload(ChangeEvent.subprocessor).selectinload(Subprocessor.tenant)
        )
        .order_by(ChangeEvent.created_at.desc())
        .limit(20)
    )).scalars().all())

    total_tenants = sum(tenants_by_status.values())
    return {
        "now": now,
        "total_tenants": total_tenants,
        "tenants_by_status": tenants_by_status,
        "expired_trials": expired_trials,
        "sub_total": sub_total,
        "sub_enabled": sub_enabled,
        "sub_browser": sub_browser,
        "sub_overdue": sub_overdue,
        "subs_total": subs_total,
        "subs_confirmed": subs_confirmed,
        "events_by_status": events_by_status,
        "events_total": sum(events_by_status.values()),
        "events_24h": events_24h,
        "pending_total": events_by_status.get(ChangeStatus.pending_review.value, 0),
        "classification_counts": classification_counts,
        "signups_chart": signups_chart,
        "events_chart": events_chart,
        "event_status_series": EVENT_STATUS_SERIES,
        "tenant_rows": tenant_rows,
        "recent_events": recent_events,
    }


def build_column_chart(days: list[date], counts: dict[date, int]) -> dict[str, Any]:
    """Single-series column chart: per-day value + height as % of max."""
    peak = max([counts.get(d, 0) for d in days] + [1])
    columns = [
        {
            "label": d.strftime("%d.%m"),
            "value": counts.get(d, 0),
            "pct": round(counts.get(d, 0) / peak * 100, 1),
        }
        for d in days
    ]
    return {"columns": columns, "peak": peak, "total": sum(counts.get(d, 0) for d in days)}


def build_stacked_chart(days: list[date], by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    """Stacked columns: per-day segments in EVENT_STATUS_SERIES order.

    Segment heights are % of the window's max daily total so all columns
    share one scale.
    """
    totals = {d: sum(by_day.get(d, {}).values()) for d in days}
    peak = max(list(totals.values()) + [1])
    columns = []
    for d in days:
        day_counts = by_day.get(d, {})
        segments = [
            {
                "label": label,
                "color": color,
                "value": day_counts.get(status_value, 0),
                "pct": round(day_counts.get(status_value, 0) / peak * 100, 1),
            }
            for status_value, label, color in EVENT_STATUS_SERIES
            if day_counts.get(status_value, 0) > 0
        ]
        columns.append({"label": d.strftime("%d.%m"), "total": totals[d], "segments": segments})
    return {"columns": columns, "peak": peak, "total": sum(totals.values())}
