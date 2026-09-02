import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class Objection(TimestampMixin, Base):
    """A manually-recorded objection to a sub-processor change — objections
    arrive by email or phone in real life, never through this product, so
    there is no automatic path that creates one. created_at (TimestampMixin)
    is when it was entered into TrustPages; objected_at is the date the
    tenant reports the objection itself arrived, which are not the same
    moment. recorded_by_email is always the authenticated tenant identity
    (never client-supplied), so this row can always say who typed it in."""
    __tablename__ = "objections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("change_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    objector_name: Mapped[str] = mapped_column(String(255), nullable=False)
    objected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_email: Mapped[str] = mapped_column(String(320), nullable=False)

    change_event: Mapped["ChangeEvent"] = relationship(  # noqa: F821
        "ChangeEvent",
        back_populates="objections",
        lazy="raise",
    )
