import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FunnelEvent(Base):
    """One row per funnel step hit, written alongside (never instead of) the
    GA4 gtag calls — see app/services/analytics.py. Lets the kill/continue
    call for the 30-day sales test be answered with SQL rather than trusted
    to GA4 alone.

    anon_id is a random cookie value (tp_aid) — never an IP or user-agent,
    so this table never becomes personal data.

    Column type is generic JSON (not the postgresql.JSONB the migration
    actually creates) so the same model works against the SQLite test
    database — see vendor.py's `entries`/`added`/`removed` columns for the
    existing precedent.
    """

    __tablename__ = "funnel_events"
    __table_args__ = (
        Index("ix_funnel_events_event_name", "event_name"),
        Index("ix_funnel_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_name: Mapped[str] = mapped_column(Text(), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    anon_id: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source: Mapped[str | None] = mapped_column(Text(), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
