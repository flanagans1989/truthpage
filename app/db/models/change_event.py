import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class ChangeStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    auto_published = "auto_published"


_STATUS_VALUES = tuple(s.value for s in ChangeStatus)


class ChangeEvent(TimestampMixin, Base):
    __tablename__ = "change_events"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_STATUS_VALUES}",
            name="ck_change_events_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subprocessor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subprocessors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    new_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_diff: Mapped[str] = mapped_column(Text, nullable=False)
    # Full page text on both sides of the change. The diff alone cannot answer
    # "what did this page say in March?" — an auditor asks for the document,
    # not the delta. Nullable because events written before 0006 have neither.
    old_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw HTML either side of the change, for the downloadable evidence
    # bundle. Deliberately not shown on the dashboard page itself — the
    # normalized text above is what a human reads, this is what an auditor
    # asks for. Nullable: events recorded before 0012 have neither.
    old_raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ChangeStatus.pending_review.value,
        server_default=ChangeStatus.pending_review.value,
    )
    # Article 28(2) notice drafted for this change. Stored so the tenant sees
    # the same words every time they open it — regenerating on each view would
    # quietly reword a document they may already have sent.
    notice_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notice_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subprocessor: Mapped["Subprocessor"] = relationship(  # noqa: F821
        "Subprocessor",
        back_populates="change_events",
        lazy="raise",
    )
