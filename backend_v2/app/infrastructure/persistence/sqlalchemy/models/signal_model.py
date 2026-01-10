"""Signal ORM Model - SQLAlchemy mapping для Signal aggregate."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SignalModel(Base):
    """ORM model для Signal aggregate.

    Це ТІЛЬКИ для персистенції - БЕЗ business logic!
    Business logic в domain.signals.entities.Signal.
    """

    __tablename__ = "whale_signals"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign keys
    whale_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    # Signal identification
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # "whale", "indicator", "manual", etc.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default="pending"
    )  # "pending", "processing", "processed", "failed", "expired"
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, default="medium"
    )  # "high", "medium", "low"

    # Signal parameters
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" or "sell"
    trade_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "spot" or "futures"

    # Trade parameters (optional)
    entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    leverage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string для SL/TP, etc.

    # Processing tracking
    trades_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Indexes для performance
    __table_args__ = (
        # Priority queue queries (status + priority + detected_at)
        Index(
            "ix_signals_queue",
            "status",
            "priority",
            "detected_at",
        ),
        # Whale signals queries
        Index("ix_signals_whale_status", "whale_id", "status", "detected_at"),
        # Expiry cleanup queries
        Index("ix_signals_status_detected", "status", "detected_at"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<SignalModel(id={self.id}, whale_id={self.whale_id}, "
            f"symbol={self.symbol}, status={self.status}, priority={self.priority})>"
        )
