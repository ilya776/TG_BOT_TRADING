"""
Rate Limit Manager

Intelligent rate limit handling for exchange APIs.
Tracks rate limits per exchange and dynamically adjusts request frequency.

Features:
- Per-exchange rate limit tracking
- Exponential backoff with jitter
- Cooldown periods with automatic recovery
- Request budgeting per time window
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import redis

logger = logging.getLogger(__name__)

# Default rate limit settings per exchange (requests per minute)
EXCHANGE_LIMITS = {
    "BINANCE": {"requests_per_minute": 60, "burst": 10},  # Conservative
    "OKX": {"requests_per_minute": 120, "burst": 20},  # More permissive
    "BITGET": {"requests_per_minute": 60, "burst": 10},
}

# Backoff settings
INITIAL_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 300  # 5 minutes max
BACKOFF_MULTIPLIER = 2
JITTER_FACTOR = 0.3  # 30% jitter

# Cooldown after rate limit hit
RATE_LIMIT_COOLDOWN_SECONDS = 60


@dataclass
class ExchangeRateLimitState:
    """State tracking for a single exchange."""

    exchange: str
    requests_this_minute: int = 0
    minute_start: datetime = field(default_factory=datetime.utcnow)
    consecutive_rate_limits: int = 0
    last_rate_limit_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    current_backoff_seconds: float = INITIAL_BACKOFF_SECONDS

    def is_in_cooldown(self) -> bool:
        """Check if exchange is in cooldown period."""
        if self.cooldown_until is None:
            return False
        return datetime.utcnow() < self.cooldown_until

    def reset_minute_counter(self) -> None:
        """Reset the per-minute request counter."""
        now = datetime.utcnow()
        if (now - self.minute_start).total_seconds() >= 60:
            self.requests_this_minute = 0
            self.minute_start = now

    def record_success(self) -> None:
        """Record a successful request."""
        self.reset_minute_counter()
        self.requests_this_minute += 1
        # Gradually reduce backoff on success
        if self.consecutive_rate_limits > 0:
            self.consecutive_rate_limits = max(0, self.consecutive_rate_limits - 1)
            if self.consecutive_rate_limits == 0:
                self.current_backoff_seconds = INITIAL_BACKOFF_SECONDS
                logger.info(f"{self.exchange}: Rate limit recovery complete")

    def record_rate_limit(self) -> float:
        """
        Record a rate limit hit and calculate backoff.

        Returns:
            Recommended wait time in seconds
        """
        self.consecutive_rate_limits += 1
        self.last_rate_limit_at = datetime.utcnow()

        # Calculate exponential backoff with jitter
        backoff = min(
            self.current_backoff_seconds * BACKOFF_MULTIPLIER,
            MAX_BACKOFF_SECONDS
        )
        jitter = random.uniform(-JITTER_FACTOR, JITTER_FACTOR) * backoff
        wait_time = backoff + jitter

        self.current_backoff_seconds = backoff
        self.cooldown_until = datetime.utcnow() + timedelta(seconds=wait_time)

        logger.warning(
            f"{self.exchange}: Rate limited (#{self.consecutive_rate_limits}), "
            f"backing off for {wait_time:.1f}s"
        )

        return wait_time

    def can_make_request(self) -> tuple[bool, str]:
        """
        Check if a request can be made.

        Returns:
            (can_proceed, reason)
        """
        self.reset_minute_counter()

        # Check cooldown
        if self.is_in_cooldown():
            remaining = (self.cooldown_until - datetime.utcnow()).total_seconds()
            return False, f"In cooldown for {remaining:.1f}s more"

        # Check rate limit budget
        limit = EXCHANGE_LIMITS.get(self.exchange, {"requests_per_minute": 60})
        if self.requests_this_minute >= limit["requests_per_minute"]:
            return False, f"Rate limit budget exhausted ({self.requests_this_minute}/{limit['requests_per_minute']})"

        return True, "OK"


class RateLimitManager:
    """
    Manages rate limits across all exchanges.

    Usage:
        manager = RateLimitManager()

        # Before making request
        if await manager.can_proceed("OKX"):
            response = await make_request()
            if response.status == 429:
                await manager.record_rate_limit("OKX")
            else:
                await manager.record_success("OKX")
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.states: dict[str, ExchangeRateLimitState] = {}
        self.redis = redis_client
        self._lock = asyncio.Lock()

    def _get_state(self, exchange: str) -> ExchangeRateLimitState:
        """Get or create state for an exchange."""
        if exchange not in self.states:
            self.states[exchange] = ExchangeRateLimitState(exchange=exchange)
        return self.states[exchange]

    async def can_proceed(self, exchange: str) -> bool:
        """
        Check if a request can be made to the exchange.

        Args:
            exchange: Exchange name (BINANCE, OKX, BITGET)

        Returns:
            True if request can proceed, False if should wait
        """
        async with self._lock:
            state = self._get_state(exchange)
            can_proceed, reason = state.can_make_request()

            if not can_proceed:
                logger.debug(f"{exchange}: Cannot proceed - {reason}")

            return can_proceed

    async def wait_if_needed(self, exchange: str) -> float:
        """
        Wait if exchange is rate limited.

        Returns:
            Seconds waited (0 if no wait needed)
        """
        async with self._lock:
            state = self._get_state(exchange)

            if state.is_in_cooldown():
                wait_time = (state.cooldown_until - datetime.utcnow()).total_seconds()
                if wait_time > 0:
                    logger.debug(f"{exchange}: Waiting {wait_time:.1f}s for cooldown")
                    await asyncio.sleep(wait_time)
                    return wait_time

        return 0

    async def record_success(self, exchange: str) -> None:
        """Record a successful request."""
        async with self._lock:
            state = self._get_state(exchange)
            state.record_success()

    async def record_rate_limit(self, exchange: str) -> float:
        """
        Record a rate limit and get recommended wait time.

        Returns:
            Recommended wait time in seconds
        """
        async with self._lock:
            state = self._get_state(exchange)
            return state.record_rate_limit()

    async def get_status(self) -> dict:
        """Get status of all exchanges."""
        async with self._lock:
            status = {}
            for exchange, state in self.states.items():
                status[exchange] = {
                    "requests_this_minute": state.requests_this_minute,
                    "consecutive_rate_limits": state.consecutive_rate_limits,
                    "in_cooldown": state.is_in_cooldown(),
                    "cooldown_remaining": (
                        (state.cooldown_until - datetime.utcnow()).total_seconds()
                        if state.cooldown_until and state.is_in_cooldown()
                        else 0
                    ),
                    "current_backoff": state.current_backoff_seconds,
                }
            return status

    async def reset(self, exchange: Optional[str] = None) -> None:
        """Reset rate limit state for exchange(s)."""
        async with self._lock:
            if exchange:
                if exchange in self.states:
                    del self.states[exchange]
            else:
                self.states.clear()


# Singleton instance
_rate_limit_manager: Optional[RateLimitManager] = None


def get_rate_limit_manager() -> RateLimitManager:
    """Get singleton RateLimitManager instance."""
    global _rate_limit_manager
    if _rate_limit_manager is None:
        _rate_limit_manager = RateLimitManager()
    return _rate_limit_manager
