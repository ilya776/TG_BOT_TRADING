"""Signals Bounded Context - Domain Layer.

Exports:
    Entities: Signal (Aggregate Root)
    Value Objects: SignalStatus, SignalPriority, SignalSource, SignalType, TradeSide
    Services: SignalQueue (Domain Service)
    Events: SignalDetectedEvent, SignalProcessedEvent, SignalFailedEvent
    Repositories: SignalRepository (interface)
"""

# Entities (Aggregate Roots)
from .entities import Signal

# Value Objects
from .value_objects import (
    SignalStatus,
    SignalPriority,
    SignalSource,
    SignalType,
    TradeSide,
    TradeType,
)

# Domain Services
from .services import SignalQueue

# Events
from .events import (
    SignalDetectedEvent,
    SignalProcessedEvent,
    SignalFailedEvent,
    SignalProcessingStartedEvent,
)

# Repository interfaces
from .repositories import SignalRepository

__all__ = [
    # Entities
    "Signal",
    # Value Objects
    "SignalStatus",
    "SignalPriority",
    "SignalSource",
    "SignalType",
    "TradeSide",
    "TradeType",
    # Domain Services
    "SignalQueue",
    # Events
    "SignalDetectedEvent",
    "SignalProcessedEvent",
    "SignalFailedEvent",
    "SignalProcessingStartedEvent",
    # Repositories
    "SignalRepository",
]
