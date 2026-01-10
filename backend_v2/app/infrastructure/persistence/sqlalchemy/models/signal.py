"""Signal ORM Models.

Maps to whale_signals table.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
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

from .base import Base

if TYPE_CHECKING:
    from .whale import Whale


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SignalStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SKIPPED = "SKIPPED"


class SignalConfidence(str, Enum):
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class WhaleSignal(Base):
    """Whale trading signal model."""

    __tablename__ = "whale_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    whale_id: Mapped[int] = mapped_column(
        ForeignKey("whales.id", ondelete="CASCADE"), index=True
    )

    # Trade details
    action: Mapped[SignalAction] = mapped_column(SQLEnum(SignalAction))
    token_in: Mapped[str] = mapped_column(String(50))  # What they sold
    token_out: Mapped[str] = mapped_column(String(50))  # What they bought
    token_in_address: Mapped[str | None] = mapped_column(String(100))
    token_out_address: Mapped[str | None] = mapped_column(String(100))
    amount_in: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    amount_out: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2))

    # DEX/Chain info
    dex: Mapped[str] = mapped_column(String(50))
    chain: Mapped[str] = mapped_column(String(20))
    tx_hash: Mapped[str] = mapped_column(String(100), unique=True)

    # CEX mapping
    cex_symbol: Mapped[str | None] = mapped_column(String(20))  # e.g., BTCUSDT
    cex_available: Mapped[bool] = mapped_column(Boolean, default=False)
    leverage: Mapped[int | None] = mapped_column()

    # Pricing
    price_at_signal: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    price_current: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    # Confidence scoring
    confidence: Mapped[SignalConfidence] = mapped_column(
        SQLEnum(SignalConfidence), default=SignalConfidence.MEDIUM
    )
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("50"))

    # Processing status
    status: Mapped[SignalStatus] = mapped_column(
        SQLEnum(SignalStatus), default=SignalStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    whale: Mapped["Whale"] = relationship(back_populates="signals")

    __table_args__ = (
        Index("ix_whale_signals_status_detected", "status", "detected_at"),
        Index("ix_whale_signals_whale_detected", "whale_id", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<WhaleSignal(id={self.id}, whale_id={self.whale_id}, action={self.action})>"
