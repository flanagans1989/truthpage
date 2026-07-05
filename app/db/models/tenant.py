import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, utc_now

SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "canceled", "unpaid")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            f"subscription_status IN {SUBSCRIPTION_STATUSES}",
            name="ck_tenants_subscription_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Owner email — the only address that can sign in to this tenant.
    # Nullable for legacy rows; claimed on first post-migration login.
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paddle_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="trialing",
        server_default="trialing",
    )
    # End of the free trial. Only meaningful while status == "trialing";
    # a paid subscription (status == "active") ignores it.
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def trial_expired(self) -> bool:
        return (
            self.subscription_status == "trialing"
            and self.trial_ends_at is not None
            and self.trial_ends_at <= utc_now()
        )

    subprocessors: Mapped[list["Subprocessor"]] = relationship(  # noqa: F821
        "Subprocessor",
        back_populates="tenant",
        lazy="raise",
    )
    subscribers: Mapped[list["Subscriber"]] = relationship(  # noqa: F821
        "Subscriber",
        back_populates="tenant",
        lazy="raise",
    )
