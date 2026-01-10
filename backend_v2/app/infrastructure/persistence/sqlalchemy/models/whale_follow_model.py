"""WhaleFollow ORM Models - SQLAlchemy mapping для whale following.

Ці моделі є КОПІЯМИ існуючих моделей з backend/ для використання в Clean Architecture.
Вони дзеркалять таблиці: whales, user_whale_follows, users.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ExchangeName(str, Enum):
    """Exchange names (mirror of backend/app/models/user.py)."""

    BINANCE = "BINANCE"
    OKX = "OKX"
    BYBIT = "BYBIT"
    BITGET = "BITGET"


class TradingMode(str, Enum):
    """Trading mode (mirror of backend/app/models/user.py)."""

    SPOT = "SPOT"
    FUTURES = "FUTURES"


class UserModel(Base):
    """User ORM model (subset of fields needed for whale following).

    Full model is in backend/app/models/user.py.
    Це read-only view для WhaleFollowRepository.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Trading settings (relevant for copy trading)
    trading_mode: Mapped[TradingMode] = mapped_column(
        SQLEnum(TradingMode), default=TradingMode.SPOT
    )
    preferred_exchange: Mapped[ExchangeName] = mapped_column(
        SQLEnum(ExchangeName), default=ExchangeName.BINANCE
    )
    default_leverage: Mapped[int] = mapped_column(Integer, default=5)
    max_leverage: Mapped[int] = mapped_column(Integer, default=10)

    # Copy trading global settings
    copy_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    whale_follows: Mapped[list["UserWhaleFollowModel"]] = relationship(
        back_populates="user"
    )


class WhaleModel(Base):
    """Whale ORM model (subset of fields for whale following).

    Full model is in backend/app/models/whale.py.
    """

    __tablename__ = "whales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # CEX Trader fields
    exchange: Mapped[str | None] = mapped_column(String(20))

    # Relationships
    followers: Mapped[list["UserWhaleFollowModel"]] = relationship(
        back_populates="whale"
    )


class UserWhaleFollowModel(Base):
    """User-Whale follow relationship model.

    Mirror of backend/app/models/whale.py UserWhaleFollow.
    """

    __tablename__ = "user_whale_follows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    whale_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("whales.id", ondelete="CASCADE"), index=True
    )

    # Copy settings for this whale
    auto_copy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_size_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    trade_size_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Mode override (null = use user default)
    trading_mode_override: Mapped[str | None] = mapped_column(String(20))

    # Notifications
    notify_on_trade: Mapped[bool] = mapped_column(Boolean, default=True)

    # Statistics
    trades_copied: Mapped[int] = mapped_column(Integer, default=0)
    total_profit: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )

    # Timestamps
    followed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="whale_follows")
    whale: Mapped["WhaleModel"] = relationship(back_populates="followers")

    __table_args__ = (
        UniqueConstraint("user_id", "whale_id", name="uq_user_whale"),
        Index("ix_user_whale_follows_auto_copy", "auto_copy_enabled"),
        Index("ix_user_whale_follows_whale_auto", "whale_id", "auto_copy_enabled"),
    )

    def __repr__(self) -> str:
        return f"<UserWhaleFollowModel(user_id={self.user_id}, whale_id={self.whale_id})>"
