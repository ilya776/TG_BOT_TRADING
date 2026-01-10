"""Position ORM Model - SQLAlchemy mapping для Position aggregate."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PositionModel(Base):
    """ORM model для Position aggregate.

    Це ТІЛЬКИ для персистенції - БЕЗ business logic!
    Business logic в domain.trading.entities.Position.
    """

    __tablename__ = "positions"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entry_trade_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trades.id"), nullable=False, index=True
    )
    exit_trade_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trades.id"), nullable=True, index=True
    )

    # Position identification
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "long" or "short"
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # "open", "closed", "liquidated"

    # Position parameters
    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Risk management (nullable - може не бути SL/TP)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    take_profit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )

    # Exit data (nullable - заповнюється при закритті)
    exit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )

    # PnL (unrealized завжди є, realized тільки після закриття)
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )

    # Timestamps
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Optimistic locking
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Composite indexes (для performance)
    __table_args__ = (
        # Query: Get user open positions by symbol
        Index(
            "ix_positions_user_status_symbol",
            "user_id",
            "status",
            "symbol",
        ),
        # Query: Get open positions sorted by PnL
        Index("ix_positions_open_pnl", "status", "unrealized_pnl"),
        # Query: Get positions by entry trade
        Index("ix_positions_entry_trade", "entry_trade_id"),
        # Covering index для dashboard queries
        Index(
            "ix_positions_covering",
            "user_id",
            "status",
            postgresql_include=["symbol", "unrealized_pnl", "entry_price", "quantity"],
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PositionModel(id={self.id}, user_id={self.user_id}, "
            f"symbol={self.symbol}, side={self.side}, status={self.status})>"
        )
