import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class Subprocessor(TimestampMixin, Base):
    __tablename__ = "subprocessors"

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
    def has_monitoring_alert(self) -> bool:
        """Persistent badge condition — independent of whether the dedupe
        window has already sent the email, so the dashboard keeps showing the
        warning for the whole outage, not just the day the email went out."""
        from app.core.config import settings

        return self.consecutive_failure_count >= settings.MONITORING_ALERT_FAILURE_THRESHOLD
