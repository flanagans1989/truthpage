"""Aggregate queries for /admin/funnel — the 30-day sales test's dashboard.

GA4 is not queryable from here, which is the whole reason funnel_events
exists: the kill/continue call at the end of the test has to be answerable
in SQL, not trusted to a dashboard elsewhere.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.funnel_event import FunnelEvent
from app.db.models.mixins import utc_now
from app.db.models.tenant import Tenant

FUNNEL_WINDOW_DAYS = 30

# The fixed sequence the conversion percentages step through — order matters,
# each entry's rate is relative to the one before it.
FUNNEL_STEPS = [
    "landing_view",
    "signup_requested",
    "signup_completed",
    "onboarding_completed",
    "checkout_opened",
    "subscription_started",
]

# All event_names worth showing in the raw counts table, including ones not
# part of the strict sequence above (grader/lead magnet are alternate entry
# points, cancellation is an exit).
ALL_EVENTS = FUNNEL_STEPS + ["grader_used", "lead_captured", "subscription_canceled"]

PAYING_CUSTOMER_TARGET = 3
TARGET_DATE = date(2026, 10, 6)


@dataclass
class EventCount:
    event_name: str
    unique_actors: int
    total: int


@dataclass
class StepConversion:
    from_event: str
    to_event: str
    rate_percent: float | None  # None when the "from" step has zero actors


@dataclass
class FunnelStats:
    window_days: int = FUNNEL_WINDOW_DAYS
    events: list[EventCount] = field(default_factory=list)
    conversions: list[StepConversion] = field(default_factory=list)
    paying_customers: int = 0
    paying_target: int = PAYING_CUSTOMER_TARGET
    days_remaining: int = 0
    past_due_count: int = 0
    trialing_count: int = 0
    ever_paid_count: int = 0


async def collect_funnel_stats(db: AsyncSession, *, now: datetime | None = None) -> FunnelStats:
    now = now or utc_now()
    cutoff = now - timedelta(days=FUNNEL_WINDOW_DAYS)

    # Distinct actor = one cookie (anon_id) or, for server-originated events
    # with no browser session (a Paddle webhook has neither), the tenant —
    # coalesced so neither kind of event silently reads as zero unique actors.
    actor = func.coalesce(FunnelEvent.anon_id, cast(FunnelEvent.tenant_id, String))
    rows = (
        await db.execute(
            select(
                FunnelEvent.event_name,
                func.count(func.distinct(actor)),
                func.count(),
            )
            .where(FunnelEvent.created_at >= cutoff)
            .group_by(FunnelEvent.event_name)
        )
    ).all()
    counts = {name: (unique, total) for name, unique, total in rows}

    events = [
        EventCount(event_name=name, unique_actors=counts.get(name, (0, 0))[0], total=counts.get(name, (0, 0))[1])
        for name in ALL_EVENTS
    ]

    conversions: list[StepConversion] = []
    for prev_name, next_name in zip(FUNNEL_STEPS, FUNNEL_STEPS[1:]):
        prev_unique = counts.get(prev_name, (0, 0))[0]
        next_unique = counts.get(next_name, (0, 0))[0]
        rate = (next_unique / prev_unique * 100) if prev_unique else None
        conversions.append(StepConversion(from_event=prev_name, to_event=next_name, rate_percent=rate))

    tenant_status_counts = dict(
        (await db.execute(select(Tenant.subscription_status, func.count()).group_by(Tenant.subscription_status))).all()
    )

    # "Ever paid" is not windowed to the last 30 days — a tenant who paid and
    # churned earlier is still a signal the kill/continue call cares about,
    # just a different one than "currently paying".
    ever_paid_count = (
        await db.execute(
            select(func.count(func.distinct(FunnelEvent.tenant_id))).where(
                FunnelEvent.event_name == "subscription_started",
                FunnelEvent.tenant_id.is_not(None),
            )
        )
    ).scalar_one()

    days_remaining = (TARGET_DATE - now.date()).days

    return FunnelStats(
        events=events,
        conversions=conversions,
        paying_customers=int(tenant_status_counts.get("active", 0)),
        paying_target=PAYING_CUSTOMER_TARGET,
        days_remaining=days_remaining,
        past_due_count=int(tenant_status_counts.get("past_due", 0)),
        trialing_count=int(tenant_status_counts.get("trialing", 0)),
        ever_paid_count=int(ever_paid_count or 0),
    )
