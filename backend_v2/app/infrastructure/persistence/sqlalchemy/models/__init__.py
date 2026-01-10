"""SQLAlchemy ORM models.

Full database models for the trading system, compatible with original backend schema.
"""

from .base import Base

# User models
from .user import (
    User,
    UserSettings,
    UserAPIKey,
    UserExchangeBalance,
    SubscriptionTier,
    TradingMode,
    ExchangeName,
)

# Whale models
from .whale import (
    Whale,
    WhaleStats,
    UserWhaleFollow,
    WhaleChain,
    WhaleRank,
)

# Signal models
from .signal import (
    WhaleSignal,
    SignalAction,
    SignalStatus,
    SignalConfidence,
)

# Trade models
from .trade import (
    Trade,
    Position,
    TradeStatus,
    TradeSide,
    TradeType,
    CloseReason,
    PositionStatus,
)

__all__ = [
    # Base
    "Base",
    # User
    "User",
    "UserSettings",
    "UserAPIKey",
    "UserExchangeBalance",
    "SubscriptionTier",
    "TradingMode",
    "ExchangeName",
    # Whale
    "Whale",
    "WhaleStats",
    "UserWhaleFollow",
    "WhaleChain",
    "WhaleRank",
    # Signal
    "WhaleSignal",
    "SignalAction",
    "SignalStatus",
    "SignalConfidence",
    # Trade
    "Trade",
    "Position",
    "TradeStatus",
    "TradeSide",
    "TradeType",
    "CloseReason",
    "PositionStatus",
]
