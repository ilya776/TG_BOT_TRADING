"""Exceptions для Exchange bounded context."""

from app.domain.shared import DomainException


class ExchangeError(DomainException):
    """Base exception для всіх exchange-related errors."""

    pass


class ExchangeConnectionError(ExchangeError):
    """Raised коли не можемо підключитись до біржі."""

    pass


class ExchangeAPIError(ExchangeError):
    """Raised коли exchange API повернув помилку."""

    pass


class RateLimitError(ExchangeError):
    """Raised коли перевищено rate limit біржі.

    Це transient error - треба retry з exponential backoff.
    """

    pass


class CircuitBreakerOpenError(ExchangeError):
    """Raised коли circuit breaker відкритий (too many failures).

    Circuit breaker захищає від cascade failures.
    """

    pass


class InvalidLeverageError(ExchangeError):
    """Raised коли leverage invalid для цього symbol."""

    pass


class AssetNotFoundError(ExchangeError):
    """Raised коли asset не знайдений на біржі."""

    pass


class InsufficientBalanceError(ExchangeError):
    """Raised коли недостатньо балансу для виконання операції."""

    pass


class PositionNotFoundError(ExchangeError):
    """Raised коли futures position не знайдена."""

    pass
