"""Trade ORM Model - SQLAlchemy mapping для Trade aggregate."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TradeModel(Base):
    """ORM model для Trade aggregate.

    Це ТІЛЬКИ для персистенції - БЕЗ business logic!
    Business logic в domain.trading.entities.Trade.
    """

    __tablename__ = "trades"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    signal_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    # Trade identification
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    exchange_order_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )

    # Trade parameters
    side: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "buy" or "sell"
    trade_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "spot" or "futures"
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # "pending", "filled", "failed", "needs_reconciliation"

    # Amounts (використовуємо Numeric для precision)
    size_usdt: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Execution data (nullable - заповнюється після execution)
    executed_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    executed_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    fee_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optimistic locking (для concurrent updates)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Composite indexes (для performance)
    __table_args__ = (
        # Query: Get user trades by status and date
        Index(
            "ix_trades_user_status_created",
            "user_id",
            "status",
            "created_at",
        ),
        # Query: Get trades by signal
        Index("ix_trades_signal_created", "signal_id", "created_at"),
        # Query: Get trades by symbol and status
        Index("ix_trades_symbol_status", "symbol", "status"),
        # Covering index (включає колонки для уникнення lookup)
        Index(
            "ix_trades_covering",
            "user_id",
            "status",
            postgresql_include=["executed_price", "quantity", "created_at"],
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<TradeModel(id={self.id}, user_id={self.user_id}, "
            f"symbol={self.symbol}, side={self.side}, status={self.status})>"
        )
