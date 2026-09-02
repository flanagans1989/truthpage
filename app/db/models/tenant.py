import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, utc_now

# "free" is the permanent free plan, not a billing state Paddle ever sends:
# it is where an expired trial lands instead of being switched off.
SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "canceled", "unpaid", "free")

# Statuses whose pages the sweeper still checks.
MONITORED_STATUSES = ("active", "trialing", "free")

# Which paid tier, independent of whether billing is currently in good
# standing — a tenant that goes past_due keeps being "starter" or "growth"
# for feature purposes, it just also gets a payment problem. Meaningless
# while subscription_status is "free"; irrelevant during "trialing", which
# always previews the full Growth feature set regardless of which tier the
# tenant will eventually choose.
PLAN_TIERS = ("starter", "growth")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            f"subscription_status IN {SUBSCRIPTION_STATUSES}",
            name="ck_tenants_subscription_status",
        ),
        CheckConstraint(
            f"plan IN {PLAN_TIERS}",
            name="ck_tenants_plan",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Owner email — the only address that can sign in to this tenant.
    # Nullable for legacy rows; claimed on first post-migration login.
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paddle_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="trialing",
        server_default="trialing",
    )
    # End of the free trial. Only meaningful while status == "trialing";
    # a paid subscription (status == "active") ignores it.
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Which paid tier — see PLAN_TIERS above. Set by the checkout the tenant
    # started (custom_data carries it) and confirmed by the webhook against
    # the actual Paddle price id on the transaction/subscription, never
    # trusted from the client alone.
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default="growth", server_default="growth"
    )

    @property
    def trial_expired(self) -> bool:
        return (
            self.subscription_status == "trialing"
            and self.trial_ends_at is not None
            and self.trial_ends_at <= utc_now()
        )

    # White-label switch for the public trust page. Only honoured on a paid
    # plan, so a downgrade brings the badge back on its own rather than
    # leaving a former subscriber permanently white-labelled.
    hide_powered_by: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Set when the onboarding wizard is finished. NULL routes a fresh signup
    # into the wizard; tenants who predate it were backfilled in 0011.
    onboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def needs_onboarding(self) -> bool:
        return self.onboarded_at is None

    @property
    def is_free_plan(self) -> bool:
        return self.subscription_status == "free"

    @property
    def is_starter_plan(self) -> bool:
        """Paying, but on the middle tier — not free, not trialing (a trial
        previews the full Growth feature set), and `plan` says Starter."""
        return not self.is_free_plan and self.subscription_status != "trialing" and self.plan == "starter"

    @property
    def has_growth_features(self) -> bool:
        """Growth-tier features: white-label badge, exportable audit evidence.
        True on Growth (even past_due — a payment problem doesn't retract a
        feature mid-cycle) and during any trial, which previews the full
        Growth experience regardless of which tier the tenant will pick
        afterwards. False for Starter and for the free plan.

        Checks "!= starter" rather than "== growth" so an in-memory Tenant
        with no `plan` set yet (the ORM default only applies at flush, same
        as hide_powered_by above) reads as Growth rather than as neither
        tier — the same fallback subprocessor_limit already relies on.
        """
        if self.is_free_plan:
            return False
        if self.subscription_status == "trialing":
            return True
        return self.plan != "starter"

    @property
    def may_hide_badge(self) -> bool:
        """Removing the badge is a Growth-tier feature."""
        return self.has_growth_features

    @property
    def may_export_evidence(self) -> bool:
        """The downloadable CSV/ZIP audit pack is a Growth-tier feature.
        Free and Starter still get the per-change evidence record on the
        dashboard — just not the exportable file."""
        return self.has_growth_features

    @property
    def shows_powered_by(self) -> bool:
        return not (self.hide_powered_by and self.may_hide_badge)

    # Tier-2 (Playwright) daily cost cap — a SAFETY VALVE now, not a feature
    # limit. The real per-source quota lives on Subprocessor
    # (tier2_daily_count/date there); this tenant-wide pool only exists to
    # bound worst-case cost if something spends far more than expected across
    # many sources at once. Sized at roughly 2x the vendor cap so normal
    # operation never gets near it — see app/services/tier2_budget.py, which
    # does the actual atomic increment (not an ORM read-modify-write, to
    # stay race-safe under concurrent workers).
    tier2_daily_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tier2_daily_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    @property
    def tier2_daily_limit(self) -> int:
        from app.core.config import settings

        if self.is_free_plan:
            return settings.TIER2_DAILY_LIMIT_FREE
        if self.is_starter_plan:
            return settings.TIER2_DAILY_LIMIT_STARTER
        return settings.TIER2_DAILY_LIMIT_GROWTH

    @property
    def subprocessor_limit(self) -> int:
        from app.core.config import settings

        if self.is_free_plan:
            return settings.FREE_TIER_MAX_SUBPROCESSORS
        if self.is_starter_plan:
            return settings.STARTER_MAX_SUBPROCESSORS
        return settings.MAX_SUBPROCESSORS_PER_TENANT

    subprocessors: Mapped[list["Subprocessor"]] = relationship(  # noqa: F821
        "Subprocessor",
        back_populates="tenant",
        lazy="raise",
    )
    subscribers: Mapped[list["Subscriber"]] = relationship(  # noqa: F821
        "Subscriber",
        back_populates="tenant",
        lazy="raise",
    )
