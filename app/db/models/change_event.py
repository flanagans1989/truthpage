import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, Uuid, false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

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

# The only two values review_action may hold — kept here as the single
# source of truth; app/services/evidence.py's validate_review_action reads
# from the same list (NOT_AVAILABLE handled separately there, since this
# column allows real NULL rather than the string "not_available").
REVIEW_ACTION_NOTICE_RELEASED = "notice_released_by_reviewer"
REVIEW_ACTION_AUTO_PUBLISHED_COSMETIC = "auto_published_cosmetic"
_REVIEW_ACTION_VALUES = (REVIEW_ACTION_NOTICE_RELEASED, REVIEW_ACTION_AUTO_PUBLISHED_COSMETIC)


class FrozenNotificationFieldError(ValueError):
    """PR 4's KURAL 0: once a notice is released, its reviewer identity,
    frozen text, recipient-list size, and objection-window dates never
    change again — see docs/manifest_v2.md. Raised the instant any code
    path tries to overwrite one of these fields with a different value,
    the same hard trip-wire PR 3 uses for timestamp_status."""


# Set exactly once, at release time, by app/services/approval.py — never
# touched again afterward. Guarded below, not just documented.
_FROZEN_ONCE_SET_FIELDS = (
    "reviewed_by_name",
    "reviewed_by_email",
    "reviewed_at",
    "review_action",
    "notice_frozen_subject",
    "notice_frozen_body",
    "notice_frozen_at",
    "recipient_count",
    "window_days",
    "window_closes_at",
)


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
        CheckConstraint(
            f"review_action IS NULL OR review_action IN {_REVIEW_ACTION_VALUES}",
            name="ck_change_events_review_action",
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
    # Whether the tenant was entitled to a downloadable evidence pack at the
    # moment this change was captured. Stamped once and never revisited:
    # cancelling Growth must not retract access to packs already earned. See
    # migration 0022.
    export_entitled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_false()
    )
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

    # [REVIEW] — who actually let this go out, copied at the moment they did
    # (not a foreign key to Tenant: the tenant may later rename itself or
    # its login email, and this record must keep reading what was true at
    # the time, not a live join). NULL for a cosmetic auto-published event
    # (no human reviewed it — review_action says so explicitly rather than
    # a name being silently absent) and for anything not yet approved.
    reviewed_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_action: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # The notice actually released, frozen at the moment it was — a second,
    # independent copy of notice_subject/notice_body above. Those two stay
    # editable (a tenant can still "Redraft" for their own reference after
    # the fact); these two never change again once set, because they are
    # what a subscriber actually received, not what the draft currently
    # reads. See app/core/llm/notice.py's placeholder resolution — unlike
    # notice_body, these have [OBJECTION WINDOW]/[CONTACT] already filled
    # in with real values, since this is the text that was actually sent.
    notice_frozen_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_frozen_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Size of the recipient list at send time — the list itself lives in
    # notification_recipients (one row per address), this is just the count
    # for the manifest/CSV. notified_at (above) doubles as [NOTIFICATION]'s
    # sent_at and [OBJECTION WINDOW]'s window_opened_at — the window opens
    # the moment the notice was sent, not the moment it was approved.
    recipient_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # [OBJECTION WINDOW] — window_days is the tenant's configured length at
    # the moment this window opened (Tenant.objection_window_days can
    # change later without moving this one); window_closes_at is computed
    # once from that and notified_at, not recomputed on every read, so a
    # later config change never shifts a window that already opened.
    window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @validates(*_FROZEN_ONCE_SET_FIELDS)
    def _guard_frozen_notification_fields(self, key: str, value):
        current = self.__dict__.get(key)
        if current is not None and value != current:
            raise FrozenNotificationFieldError(
                f"{key} is frozen once set (KURAL 0) — attempted to change it "
                f"from {current!r} to {value!r}"
            )
        return value

    subprocessor: Mapped["Subprocessor"] = relationship(  # noqa: F821
        "Subprocessor",
        back_populates="change_events",
        lazy="raise",
    )
    notification_recipients: Mapped[list["NotificationRecipient"]] = relationship(  # noqa: F821
        "NotificationRecipient",
        back_populates="change_event",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    objections: Mapped[list["Objection"]] = relationship(  # noqa: F821
        "Objection",
        back_populates="change_event",
        lazy="raise",
        cascade="all, delete-orphan",
    )
