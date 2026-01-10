"""Trade and Position ORM Models.

Maps to trades and positions tables.
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
    from .user import User


class TradeStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeType(str, Enum):
    SPOT = "SPOT"
    FUTURES = "FUTURES"


class CloseReason(str, Enum):
    MANUAL = "MANUAL"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    LIQUIDATION = "LIQUIDATION"
    WHALE_SOLD = "WHALE_SOLD"
    AUTO_CLOSE = "AUTO_CLOSE"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class Trade(Base):
    """Trade execution model."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("whale_signals.id", ondelete="SET NULL")
    )
    whale_id: Mapped[int | None] = mapped_column(
        ForeignKey("whales.id", ondelete="SET NULL")
    )

    # Trade origin
    is_copy_trade: Mapped[bool] = mapped_column(Boolean, default=True)

    # Exchange info
    exchange: Mapped[str] = mapped_column(String(20))  # BINANCE, BYBIT, etc.
    exchange_order_id: Mapped[str | None] = mapped_column(String(100))

    # Trade details
    symbol: Mapped[str] = mapped_column(String(20))
    trade_type: Mapped[TradeType] = mapped_column(SQLEnum(TradeType))
    side: Mapped[TradeSide] = mapped_column(SQLEnum(TradeSide))

    # Quantities
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10), default=Decimal("0"))

    # Prices
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    executed_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    # Values in USDT
    trade_value_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 8))

    # Futures specific
    leverage: Mapped[int | None] = mapped_column()

    # Fees
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    fee_currency: Mapped[str] = mapped_column(String(10), default="USDT")
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))

    # Status
    status: Mapped[TradeStatus] = mapped_column(
        SQLEnum(TradeStatus), default=TradeStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="trades")
    position: Mapped["Position | None"] = relationship(
        back_populates="entry_trade",
        foreign_keys="Position.entry_trade_id",
    )

    __table_args__ = (
        Index("ix_trades_user_status", "user_id", "status"),
        Index("ix_trades_created_at", "created_at"),
        Index("ix_trades_signal_id", "signal_id"),
    )

    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol}, status={self.status})>"


class Position(Base):
    """Position tracking model."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    whale_id: Mapped[int | None] = mapped_column(
        ForeignKey("whales.id", ondelete="SET NULL")
    )

    # Entry trade reference
    entry_trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trades.id", ondelete="SET NULL")
    )
    exit_trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trades.id", ondelete="SET NULL")
    )

    # Position details
    exchange: Mapped[str] = mapped_column(String(20))
    symbol: Mapped[str] = mapped_column(String(20))
    position_type: Mapped[TradeType] = mapped_column(SQLEnum(TradeType))
    side: Mapped[str] = mapped_column(String(10))  # BUY/SELL

    # Quantities
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10))

    # Prices
    entry_price: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    # Values in USDT
    entry_value_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    current_value_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))

    # Futures specific
    leverage: Mapped[int | None] = mapped_column()
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    # Risk management
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    trailing_stop_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # PnL
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    unrealized_pnl_percent: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    realized_pnl_percent: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))

    # Fees
    total_fees: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))

    # Status
    status: Mapped[PositionStatus] = mapped_column(
        SQLEnum(PositionStatus), default=PositionStatus.OPEN
    )
    close_reason: Mapped[CloseReason | None] = mapped_column(SQLEnum(CloseReason))

    # Timestamps
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="positions")
    entry_trade: Mapped["Trade | None"] = relationship(
        back_populates="position",
        foreign_keys=[entry_trade_id],
    )

    __table_args__ = (
        Index("ix_positions_user_status", "user_id", "status"),
        Index("ix_positions_symbol", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<Position(id={self.id}, symbol={self.symbol}, status={self.status})>"
