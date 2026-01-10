"""Whale ORM Models.

Maps to whales, whale_stats, user_whale_follows tables.
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
    from .signal import WhaleSignal
    from .user import User


class WhaleChain(str, Enum):
    ETH = "ETH"
    BSC = "BSC"
    ARB = "ARB"
    SOL = "SOL"
    BASE = "BASE"
    POLYGON = "POLYGON"
    HYPERLIQUID = "HYPERLIQUID"


class WhaleRank(str, Enum):
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"
    DIAMOND = "DIAMOND"


class Whale(Base):
    """Whale trader model."""

    __tablename__ = "whales"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    chain: Mapped[WhaleChain] = mapped_column(SQLEnum(WhaleChain), default=WhaleChain.ETH)

    # Profile
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(500))  # Comma-separated
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # Scoring
    rank: Mapped[WhaleRank] = mapped_column(SQLEnum(WhaleRank), default=WhaleRank.BRONZE)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    stats: Mapped["WhaleStats | None"] = relationship(
        back_populates="whale", uselist=False, cascade="all, delete-orphan"
    )
    signals: Mapped[list["WhaleSignal"]] = relationship(
        back_populates="whale", cascade="all, delete-orphan"
    )
    followers: Mapped[list["UserWhaleFollow"]] = relationship(
        back_populates="whale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_whales_chain_rank", "chain", "rank"),
        Index("ix_whales_score", "score"),
    )

    def __repr__(self) -> str:
        return f"<Whale(id={self.id}, name={self.name})>"


class WhaleStats(Base):
    """Whale performance statistics."""

    __tablename__ = "whale_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    whale_id: Mapped[int] = mapped_column(
        ForeignKey("whales.id", ondelete="CASCADE"), unique=True
    )

    # Trade counts
    total_trades: Mapped[int] = mapped_column(default=0)
    winning_trades: Mapped[int] = mapped_column(default=0)
    losing_trades: Mapped[int] = mapped_column(default=0)

    # Performance metrics
    win_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    total_volume_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    total_profit_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    avg_profit_percent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    avg_loss_percent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    max_drawdown_percent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    # Trading patterns
    avg_holding_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    trades_per_week: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    # Recent performance
    profit_7d: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    profit_30d: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    profit_90d: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))

    # Timestamps
    last_trade_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    whale: Mapped["Whale"] = relationship(back_populates="stats")

    def __repr__(self) -> str:
        return f"<WhaleStats(whale_id={self.whale_id}, win_rate={self.win_rate})>"


class UserWhaleFollow(Base):
    """User-Whale follow relationship with copy trading settings."""

    __tablename__ = "user_whale_follows"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    whale_id: Mapped[int] = mapped_column(
        ForeignKey("whales.id", ondelete="CASCADE"), index=True
    )

    # Copy trading settings
    auto_copy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_size_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    trade_size_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    trading_mode_override: Mapped[str | None] = mapped_column(String(20))

    # Notifications
    notify_on_trade: Mapped[bool] = mapped_column(Boolean, default=True)

    # Statistics
    trades_copied: Mapped[int] = mapped_column(default=0)
    total_profit: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))

    # Timestamps
    followed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="whale_follows")
    whale: Mapped["Whale"] = relationship(back_populates="followers")

    __table_args__ = (
        Index("ix_user_whale_follows_user_whale", "user_id", "whale_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserWhaleFollow(user_id={self.user_id}, whale_id={self.whale_id})>"
