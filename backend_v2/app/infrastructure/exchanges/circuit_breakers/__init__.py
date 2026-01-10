"""Circuit breaker pattern для захисту від cascade failures."""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    circuit_breaker_protected,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "circuit_breaker_protected",
]
