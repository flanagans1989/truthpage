import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class ChangeStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    auto_published = "auto_published"


_STATUS_VALUES = tuple(s.value for s in ChangeStatus)


class TimestampStatus(str, enum.Enum):
    """RFC 3161 independent-timestamp state for this event's `new_raw_html`
    digest. `not_available_pre_tsa` is TERMINAL and permanent — it means
    this event was recorded before independent timestamping existed at
    all, and no code path may ever move a record out of it. Backdating a
    timestamp onto a pre-existing capture would make this product assert a
    document existed at a time it did not; see docs/manifest_v2.md."""
    pending = "pending"
    retrying = "retrying"
    timestamped = "timestamped"
    failed = "failed"
    not_available_pre_tsa = "not_available_pre_tsa"


_TIMESTAMP_STATUS_VALUES = tuple(s.value for s in TimestampStatus)


class ChangeEvent(TimestampMixin, Base):
    __tablename__ = "change_events"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_STATUS_VALUES}",
            name="ck_change_events_status",
        ),
        CheckConstraint(
            f"timestamp_status IN {_TIMESTAMP_STATUS_VALUES}",
            name="ck_change_events_timestamp_status",
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
    # SHA-256 of old_raw_html / new_raw_html — the digest of the document
    # itself. Deliberately separate from old_hash/new_hash above, which hash
    # the normalized text change detection compares; those two would not
    # match a hash a tenant computes over the downloaded before.html/after.html.
    old_raw_html_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_raw_html_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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

    # RFC 3161 independent timestamp over new_raw_html_hash — never over the
    # content itself (see app/core/tsa.py). Every row backfills to
    # not_available_pre_tsa (server_default) on migration: a pre-existing
    # capture never becomes eligible for a timestamp after the fact. Rows
    # created after this shipped are explicitly set to `pending` at insert
    # time — the default is deliberately the safe, inert state, not an
    # assumption that new code remembered to opt in.
    timestamp_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=TimestampStatus.not_available_pre_tsa.value,
        server_default=TimestampStatus.not_available_pre_tsa.value,
    )
    # Raw .tsr token bytes, stored the same way new_raw_html is (a DB column,
    # no object-storage layer) — just binary rather than text.
    tsa_token: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Which of TSA_PRIMARY_URL / TSA_FALLBACK_URL actually issued the token
    # that's stored (or attempted last), so a reader never has to guess.
    tsa_authority_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # The time the TSA itself reported inside the token — not utc_now() at
    # request time, and never backfilled for a status other than
    # `timestamped`.
    tsa_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tsa_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tsa_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    subprocessor: Mapped["Subprocessor"] = relationship(  # noqa: F821
        "Subprocessor",
        back_populates="change_events",
        lazy="raise",
    )
