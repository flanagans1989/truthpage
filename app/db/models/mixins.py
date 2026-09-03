from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp. Use instead of datetime.utcnow() (deprecated in 3.12+)."""
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite (tests only — Postgres round-trips tz-aware values) hands
    back a naive datetime; we only ever write UTC into these columns, so
    that's the correct zone to attach. Subtracting one of these from a
    tz-aware now() is otherwise a TypeError that only ever shows up under
    test, which is the worst possible place for it to hide."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class TimestampMixin:
    """Adds created_at / updated_at columns to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
