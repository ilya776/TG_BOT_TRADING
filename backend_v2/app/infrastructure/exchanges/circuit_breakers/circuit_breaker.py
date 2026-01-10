"""Circuit Breaker pattern для захисту від cascade failures.

Коли біржа down:
- Без circuit breaker: Кожен trade спробує → timeout → fail (повільно!)
- З circuit breaker: Після N failures → OPEN → fast fail (швидко!)

State Machine:
CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED/OPEN
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Нормальний стан - пропускаємо requests
    OPEN = "OPEN"  # Failure стан - reject requests (fast fail)
    HALF_OPEN = "HALF_OPEN"  # Testing стан - спробуємо 1 request


class CircuitBreakerOpenError(Exception):
    """Exception коли circuit breaker OPEN (fast fail).

    Example:
        >>> raise CircuitBreakerOpenError("Binance circuit open, retry later")
    """

    pass


class CircuitBreaker:
    """Circuit Breaker implementation.

    Args:
        failure_threshold: Кількість failures для відкриття circuit (default: 5).
        timeout_seconds: Скільки секунд circuit залишається OPEN (default: 60).
        success_threshold: Кількість successes в HALF_OPEN для закриття (default: 2).

    Example:
        >>> circuit = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        >>> 
        >>> # CLOSED → 5 failures → OPEN
        >>> for i in range(5):
        ...     await circuit.call(failing_api_call)  # Failures
        >>> # Circuit now OPEN
        >>> 
        >>> await circuit.call(any_call)  # Raises CircuitBreakerOpenError (fast fail)
        >>> 
        >>> # After 60s → HALF_OPEN
        >>> await circuit.call(successful_call)  # Success → back to CLOSED
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Кількість consecutive failures для OPEN.
            timeout_seconds: Скільки секунд тримати circuit OPEN.
            success_threshold: Кількість successes в HALF_OPEN для CLOSED.
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold

        # State
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None

        # Lock для thread-safety
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function через circuit breaker.

        Args:
            func: Async function для виконання.
            *args: Positional arguments для func.
            **kwargs: Keyword arguments для func.

        Returns:
            Result від func.

        Raises:
            CircuitBreakerOpenError: Якщо circuit OPEN.
            Exception: Будь-яка exception від func.
        """
        async with self._lock:
            # Check if circuit should transition from OPEN → HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        "circuit_breaker.half_open",
                        extra={
                            "function": func.__name__,
                            "previous_failures": self._failure_count,
                        },
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    # Circuit still OPEN - fast fail
                    logger.warning(
                        "circuit_breaker.rejected",
                        extra={
                            "function": func.__name__,
                            "state": self._state.value,
                            "failure_count": self._failure_count,
                        },
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker OPEN for {func.__name__}, retry later"
                    )

        # Execute function
        try:
            result = await func(*args, **kwargs)

            # Success - update state
            async with self._lock:
                self._on_success()

            return result

        except Exception as e:
            # Failure - update state
            async with self._lock:
                self._on_failure()

            raise e

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1

            if self._success_count >= self.success_threshold:
                # Достатньо successes - закриваємо circuit
                logger.info(
                    "circuit_breaker.closed",
                    extra={
                        "success_count": self._success_count,
                        "previous_failures": self._failure_count,
                    },
                )
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0

        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now(timezone.utc)

        if self._state == CircuitState.HALF_OPEN:
            # Failure in HALF_OPEN → back to OPEN
            logger.warning(
                "circuit_breaker.reopened",
                extra={
                    "failure_count": self._failure_count,
                },
            )
            self._state = CircuitState.OPEN

        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                # Досягли threshold - відкриваємо circuit
                logger.error(
                    "circuit_breaker.opened",
                    extra={
                        "failure_count": self._failure_count,
                        "threshold": self.failure_threshold,
                    },
                )
                self._state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should transition OPEN → HALF_OPEN."""
        if self._last_failure_time is None:
            return True

        elapsed = datetime.now(timezone.utc) - self._last_failure_time
        return elapsed >= timedelta(seconds=self.timeout_seconds)

    def reset(self) -> None:
        """Manually reset circuit breaker (for testing/admin)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info("circuit_breaker.manual_reset")


def circuit_breaker_protected(
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
    success_threshold: int = 2,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator для захисту function з circuit breaker.

    Args:
        failure_threshold: Кількість failures для OPEN.
        timeout_seconds: Скільки секунд circuit OPEN.
        success_threshold: Кількість successes для CLOSED.

    Returns:
        Decorated function з circuit breaker protection.

    Example:
        >>> @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
        ... async def call_binance_api():
        ...     return await binance.get_balance()
        
        >>> # Circuit відкриється після 5 consecutive failures
        >>> # Далі всі calls fast-fail з CircuitBreakerOpenError
    """
    circuit = CircuitBreaker(
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds,
        success_threshold=success_threshold,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await circuit.call(func, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator
