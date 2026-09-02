import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class Lead(TimestampMixin, Base):
    """An email address handed over by a marketing tool, not a signup.

    Deliberately its own table rather than a Tenant with no password: a lead
    hasn't agreed to anything a tenant has (terms, a trial clock, a slug).
    `source` says which tool captured it, so a later campaign can be honest
    about where the address came from instead of one undifferentiated list.
    """
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # Free-text context for the source — the URL scanned, the company name
    # typed in, whatever the specific tool captured. Never required.
    context: Mapped[str | None] = mapped_column(String(2048), nullable=True)
