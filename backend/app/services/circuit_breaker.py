"""
Circuit Breaker Pattern Implementation for Exchange APIs

Protects the system from cascading failures when exchange APIs become unavailable.
Uses Redis for distributed state management across multiple workers.

States:
- CLOSED: Normal operation, requests go through
- OPEN: Too many failures, requests blocked immediately (fast-fail)
- HALF_OPEN: Testing recovery, limited requests allowed

Usage:
    breaker = CircuitBreaker("binance")

    if not breaker.can_execute():
        raise CircuitOpenError("Exchange unavailable")

    try:
        result = await exchange_api_call()
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise
"""

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import redis

logger = logging.getLogger(__name__)

# Redis client singleton
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None


def get_redis_client():
    """Get Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL)
    return _redis_client


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when circuit is open and requests are blocked."""

    def __init__(self, service_name: str, time_remaining: float = 0):
        self.service_name = service_name
        self.time_remaining = time_remaining
        super().__init__(
            f"Circuit breaker OPEN for {service_name}. "
            f"Service unavailable. Retry in {time_remaining:.1f}s"
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    # Number of failures before opening circuit
    failure_threshold: int = 5

    # Time window for counting failures (seconds)
    failure_window: int = 60

    # How long to stay open before testing (seconds)
    reset_timeout: int = 30

    # Number of successes in HALF_OPEN to close circuit
    success_threshold: int = 2

    # TTL for Redis keys (seconds)
    key_ttl: int = 300


class CircuitBreaker:
    """
    Distributed Circuit Breaker using Redis.

    Thread-safe and works across multiple processes/workers.
    """

    # Default configs per service type
    DEFAULT_CONFIGS = {
        "binance": CircuitBreakerConfig(failure_threshold=5, reset_timeout=30),
        "bybit": CircuitBreakerConfig(failure_threshold=5, reset_timeout=30),
        "okx": CircuitBreakerConfig(failure_threshold=5, reset_timeout=30),
        "default": CircuitBreakerConfig(failure_threshold=5, reset_timeout=30),
    }

    def __init__(self, service_name: str, config: CircuitBreakerConfig = None):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of the service (e.g., "binance", "bybit")
            config: Optional custom configuration
        """
        self.service_name = service_name.lower()
        self.config = config or self.DEFAULT_CONFIGS.get(
            self.service_name,
            self.DEFAULT_CONFIGS["default"]
        )
        self.redis = get_redis_client()

        # Redis keys
        self._state_key = f"cb:{self.service_name}:state"
        self._failures_key = f"cb:{self.service_name}:failures"
        self._last_failure_key = f"cb:{self.service_name}:last_failure"
        self._successes_key = f"cb:{self.service_name}:successes"
        self._opened_at_key = f"cb:{self.service_name}:opened_at"

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        state = self.redis.get(self._state_key)
        if state:
            return CircuitState(state.decode())
        return CircuitState.CLOSED

    def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns True if circuit is CLOSED or HALF_OPEN.
        Returns False if circuit is OPEN.
        """
        state = self.get_state()

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if reset timeout has passed
            opened_at = self.redis.get(self._opened_at_key)
            if opened_at:
                elapsed = time.time() - float(opened_at)
                if elapsed >= self.config.reset_timeout:
                    # Transition to HALF_OPEN
                    self._set_state(CircuitState.HALF_OPEN)
                    logger.info(f"Circuit {self.service_name}: OPEN -> HALF_OPEN (testing recovery)")
                    return True
            return False

        # HALF_OPEN - allow requests for testing
        return True

    def get_time_remaining(self) -> float:
        """Get time remaining until circuit might close (when in OPEN state)."""
        if self.get_state() != CircuitState.OPEN:
            return 0

        opened_at = self.redis.get(self._opened_at_key)
        if opened_at:
            elapsed = time.time() - float(opened_at)
            remaining = self.config.reset_timeout - elapsed
            return max(0, remaining)
        return 0

    def record_success(self):
        """Record a successful request."""
        state = self.get_state()

        if state == CircuitState.HALF_OPEN:
            # Increment success counter
            successes = self.redis.incr(self._successes_key)
            self.redis.expire(self._successes_key, self.config.key_ttl)

            if successes >= self.config.success_threshold:
                # Close the circuit
                self._close_circuit()
                logger.info(
                    f"Circuit {self.service_name}: HALF_OPEN -> CLOSED "
                    f"(recovered after {successes} successes)"
                )

        elif state == CircuitState.CLOSED:
            # Reset failure count on success (sliding window reset)
            self.redis.delete(self._failures_key)

    def record_failure(self, exception: Exception = None):
        """Record a failed request."""
        state = self.get_state()

        # Log the failure
        if exception:
            logger.warning(
                f"Circuit {self.service_name}: Failure recorded - {type(exception).__name__}: {exception}"
            )

        if state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN reopens the circuit
            self._open_circuit()
            logger.warning(
                f"Circuit {self.service_name}: HALF_OPEN -> OPEN "
                f"(failure during recovery test)"
            )

        elif state == CircuitState.CLOSED:
            # Increment failure counter with sliding window
            pipe = self.redis.pipeline()
            pipe.incr(self._failures_key)
            pipe.expire(self._failures_key, self.config.failure_window)
            pipe.set(self._last_failure_key, time.time(), ex=self.config.key_ttl)
            results = pipe.execute()

            failures = results[0]

            if failures >= self.config.failure_threshold:
                # Open the circuit
                self._open_circuit()
                logger.error(
                    f"Circuit {self.service_name}: CLOSED -> OPEN "
                    f"({failures} failures in {self.config.failure_window}s window)"
                )

    def _set_state(self, state: CircuitState):
        """Set circuit state in Redis."""
        self.redis.set(self._state_key, state.value, ex=self.config.key_ttl)

    def _open_circuit(self):
        """Open the circuit (block all requests)."""
        pipe = self.redis.pipeline()
        pipe.set(self._state_key, CircuitState.OPEN.value, ex=self.config.key_ttl)
        pipe.set(self._opened_at_key, time.time(), ex=self.config.key_ttl)
        pipe.delete(self._successes_key)  # Reset success counter
        pipe.execute()

    def _close_circuit(self):
        """Close the circuit (allow all requests)."""
        pipe = self.redis.pipeline()
        pipe.set(self._state_key, CircuitState.CLOSED.value, ex=self.config.key_ttl)
        pipe.delete(self._failures_key)
        pipe.delete(self._successes_key)
        pipe.delete(self._opened_at_key)
        pipe.execute()

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        self._close_circuit()
        logger.info(f"Circuit {self.service_name}: Manually reset to CLOSED")

    def get_stats(self) -> dict:
        """Get current circuit breaker statistics."""
        return {
            "service": self.service_name,
            "state": self.get_state().value,
            "failures": int(self.redis.get(self._failures_key) or 0),
            "successes": int(self.redis.get(self._successes_key) or 0),
            "time_remaining": self.get_time_remaining(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "failure_window": self.config.failure_window,
                "reset_timeout": self.config.reset_timeout,
                "success_threshold": self.config.success_threshold,
            }
        }


# Singleton instances for each exchange
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a service.

    Args:
        service_name: Name of the service (e.g., "binance", "bybit", "okx")

    Returns:
        CircuitBreaker instance
    """
    service_name = service_name.lower()
    if service_name not in _breakers:
        _breakers[service_name] = CircuitBreaker(service_name)
    return _breakers[service_name]


def check_circuit(service_name: str) -> bool:
    """
    Quick check if circuit allows requests.

    Args:
        service_name: Name of the service

    Returns:
        True if requests are allowed, False if blocked

    Raises:
        CircuitOpenError: If circuit is open (optional, based on usage)
    """
    breaker = get_circuit_breaker(service_name)
    return breaker.can_execute()


def with_circuit_breaker(service_name: str):
    """
    Decorator to wrap function with circuit breaker protection.

    Usage:
        @with_circuit_breaker("binance")
        async def call_binance_api():
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            breaker = get_circuit_breaker(service_name)

            if not breaker.can_execute():
                raise CircuitOpenError(
                    service_name,
                    breaker.get_time_remaining()
                )

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(e)
                raise

        return wrapper
    return decorator
