"""Process-independent operational state.

One tiny key/value table whose only job is to answer questions the app
cannot answer about itself from memory: "did the sweep actually run?"

This exists because the monitor runs *inside* the web process
(APScheduler, see app/main.py's lifespan). On Render's free plan the web
service is spun down when idle, and an idle service runs no jobs — so the
scheduler stopping is not an error anyone sees. Worse, every existing
alarm in this codebase (the failure counter, the staleness alert in
app/services/monitoring.py) is itself produced *by* a sweep tick. If the
sweep never runs, nothing fails, nothing goes stale in code, and nobody is
emailed: total monitoring death is the quietest state the system has.

Writing a row here at the end of every cycle inverts that: absence of a
recent write is the signal. See app/services/system_state.py for the
helpers and GET /healthz/monitoring for the external probe that reads it.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin

# Keys are namespaced by subsystem so this table never becomes a junk
# drawer. Anything added here must be operational state, never user data.
SWEEP_LAST_STARTED_AT = "sweep.last_started_at"
SWEEP_LAST_COMPLETED_AT = "sweep.last_completed_at"
SWEEP_LAST_ERROR = "sweep.last_error"


class SystemState(Base, TimestampMixin):
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Free-form detail for the key (an error message, a count). The
    # authoritative "when" is occurred_at, never updated_at — updated_at
    # moves on any write, including one that only records a failure.
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
