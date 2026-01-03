"""
Subscription and Payment Models
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import SubscriptionTier

if TYPE_CHECKING:
    from app.models.user import User


class SubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PAST_DUE = "PAST_DUE"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, Enum):
    TELEGRAM_STARS = "TELEGRAM_STARS"
    CRYPTO_USDT = "CRYPTO_USDT"
    CRYPTO_BTC = "CRYPTO_BTC"
    STRIPE = "STRIPE"


class Subscription(Base):
    """User subscription records."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Subscription details
    tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE
    )

    # Pricing
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # Dates
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    current_period_start: Mapped[datetime] = mapped_column(DateTime)
    current_period_end: Mapped[datetime] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Auto-renewal
    auto_renew: Mapped[bool] = mapped_column(default=True)
    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SQLEnum(PaymentMethod)
    )

    # External IDs (for payment processors)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscription")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_subscriptions_status_tier", "status", "tier"),
        Index("ix_subscriptions_period_end", "current_period_end"),
    )

    def __repr__(self) -> str:
        return f"<Subscription(user_id={self.user_id}, tier={self.tier}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        return self.status == SubscriptionStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        return self.status == SubscriptionStatus.EXPIRED or (
            self.current_period_end and datetime.utcnow() > self.current_period_end
        )


class Payment(Base):
    """Payment transaction records."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Payment details
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod), nullable=False
    )

    # Status
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus), default=PaymentStatus.PENDING
    )

    # Description
    description: Mapped[str | None] = mapped_column(String(500))

    # For subscription payments
    period_start: Mapped[datetime | None] = mapped_column(DateTime)
    period_end: Mapped[datetime | None] = mapped_column(DateTime)

    # External IDs
    external_payment_id: Mapped[str | None] = mapped_column(
        String(100), unique=True
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(100))

    # Crypto payment details
    crypto_address: Mapped[str | None] = mapped_column(String(100))
    crypto_tx_hash: Mapped[str | None] = mapped_column(String(100))
    crypto_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)

    # Refund tracking
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime)
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    refund_reason: Mapped[str | None] = mapped_column(String(500))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="payments"
    )

    __table_args__ = (
        Index("ix_payments_user_status", "user_id", "status"),
        Index("ix_payments_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"
