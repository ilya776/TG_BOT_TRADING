"""Exceptions для Exchange bounded context."""

from .exchange_exceptions import (
    AssetNotFoundError,
    CircuitBreakerOpenError,
    ExchangeAPIError,
    ExchangeConnectionError,
    ExchangeError,
    InsufficientBalanceError,
    InvalidLeverageError,
    PositionNotFoundError,
    RateLimitError,
)

__all__ = [
    "ExchangeError",
    "ExchangeConnectionError",
    "ExchangeAPIError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "InvalidLeverageError",
    "AssetNotFoundError",
    "InsufficientBalanceError",
    "PositionNotFoundError",
]
