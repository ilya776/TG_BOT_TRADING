"""Trading Bounded Context - Domain Layer.

Exports:
    Entities: Trade, Position (Aggregate Roots)
    Value Objects: TradeStatus, TradeSide, TradeType, PositionStatus, PositionSide
    Exceptions: InvalidTradeStateError, InvalidTradeSizeError, InsufficientBalanceError
    Events: TradeExecutedEvent, TradeFailed, PositionOpenedEvent, PositionClosedEvent
    Repositories: TradeRepository, PositionRepository (interfaces)
"""

# Entities (Aggregate Roots)
from .entities import Trade, Position

# Value Objects
from .value_objects import (
    TradeStatus,
    TradeSide,
    TradeType,
    PositionStatus,
    PositionSide,
)

# Exceptions
from .exceptions import (
    InvalidTradeStateError,
    InvalidTradeSizeError,
    InsufficientBalanceError,
)

# Events
from .events import (
    TradeExecutedEvent,
    TradeFailedEvent,
    TradeNeedsReconciliationEvent,
    PositionOpenedEvent,
    PositionClosedEvent,
    PositionLiquidatedEvent,
    StopLossTriggeredEvent,
    TakeProfitTriggeredEvent,
)

# Repository interfaces
from .repositories import TradeRepository, PositionRepository

__all__ = [
    # Entities
    "Trade",
    "Position",
    # Value Objects
    "TradeStatus",
    "TradeSide",
    "TradeType",
    "PositionStatus",
    "PositionSide",
    # Exceptions
    "InvalidTradeStateError",
    "InvalidTradeSizeError",
    "InsufficientBalanceError",
    # Events
    "TradeExecutedEvent",
    "TradeFailedEvent",
    "TradeNeedsReconciliationEvent",
    "PositionOpenedEvent",
    "PositionClosedEvent",
    "PositionLiquidatedEvent",
    "StopLossTriggeredEvent",
    "TakeProfitTriggeredEvent",
    # Repositories
    "TradeRepository",
    "PositionRepository",
]
