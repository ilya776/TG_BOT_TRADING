"""
Whale Models
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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.signal import WhaleSignal
    from app.models.user import User


class WhaleChain(str, Enum):
    ETHEREUM = "ETHEREUM"
    BSC = "BSC"
    POLYGON = "POLYGON"
    ARBITRUM = "ARBITRUM"
    OPTIMISM = "OPTIMISM"


class WhaleRank(str, Enum):
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"
    DIAMOND = "DIAMOND"


class Whale(Base):
    """Tracked whale wallets."""

    __tablename__ = "whales"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    wallet_address: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    chain: Mapped[WhaleChain] = mapped_column(
        SQLEnum(WhaleChain), default=WhaleChain.ETHEREUM
    )

    # Description
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(500))  # Comma-separated

    # Social links (optional)
    twitter_handle: Mapped[str | None] = mapped_column(String(100))
    ens_name: Mapped[str | None] = mapped_column(String(255))

    # Ranking
    rank: Mapped[WhaleRank] = mapped_column(
        SQLEnum(WhaleRank), default=WhaleRank.BRONZE
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0")
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    # Discovery metadata
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    discovered_by: Mapped[str] = mapped_column(
        String(50), default="system"
    )  # "system" or "manual" or user_id

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # CEX Trader fields (for exchange-based tracking)
    whale_type: Mapped[str | None] = mapped_column(
        String(20), default="CEX_TRADER"
    )  # CEX_TRADER, ON_CHAIN
    exchange: Mapped[str | None] = mapped_column(String(20))  # BINANCE, OKX, BITGET
    exchange_uid: Mapped[str | None] = mapped_column(String(100))  # Trader UID on exchange

    # Data status and polling
    data_status: Mapped[str | None] = mapped_column(
        String(30), default="ACTIVE"
    )  # ACTIVE, SHARING_DISABLED, ERROR
    consecutive_empty_checks: Mapped[int | None] = mapped_column(Integer, default=0)
    last_position_check: Mapped[datetime | None] = mapped_column(DateTime)
    last_position_found: Mapped[datetime | None] = mapped_column(DateTime)
    sharing_disabled_at: Mapped[datetime | None] = mapped_column(DateTime)
    sharing_recheck_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Priority for polling frequency
    priority_score: Mapped[int | None] = mapped_column(Integer, default=50)  # 0-100
    polling_interval_seconds: Mapped[int | None] = mapped_column(Integer, default=60)

    # Relationships
    stats: Mapped["WhaleStats | None"] = relationship(
        back_populates="whale", uselist=False, cascade="all, delete-orphan"
    )
    followers: Mapped[list["UserWhaleFollow"]] = relationship(
        back_populates="whale", cascade="all, delete-orphan"
    )
    signals: Mapped[list["WhaleSignal"]] = relationship(
        back_populates="whale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_whales_chain_active", "chain", "is_active"),
        Index("ix_whales_rank_score", "rank", "score"),
    )

    def __repr__(self) -> str:
        return f"<Whale(id={self.id}, name={self.name}, address={self.wallet_address[:10]}...)>"


class WhaleStats(Base):
    """Whale performance statistics."""

    __tablename__ = "whale_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    whale_id: Mapped[int] = mapped_column(
        ForeignKey("whales.id", ondelete="CASCADE"), unique=True
    )

    # Trade statistics
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)

    # Financial metrics
    total_volume_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0")
    )
    total_profit_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0")
    )
    total_loss_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0")
    )

    # Performance metrics
    win_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )  # Percentage
    avg_profit_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )
    avg_loss_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )
    max_drawdown_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )

    # Timing metrics
    avg_holding_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )
    trades_per_week: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )

    # Last activity
    last_trade_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Time-based performance
    profit_7d: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0")
    )
    profit_30d: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0")
    )
    profit_90d: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0")
    )

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    whale: Mapped["Whale"] = relationship(back_populates="stats")

    def __repr__(self) -> str:
        return f"<WhaleStats(whale_id={self.whale_id}, win_rate={self.win_rate}%)>"


class UserWhaleFollow(Base):
    """Many-to-many relationship between users and whales they follow."""

    __tablename__ = "user_whale_follows"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    whale_id: Mapped[int] = mapped_column(
        ForeignKey("whales.id", ondelete="CASCADE"), index=True
    )

    # Copy settings for this whale
    auto_copy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_size_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    trade_size_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2)
    )  # % of balance

    # Mode override
    trading_mode_override: Mapped[str | None] = mapped_column(
        String(20)
    )  # SPOT, FUTURES, or null for default

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
    user: Mapped["User"] = relationship(back_populates="whale_follows")
    whale: Mapped["Whale"] = relationship(back_populates="followers")

    __table_args__ = (
        UniqueConstraint("user_id", "whale_id", name="uq_user_whale"),
        Index("ix_user_whale_follows_auto_copy", "auto_copy_enabled"),
    )

    def __repr__(self) -> str:
        return f"<UserWhaleFollow(user_id={self.user_id}, whale_id={self.whale_id})>"
