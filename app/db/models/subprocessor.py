import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.change_event import _TIMESTAMP_STATUS_VALUES
from app.db.models.mixins import TimestampMixin


class Subprocessor(TimestampMixin, Base):
    __tablename__ = "subprocessors"
    __table_args__ = (
        CheckConstraint(
            f"baseline_timestamp_status IN {_TIMESTAMP_STATUS_VALUES}",
            name="ck_subprocessors_baseline_timestamp_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    monitored_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw HTML of the last successful fetch, carried forward so the next
    # change event has a "before" document to store — not just its
    # normalized text. Same nullability story as last_content_text.
    last_raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SHA-256 of last_raw_html, carried forward the same way — the digest of
    # the document itself, not of the normalized text used for diffing.
    last_raw_html_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requires_browser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    check_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440, server_default="1440")
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Only ever advanced on a *successful* check (see monitoring.py) — a
    # failed attempt updates next_check_at for the retry but leaves this
    # alone, so it already doubles as "last verified" for the trust page and
    # for resource-health tracking below.
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Resource health: consecutive failed checks (HTTP 4xx/5xx, timeout, empty/
    # meaningless content, or a Tier-2 attempt that also failed). Reset to 0 on
    # any successful check.
    consecutive_failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # When the "Monitoring Alert" email last went out for this source — reset
    # to NULL on recovery so a later, separate failure streak alerts again
    # right away rather than waiting out a stale dedupe window.
    monitoring_alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Why the last check failed, for the dashboard tooltip. NULL on a healthy
    # source. Set alongside consecutive_failure_count, cleared on recovery.
    last_failure_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # True for exactly the tick where a check was skipped for lack of Tier-2
    # budget (see tier2_budget.py) — cleared the moment a real fetch attempt
    # runs again, success or failure. Not a failure: doesn't touch
    # consecutive_failure_count. This is what makes a budget-queued source
    # visible on the dashboard instead of just quietly not being scraped.
    tier2_deferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Per-source Tier-2 daily quota (TIER2_DAILY_PER_SOURCE) — the primary
    # cost control. Separate from the tenant-level pool below (a safety valve,
    # not a feature limit); see tier2_budget.py for why both exist.
    tier2_daily_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tier2_daily_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Second, independent alarm from the failure-count one above: fires once
    # last_checked_at is older than STALENESS_ALERT_DAYS, no matter why (a
    # failure streak, a long budget deferral, a dead worker, anything) — the
    # only question it asks is "was this source actually looked at recently".
    staleness_alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # RFC 3161 timestamping for this source's very FIRST captured snapshot
    # — the one taken on first check, before there is anything to diff
    # against (see monitoring.py's "First check" branch), so it never
    # becomes a change_event and would otherwise never be timestamp-
    # eligible at all. Mirrors ChangeEvent's TSA columns exactly, same
    # KURAL 0: every EXISTING row defaults to the terminal
    # not_available_pre_tsa (server_default) — a baseline captured before
    # this feature shipped is never backdated. baseline_raw_html_hash is a
    # frozen copy of the hash actually offered for stamping —
    # last_raw_html_hash above keeps moving with every later check, so the
    # baseline's own digest has to be pinned separately.
    baseline_raw_html_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_timestamp_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_available_pre_tsa", server_default="not_available_pre_tsa"
    )
    baseline_tsa_token: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    baseline_tsa_authority_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    baseline_tsa_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_tsa_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    baseline_tsa_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(  # noqa: F821
        "Tenant",
        back_populates="subprocessors",
        lazy="raise",
    )
    change_events: Mapped[list["ChangeEvent"]] = relationship(  # noqa: F821
        "ChangeEvent",
        back_populates="subprocessor",
        lazy="raise",
    )

    @property
    def is_stale(self) -> bool:
        """A source is stale once it's been longer than STALENESS_ALERT_DAYS
        since it was actually, successfully looked at — regardless of cause
        (a failure streak, a long Tier-2 budget deferral, a dropped worker,
        anything unforeseen). Falls back to created_at for a source that has
        never had a successful check yet, so a page added seconds ago isn't
        immediately flagged before its first check has had a chance to run.
        """
        from datetime import UTC

        from app.core.config import settings
        from app.db.models.mixins import utc_now

        reference = self.last_checked_at or self.created_at
        if reference is None:
            return False
        # SQLite (tests only) hands back naive datetimes; we only ever write
        # UTC into either column, so that's the correct zone to attach.
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        age = utc_now() - reference
        return age >= timedelta(days=settings.STALENESS_ALERT_DAYS)

    @property
    def has_monitoring_alert(self) -> bool:
        """Persistent badge condition — independent of whether either
        dedupe window has already sent its email, so the dashboard keeps
        showing the warning for the whole outage, not just the day an email
        went out. True on EITHER signal: a failure streak past threshold, or
        staleness past STALENESS_ALERT_DAYS — two different questions
        ("is it erroring" vs. "has it actually been checked recently") that
        can each be true without the other (a budget deferral trips
        staleness with zero failures recorded)."""
        from app.core.config import settings

        return (
            self.consecutive_failure_count >= settings.MONITORING_ALERT_FAILURE_THRESHOLD
            or self.is_stale
        )
