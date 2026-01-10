"""
Whale Signal Models
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
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

from app.database import Base
from app.models.whale import Whale


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    ADD_LIQUIDITY = "ADD_LIQUIDITY"
    REMOVE_LIQUIDITY = "REMOVE_LIQUIDITY"


class SignalConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class SignalStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class WhaleSignal(Base):
    """Detected whale transaction signals."""

    __tablename__ = "whale_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    whale_id: Mapped[int] = mapped_column(
        ForeignKey("whales.id", ondelete="CASCADE"), index=True
    )

    # Transaction details
    tx_hash: Mapped[str] = mapped_column(
        String(66), unique=True, nullable=False, index=True
    )
    block_number: Mapped[int] = mapped_column(nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)

    # Trade details
    action: Mapped[SignalAction] = mapped_column(SQLEnum(SignalAction))
    dex: Mapped[str] = mapped_column(String(50), nullable=False)

    # Token information
    token_in: Mapped[str] = mapped_column(String(100), nullable=False)
    token_in_address: Mapped[str] = mapped_column(String(42))
    token_in_amount: Mapped[Decimal] = mapped_column(Numeric(30, 18))

    token_out: Mapped[str] = mapped_column(String(100), nullable=False)
    token_out_address: Mapped[str] = mapped_column(String(42))
    token_out_amount: Mapped[Decimal] = mapped_column(Numeric(30, 18))

    # USD values
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )
    price_at_signal: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))

    # CEX mapping (for copy trading)
    cex_symbol: Mapped[str | None] = mapped_column(
        String(20)
    )  # e.g., "PEPEUSDT"
    cex_available: Mapped[bool] = mapped_column(default=False)

    # Signal quality
    confidence: Mapped[SignalConfidence] = mapped_column(
        SQLEnum(SignalConfidence), default=SignalConfidence.MEDIUM
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("50")
    )

    # Processing status
    status: Mapped[SignalStatus] = mapped_column(
        SQLEnum(SignalStatus), default=SignalStatus.PENDING
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Close signal indicator (True when whale is closing a position)
    is_close: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    gas_price_gwei: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    gas_used: Mapped[int | None] = mapped_column()

    # Raw data (for debugging)
    raw_data: Mapped[str | None] = mapped_column(Text)  # JSON string

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    tx_timestamp: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    whale: Mapped["Whale"] = relationship(back_populates="signals")

    __table_args__ = (
        Index("ix_whale_signals_status_detected", "status", "detected_at"),
        Index("ix_whale_signals_action_confidence", "action", "confidence"),
        Index("ix_whale_signals_cex_symbol", "cex_symbol"),
    )

    def __repr__(self) -> str:
        return f"<WhaleSignal(id={self.id}, whale_id={self.whale_id}, action={self.action}, token={self.token_out})>"

    @property
    def is_buy(self) -> bool:
        return self.action == SignalAction.BUY

    @property
    def is_sell(self) -> bool:
        return self.action == SignalAction.SELL

    @property
    def is_large_trade(self) -> bool:
        return self.amount_usd >= Decimal("50000")

    @property
    def is_whale_sized(self) -> bool:
        return self.amount_usd >= Decimal("100000")
