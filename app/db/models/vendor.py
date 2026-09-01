"""The public vendor directory.

Deliberately not a `Subprocessor`. That table is tenant-scoped: it records
which pages one customer asked us to watch. A directory entry is the
opposite — one canonical page, monitored once by the platform, published to
everyone. Modelling them together would mean scraping Stripe once per
customer and having no answer to "which row is the real one".
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class Vendor(TimestampMixin, Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # URL segment: /vendors/{slug}. Stable — it is the indexed address.
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    monitored_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    homepage_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # A page is published only once a check has produced a usable list. A
    # directory entry with nothing on it is worse than no entry: it wastes a
    # visitor's click and an indexer's crawl.
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )

    # Extracted current state: [{"name": ..., "purpose": ..., "location": ...}]
    entries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    entries_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_browser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    check_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1440, server_default="1440"
    )
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    changes: Mapped[list["VendorChange"]] = relationship(  # noqa: F821
        "VendorChange",
        back_populates="vendor",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class VendorChange(TimestampMixin, Base):
    """One detected movement on a directory page.

    Unlike a tenant's ChangeEvent there is no approval step: nobody's trust
    page depends on it, and a directory that waits for a human is a directory
    that goes stale.
    """

    __tablename__ = "vendor_changes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    new_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_diff: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Names only — the readable half of the change, and what the vendor page
    # and its structured data show.
    added: Mapped[list | None] = mapped_column(JSON, nullable=True)
    removed: Mapped[list | None] = mapped_column(JSON, nullable=True)

    vendor: Mapped["Vendor"] = relationship(
        "Vendor",
        back_populates="changes",
        lazy="raise",
    )
