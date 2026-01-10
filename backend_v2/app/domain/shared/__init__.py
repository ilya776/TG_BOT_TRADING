"""Shared Kernel - base classes для всієї domain layer.

Shared Kernel містить building blocks для Domain-Driven Design:
- Entity: Об'єкт з identity
- ValueObject: Immutable об'єкт порівнюваний за значенням
- AggregateRoot: Головний entity в aggregate
- DomainEvent: Подія що сталась в domain
- DomainException: Порушення бізнес-правил
"""

from .aggregate_root import AggregateRoot
from .domain_event import DomainEvent
from .entity import Entity
from .exceptions import (
    AggregateNotFound,
    BusinessRuleViolation,
    ConcurrencyException,
    DomainException,
    InvalidStateTransition,
)
from .value_object import ValueObject, validate_value_object

__all__ = [
    # Base classes
    "Entity",
    "ValueObject",
    "AggregateRoot",
    "DomainEvent",
    # Utilities
    "validate_value_object",
    # Exceptions
    "DomainException",
    "BusinessRuleViolation",
    "AggregateNotFound",
    "InvalidStateTransition",
    "ConcurrencyException",
]
