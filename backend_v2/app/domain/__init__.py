"""Domain Layer - Pure Business Logic.

This layer contains:
- Bounded Contexts (Trading, Signals, Exchanges, Whales)
- Aggregate Roots (Trade, Position, Signal)
- Value Objects (immutable domain primitives)
- Domain Services (SignalQueue)
- Domain Events (for decoupling)
- Repository Interfaces (ports)

Key Principles:
- Zero dependencies on infrastructure
- Pure business logic only
- Rich domain models (not anemic)
- Ubiquitous language

Bounded Contexts:
- trading: Trade execution, position management
- signals: Signal detection and queue processing
- exchanges: Exchange abstraction (ports)
- whales: Whale tracking and following
- shared: Common base classes
"""

# Shared kernel
from .shared import AggregateRoot, DomainEvent, BusinessRuleViolation

__all__ = [
    "AggregateRoot",
    "DomainEvent",
    "BusinessRuleViolation",
]
