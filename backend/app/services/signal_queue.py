"""
Signal Queue Service
Manages per-user priority queues for signal processing.

Fixes race conditions by:
1. Early balance validation (Redis cache)
2. Priority-based signal ordering
3. Per-user serialized processing
"""

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Optional

import redis

from app.config import MIN_TRADING_BALANCE_USDT
from app.models.signal import WhaleSignal, SignalConfidence
from app.models.whale import Whale

logger = logging.getLogger(__name__)

# Redis key prefixes
QUEUE_KEY_PREFIX = "signal_queue:"
PROCESSING_LOCK_PREFIX = "signal_processing_user:"
BALANCE_CACHE_PREFIX = "user_balance:"

# TTLs
QUEUE_TTL = 300  # 5 minutes - signals expire if not processed
PROCESSING_LOCK_TTL = 60  # 1 minute max processing time
BALANCE_CACHE_TTL = 30  # 30 seconds - matches sync_all_user_balances interval

# Redis client singleton
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_signal_queue_service: Optional["SignalQueueService"] = None


def calculate_signal_priority(signal: WhaleSignal, whale: Whale) -> int:
    """
    Calculate combined priority score (0-100).
    Higher score = higher priority = processed first.

    Factors:
    1. Confidence (0-40 points) - from SignalConfidence enum
    2. Whale ROI / score (0-35 points) - from whale.score (historical performance)
    3. Position Size (0-25 points) - from signal.amount_usd
    """
    # Factor 1: Confidence (0-40 points)
    confidence_weights = {
        SignalConfidence.VERY_HIGH: 40,
        SignalConfidence.HIGH: 30,
        SignalConfidence.MEDIUM: 20,
        SignalConfidence.LOW: 10,
    }
    confidence_score = confidence_weights.get(signal.confidence, 20)

    # Factor 2: Whale ROI / Historical Performance (0-35 points)
    # whale.score is 0-100 based on win_rate and profit
    whale_score_value = float(whale.score or 50)
    whale_roi_score = min(35, int(whale_score_value * 0.35))

    # Factor 3: Position Size / Amount USD (0-25 points)
    # Larger positions from whales = higher conviction = higher priority
    amount_usd = float(signal.amount_usd or 0)
    if amount_usd >= 100_000:
        size_score = 25
    elif amount_usd >= 50_000:
        size_score = 15 + int((amount_usd - 50_000) / 5_000)  # 15-25
    elif amount_usd >= 10_000:
        size_score = 5 + int((amount_usd - 10_000) / 4_000)   # 5-15
    else:
        size_score = max(0, int(amount_usd / 2_000))  # 0-5

    total = confidence_score + whale_roi_score + size_score
    return min(100, max(0, total))


@dataclass
class QueuedSignal:
    """Signal queued for execution with priority."""
    signal_id: int
    whale_id: int
    user_id: int
    priority: int  # 0-100
    symbol: str
    action: str  # BUY/SELL
    amount_usd: float
    confidence: str  # LOW/MEDIUM/HIGH/VERY_HIGH
    queued_at: float  # Unix timestamp

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "QueuedSignal":
        return cls(**json.loads(data))


