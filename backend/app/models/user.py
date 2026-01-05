"""
User Models
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

from app.database import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.trade import Position, Trade
    from app.models.whale import UserWhaleFollow


class SubscriptionTier(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    ELITE = "ELITE"


class TradingMode(str, Enum):
    SPOT = "SPOT"
    FUTURES = "FUTURES"
    MIXED = "MIXED"


class ExchangeName(str, Enum):
    BINANCE = "BINANCE"
    OKX = "OKX"
    BYBIT = "BYBIT"


class User(Base):
    """Main user model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(10), default="en")

    # Balance tracking (in USDT equivalent)
    total_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )

    # Subscription
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    # 2FA
    totp_secret: Mapped[str | None] = mapped_column(String(32))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["UserAPIKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    whale_follows: Mapped[list["UserWhaleFollow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    trades: Mapped[list["Trade"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    positions: Mapped[list["Position"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", uselist=False
    )

    __table_args__ = (
        Index("ix_users_subscription_tier", "subscription_tier"),
        Index("ix_users_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"


class UserSettings(Base):
    """User trading settings and preferences."""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    # Trading mode
    trading_mode: Mapped[TradingMode] = mapped_column(
        SQLEnum(TradingMode), default=TradingMode.SPOT
    )
    preferred_exchange: Mapped[ExchangeName] = mapped_column(
        SQLEnum(ExchangeName), default=ExchangeName.BINANCE
    )

    # Copy trading settings
    auto_copy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_copy_delay_seconds: Mapped[int] = mapped_column(default=10)
    default_trade_size_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("100")
    )
    max_trade_size_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("1000")
    )

    # Risk management
    stop_loss_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("10")
    )
    take_profit_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    daily_loss_limit_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("500")
    )
    max_open_positions: Mapped[int] = mapped_column(default=5)

    # Futures settings
    default_leverage: Mapped[int] = mapped_column(default=5)
    max_leverage: Mapped[int] = mapped_column(default=10)

    # Notifications
    notify_whale_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_trade_executed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_position_closed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_stop_loss_hit: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id})>"


class UserAPIKey(Base):
    """Encrypted exchange API keys for users."""

    __tablename__ = "user_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    exchange: Mapped[ExchangeName] = mapped_column(SQLEnum(ExchangeName))

    # Encrypted credentials
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    passphrase_encrypted: Mapped[str | None] = mapped_column(Text)  # OKX only

    # Metadata
    label: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_testnet: Mapped[bool] = mapped_column(Boolean, default=False)

    # Permissions (for reference, not enforced here)
    can_spot_trade: Mapped[bool] = mapped_column(Boolean, default=True)
    can_futures_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    can_withdraw: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="api_keys")

    __table_args__ = (
        Index("ix_user_api_keys_user_exchange", "user_id", "exchange"),
    )

    def __repr__(self) -> str:
        return f"<UserAPIKey(user_id={self.user_id}, exchange={self.exchange})>"


class UserExchangeBalance(Base):
    """Per-exchange balance tracking for users."""

    __tablename__ = "user_exchange_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exchange: Mapped[ExchangeName] = mapped_column(SQLEnum(ExchangeName))

    # Spot balances (in USDT equivalent)
    spot_total_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    spot_available_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )

    # Futures balances (in USDT equivalent)
    futures_total_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    futures_available_usdt: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )
    futures_unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0")
    )

    # Detailed asset breakdown (JSON)
    spot_assets: Mapped[str | None] = mapped_column(Text)  # JSON string
    futures_assets: Mapped[str | None] = mapped_column(Text)  # JSON string

    # Connection status
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync_error: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_user_exchange_balances_user_exchange", "user_id", "exchange", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserExchangeBalance(user_id={self.user_id}, exchange={self.exchange})>"

    @property
    def total_usdt(self) -> Decimal:
        """Total balance across spot and futures."""
        return self.spot_total_usdt + self.futures_total_usdt

    @property
    def available_usdt(self) -> Decimal:
        """Available balance across spot and futures."""
        return self.spot_available_usdt + self.futures_available_usdt
