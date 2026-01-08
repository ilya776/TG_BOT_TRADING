"""
Trade and Position Models
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

if TYPE_CHECKING:
    from app.models.user import User


class TradeType(str, Enum):
    SPOT = "SPOT"
    FUTURES = "FUTURES"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"


class TradeStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"  # For orphaned trades that need manual review


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class CloseReason(str, Enum):
    MANUAL = "MANUAL"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    WHALE_EXIT = "WHALE_EXIT"
    LIQUIDATION = "LIQUIDATION"
    AUTO_CLOSE = "AUTO_CLOSE"


class Trade(Base):
    """Individual trade records."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Source
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("whale_signals.id", ondelete="SET NULL")
    )
    whale_id: Mapped[int | None] = mapped_column(
        ForeignKey("whales.id", ondelete="SET NULL")
    )
    is_copy_trade: Mapped[bool] = mapped_column(default=True)

    # Exchange details
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(String(100))
    exchange_trade_id: Mapped[str | None] = mapped_column(String(100))

    # Trade details
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trade_type: Mapped[TradeType] = mapped_column(SQLEnum(TradeType))
    side: Mapped[TradeSide] = mapped_column(SQLEnum(TradeSide))
    order_type: Mapped[OrderType] = mapped_column(
        SQLEnum(OrderType), default=OrderType.MARKET
    )

    # Quantities
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 18), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 18), default=Decimal("0")
    )

    # Prices
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))
    executed_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))

    # Value in USDT
    trade_value_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False
    )

    # Leverage (for futures)
    leverage: Mapped[int | None] = mapped_column()

    # Fees
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    fee_currency: Mapped[str | None] = mapped_column(String(20))
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )  # Platform commission

    # Status
    status: Mapped[TradeStatus] = mapped_column(
        SQLEnum(TradeStatus), default=TradeStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="trades")

    __table_args__ = (
        Index("ix_trades_user_status", "user_id", "status"),
        Index("ix_trades_symbol_created", "symbol", "created_at"),
        Index("ix_trades_whale_id", "whale_id"),
    )

    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"


class Position(Base):
    """Open positions tracking."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Source tracking
    whale_id: Mapped[int | None] = mapped_column(
        ForeignKey("whales.id", ondelete="SET NULL")
    )
    entry_trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trades.id", ondelete="SET NULL")
    )
    exit_trade_id: Mapped[int | None] = mapped_column(
        ForeignKey("trades.id", ondelete="SET NULL")
    )

    # Exchange details
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange_position_id: Mapped[str | None] = mapped_column(String(100))

    # Position details
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    position_type: Mapped[TradeType] = mapped_column(SQLEnum(TradeType))
    side: Mapped[TradeSide] = mapped_column(SQLEnum(TradeSide))

    # Quantities
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 18), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(30, 18))

    # Prices
    entry_price: Mapped[Decimal] = mapped_column(Numeric(30, 18), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))

    # Value
    entry_value_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    current_value_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))

    # Leverage (for futures)
    leverage: Mapped[int | None] = mapped_column()
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))

    # Risk management
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))
    stop_loss_order_id: Mapped[str | None] = mapped_column(String(100))  # Exchange SL order ID
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 18))
    take_profit_order_id: Mapped[str | None] = mapped_column(String(100))  # Exchange TP order ID
    trailing_stop_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # PnL
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    unrealized_pnl_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    realized_pnl_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0")
    )

    # Fees
    total_fees: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )

    # Status
    status: Mapped[PositionStatus] = mapped_column(
        SQLEnum(PositionStatus), default=PositionStatus.OPEN
    )
    close_reason: Mapped[CloseReason | None] = mapped_column(SQLEnum(CloseReason))

    # Timestamps
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="positions")

    __table_args__ = (
        Index("ix_positions_user_status", "user_id", "status"),
        Index("ix_positions_symbol_status", "symbol", "status"),
        Index("ix_positions_whale_id", "whale_id"),
    )

    def __repr__(self) -> str:
        return f"<Position(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"

    @property
    def is_profitable(self) -> bool:
        return self.unrealized_pnl > 0 or self.realized_pnl > 0

    @property
    def is_long(self) -> bool:
        return self.side in (TradeSide.BUY, TradeSide.LONG)

    @property
    def is_short(self) -> bool:
        return self.side in (TradeSide.SELL, TradeSide.SHORT)