class SignalQueueService:
    """
    Per-user Redis priority queue for signal processing.

    Features:
    - Priority scoring based on confidence, whale ROI, position size
    - Early balance validation to reduce system load
    - Per-user serialized processing to prevent race conditions
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def check_balance_cached(self, user_id: int) -> tuple[bool, Optional[Decimal]]:
        """
        Check cached balance for early filtering.

        Returns:
            (has_sufficient_balance, cached_balance_or_none)
        """
        cache_key = f"{BALANCE_CACHE_PREFIX}{user_id}"
        cached = self.redis.get(cache_key)

        if cached:
            balance = Decimal(str(cached))
            min_balance = Decimal(str(MIN_TRADING_BALANCE_USDT))
            return balance >= min_balance, balance

        # No cache = assume eligible (will check in DB later)
        return True, None

    def enqueue_signal(
        self,
        signal: WhaleSignal,
        whale: Whale,
        user_id: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Enqueue signal for a user with priority scoring.

        Returns:
            (success, reason_if_skipped)
        """
        # Early balance validation
        has_balance, cached_balance = self.check_balance_cached(user_id)
        if not has_balance:
            logger.debug(
                f"Early skip: User {user_id} insufficient balance "
                f"(cached: ${cached_balance})"
            )
            return False, "insufficient_balance_cached"

        # Calculate priority
        priority = calculate_signal_priority(signal, whale)

        # Create queue entry
        queued = QueuedSignal(
            signal_id=signal.id,
            whale_id=whale.id,
            user_id=user_id,
            priority=priority,
            symbol=signal.cex_symbol or "",
            action=signal.action.value,
            amount_usd=float(signal.amount_usd or 0),
            confidence=signal.confidence.value,
            queued_at=time.time(),
        )

        # Enqueue with negative priority (ZPOPMIN gets lowest = highest priority)
        queue_key = f"{QUEUE_KEY_PREFIX}{user_id}"
        self.redis.zadd(queue_key, {queued.to_json(): -priority})
        self.redis.expire(queue_key, QUEUE_TTL)

        logger.info(
            f"Enqueued signal {signal.id} for user {user_id} "
            f"with priority {priority} ({signal.confidence.value}, "
            f"whale_score={whale.score}, ${signal.amount_usd:.0f})"
        )

        return True, None

    def get_queue_depth(self, user_id: int) -> int:
        """Get number of pending signals for user."""
        queue_key = f"{QUEUE_KEY_PREFIX}{user_id}"
        return self.redis.zcard(queue_key) or 0

    def pop_highest_priority(self, user_id: int) -> Optional[QueuedSignal]:
        """Pop and return the highest priority signal from queue."""
        queue_key = f"{QUEUE_KEY_PREFIX}{user_id}"

        # ZPOPMIN gets lowest score (most negative = highest priority)
        items = self.redis.zpopmin(queue_key, count=1)
        if not items:
            return None

        signal_json, score = items[0]
        if isinstance(signal_json, bytes):
            signal_json = signal_json.decode()

        return QueuedSignal.from_json(signal_json)

    def peek_queue(self, user_id: int, count: int = 5) -> list[QueuedSignal]:
        """Peek at top signals in queue without removing them."""
        queue_key = f"{QUEUE_KEY_PREFIX}{user_id}"
        items = self.redis.zrange(queue_key, 0, count - 1, withscores=True)

        result = []
        for signal_json, score in items:
            if isinstance(signal_json, bytes):
                signal_json = signal_json.decode()
            result.append(QueuedSignal.from_json(signal_json))
        return result

    def acquire_processing_lock(self, user_id: int) -> bool:
        """
        Acquire distributed lock for processing user's queue.

        Returns True if lock acquired, False if already held.
        """
        lock_key = f"{PROCESSING_LOCK_PREFIX}{user_id}"
        return bool(self.redis.set(lock_key, "1", nx=True, ex=PROCESSING_LOCK_TTL))

    def release_processing_lock(self, user_id: int):
        """Release processing lock for user."""
        lock_key = f"{PROCESSING_LOCK_PREFIX}{user_id}"
        self.redis.delete(lock_key)

    def extend_processing_lock(self, user_id: int, seconds: int = PROCESSING_LOCK_TTL):
        """Extend processing lock TTL (call during long processing)."""
        lock_key = f"{PROCESSING_LOCK_PREFIX}{user_id}"
        self.redis.expire(lock_key, seconds)

    def update_balance_cache(self, user_id: int, balance: Decimal):
        """Update cached balance for user."""
        cache_key = f"{BALANCE_CACHE_PREFIX}{user_id}"
        self.redis.setex(cache_key, BALANCE_CACHE_TTL, str(balance))

    def get_all_queue_keys(self) -> list[str]:
        """Get all user queue keys (for stale queue processing)."""
        keys = self.redis.keys(f"{QUEUE_KEY_PREFIX}*")
        return [k.decode() if isinstance(k, bytes) else k for k in keys]

    def get_user_id_from_queue_key(self, key: str) -> int:
        """Extract user_id from queue key."""
        return int(key.replace(QUEUE_KEY_PREFIX, ""))


def get_signal_queue() -> SignalQueueService:
    """Get or create SignalQueueService singleton."""
    global _signal_queue_service
    if _signal_queue_service is None:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _signal_queue_service = SignalQueueService(redis_client)
    return _signal_queue_service
