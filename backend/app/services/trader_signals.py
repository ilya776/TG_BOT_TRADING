"""
Trader Signal Generation Service
Generates trading signals from exchange leaderboard traders' positions.
Monitors position changes and creates signals when traders open/close positions.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable, Any

import httpx
import redis
from sqlalchemy import select

from app.database import get_db_context
from app.models.signal import SignalAction, SignalConfidence, SignalStatus, WhaleSignal
from app.models.whale import Whale, UserWhaleFollow
from app.models.user import User
from app.services.sharing_validator import get_sharing_validator, SharingValidator

logger = logging.getLogger(__name__)

# Retry configuration for network requests
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds between retries (exponential backoff)

# ============================================================================
# BITGET CIRCUIT BREAKER - Prevents cascading failures when API is down
# ============================================================================
# When Bitget API fails repeatedly (timeouts, 403s), the circuit opens and
# all requests fail fast for a cooldown period. This prevents:
# 1. Wasting time on requests that will fail
# 2. Overloading the API with retries (making rate limits worse)
# 3. Blocking worker threads with timeout waits

class BitgetCircuitBreaker:
    """Simple circuit breaker for Bitget API calls."""

    FAILURE_THRESHOLD = 5  # Open circuit after 5 consecutive failures
    COOLDOWN_SECONDS = 120  # Keep circuit open for 2 minutes

    def __init__(self):
        self._failures = 0
        self._circuit_opened_at: Optional[float] = None
        self._last_success_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self._circuit_opened_at is None:
            return False

        elapsed = time.time() - self._circuit_opened_at
        if elapsed >= self.COOLDOWN_SECONDS:
            # Cooldown expired - allow one request through (half-open state)
            return False
        return True

    @property
    def time_until_retry(self) -> float:
        """Seconds until circuit allows requests again."""
        if self._circuit_opened_at is None:
            return 0
        elapsed = time.time() - self._circuit_opened_at
        return max(0, self.COOLDOWN_SECONDS - elapsed)

    def record_success(self):
        """Record a successful API call."""
        self._failures = 0
        self._circuit_opened_at = None
        self._last_success_at = time.time()

    def record_failure(self):
        """Record a failed API call."""
        self._failures += 1
        if self._failures >= self.FAILURE_THRESHOLD:
            if self._circuit_opened_at is None:
                self._circuit_opened_at = time.time()
                logger.warning(
                    f"Bitget circuit breaker OPENED after {self._failures} failures. "
                    f"Blocking requests for {self.COOLDOWN_SECONDS}s"
                )

    def reset(self):
        """Reset circuit breaker (for testing)."""
        self._failures = 0
        self._circuit_opened_at = None


# Global Bitget circuit breaker instance
_bitget_circuit_breaker = BitgetCircuitBreaker()

def get_bitget_circuit_breaker() -> BitgetCircuitBreaker:
    """Get the global Bitget circuit breaker."""
    return _bitget_circuit_breaker


# FlareSolverr URL for Cloudflare bypass (used by Bitget fallback)
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1")


RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.TimeoutException,
    httpx.NetworkError,
)

# Low-latency configuration
MAX_POSITION_AGE_FOR_SIGNAL = 60  # Only generate signals for positions opened within 60 seconds
ENABLE_IMMEDIATE_EXECUTION = True  # Bypass queue for followed whales with auto-copy

# Redis client for persistent position cache
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client: Optional[redis.Redis] = None

# Redis key for eligible whales cache (whales with auto-copy followers)
ELIGIBLE_WHALES_CACHE_KEY = "whale_trading:eligible_whales"
ELIGIBLE_WHALES_CACHE_TTL = 30  # Cache TTL in seconds (rebuild every 30s)


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for position caching."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def check_whale_has_eligible_users_cached(whale_id: int) -> bool:
    """
    Check Redis cache if whale has eligible auto-copy users.
    Returns True if whale_id is in the eligible set, False otherwise.
    Falls back to True if cache doesn't exist (will trigger DB check).
    """
    try:
        r = get_redis_client()
        # Check if the set exists and contains this whale
        if r.exists(ELIGIBLE_WHALES_CACHE_KEY):
            return r.sismember(ELIGIBLE_WHALES_CACHE_KEY, str(whale_id))
        # Cache doesn't exist yet - return True to trigger DB fallback
        return True
    except Exception as e:
        logger.warning(f"Redis cache check failed: {e}")
        return True  # Fallback to DB check on error


async def rebuild_eligible_whales_cache() -> int:
    """
    Rebuild the Redis cache of whale IDs that have eligible auto-copy users.
    Called periodically by Celery beat (every 10-30 seconds).

    Returns:
        Number of eligible whales cached
    """
    from sqlalchemy import or_, func
    from app.config import MIN_TRADING_BALANCE_USDT
    from app.models.user import UserSettings

    try:
        async with get_db_context() as db:
            # Get all whale IDs with at least one eligible auto-copy user
            result = await db.execute(
                select(UserWhaleFollow.whale_id)
                .join(User, UserWhaleFollow.user_id == User.id)
                .outerjoin(UserSettings, User.id == UserSettings.user_id)
                .where(
                    User.is_active == True,
                    User.available_balance >= MIN_TRADING_BALANCE_USDT,
                    or_(
                        UserWhaleFollow.auto_copy_enabled == True,
                        UserSettings.auto_copy_enabled == True,
                    ),
                )
                .distinct()
            )
            eligible_whale_ids = [str(row[0]) for row in result.all()]

            # Update Redis cache
            r = get_redis_client()
            pipe = r.pipeline()
            pipe.delete(ELIGIBLE_WHALES_CACHE_KEY)
            if eligible_whale_ids:
                pipe.sadd(ELIGIBLE_WHALES_CACHE_KEY, *eligible_whale_ids)
            pipe.expire(ELIGIBLE_WHALES_CACHE_KEY, ELIGIBLE_WHALES_CACHE_TTL)
            pipe.execute()

            logger.info(f"Rebuilt eligible whales cache: {len(eligible_whale_ids)} whales")
            return len(eligible_whale_ids)

    except Exception as e:
        logger.error(f"Failed to rebuild eligible whales cache: {e}")
        return 0


async def retry_on_network_error(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    **kwargs: Any
) -> Any:
    """
    Retry a function on network errors with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"Network error on attempt {attempt + 1}/{max_retries} for {func.__name__}: "
                    f"{type(e).__name__}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {max_retries} attempts failed for {func.__name__}: "
                    f"{type(e).__name__}: {e}"
                )

    raise last_exception


def detect_futures_type(symbol: str, exchange: str) -> str:
    """
    Detect COIN-M vs USD-M from symbol format.

    Symbol patterns:
    - Binance COIN-M: BTCUSD_PERP, ETHUSD_PERP, BTCUSD_201225 (quarterly)
    - Binance USD-M: BTCUSDT, ETHUSDT
    - OKX: Uses unified account, symbols like BTC-USDT-SWAP
    - Bitget: Uses umcbl for USD-M (BTCUSDT_UMCBL)

    Returns:
        "COIN-M" or "USD-M"
    """
    symbol = symbol.upper()

    if exchange.lower() == "binance":
        # COIN-M symbols contain "_PERP" or "_" with date (quarterly)
        # or end with "USD" without "T" (like BTCUSD)
        if "_" in symbol:
            return "COIN-M"
        if symbol.endswith("USD") and not symbol.endswith("USDT") and not symbol.endswith("BUSD"):
            return "COIN-M"
        return "USD-M"

    elif exchange.lower() == "okx":
        # OKX uses unified account - check for SWAP vs other types
        # BTC-USD-SWAP is COIN-M equivalent
        # BTC-USDT-SWAP is USD-M
        if "-USD-" in symbol and "-USDT-" not in symbol:
            return "COIN-M"
        return "USD-M"

    elif exchange.lower() == "bitget":
        # Bitget uses productType in API
        # DMCBL = COIN-M, UMCBL = USD-M
        if "DMCBL" in symbol or symbol.endswith("USD"):
            return "COIN-M"
        return "USD-M"

    # Default to USD-M
    return "USD-M"


@dataclass
class TraderPosition:
    """Represents a trader's open position."""
    symbol: str
    side: str  # LONG or SHORT
    entry_price: Decimal
    mark_price: Decimal
    size: Decimal
    pnl: Decimal
    roe: Decimal  # Return on equity (%)
    leverage: int
    update_time: datetime
    futures_type: str = "USD-M"  # "USD-M" or "COIN-M"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for Redis storage."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": str(self.entry_price),
            "mark_price": str(self.mark_price),
            "size": str(self.size),
            "pnl": str(self.pnl),
            "roe": str(self.roe),
            "leverage": self.leverage,
            "update_time": self.update_time.isoformat(),
            "futures_type": self.futures_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TraderPosition":
        """Create from JSON dict."""
        return cls(
            symbol=data["symbol"],
            side=data["side"],
            entry_price=Decimal(data["entry_price"]),
            mark_price=Decimal(data["mark_price"]),
            size=Decimal(data["size"]),
            pnl=Decimal(data["pnl"]),
            roe=Decimal(data["roe"]),
            leverage=int(data["leverage"]),
            update_time=datetime.fromisoformat(data["update_time"]),
            futures_type=data.get("futures_type", "USD-M"),
        )


class TraderSignalService:
    """
    Monitors top traders on Binance/Bitget/OKX and generates signals
    when they open or close positions.
    """

    CACHE_PREFIX = "trader_positions:"
    CACHE_TTL = 300  # 5 minutes - positions older than this are considered stale

    # Required fields for position parsing (exchange-specific)
    REQUIRED_FIELDS = {
        "binance": ["symbol", "amount", "entryPrice"],
        "okx": ["instId", "posSide", "subPos"],
        "bitget": ["symbol", "holdSide", "total"],
    }

    def _validate_position_data(self, item: dict, exchange: str) -> tuple[bool, list[str]]:
        """Validate that required fields are present in position data.

        Returns:
            Tuple of (is_valid, list of missing fields)
        """
        required = self.REQUIRED_FIELDS.get(exchange, [])
        missing = []
        for field in required:
            value = item.get(field)
            if value is None or (isinstance(value, str) and value == ""):
                missing.append(field)
        return len(missing) == 0, missing

    def __init__(self):
        # Configure httpx with higher connection limits for parallel fetching
        # Default limits are too low for batch position fetching (50+ whales)
        # Increased timeouts to reduce ReadTimeout errors during high load
        limits = httpx.Limits(
            max_keepalive_connections=100,  # Keep more connections alive
            max_connections=200,  # Allow more concurrent connections
            keepalive_expiry=60.0,  # Keep connections alive for 60s (increased from 30s)
        )
        timeout = httpx.Timeout(
            connect=15.0,  # Connection timeout (increased from 10s)
            read=45.0,  # Read timeout (increased from 30s to handle slow responses)
            write=15.0,  # Write timeout (increased from 10s)
            pool=45.0,  # Pool wait timeout (increased from 30s)
        )
        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )
        self._redis = get_redis_client()

    def _get_cached_positions(self, cache_key: str) -> list[TraderPosition]:
        """Get cached positions from Redis."""
        try:
            data = self._redis.get(f"{self.CACHE_PREFIX}{cache_key}")
            if data:
                positions_data = json.loads(data)
                return [TraderPosition.from_dict(p) for p in positions_data]
        except Exception as e:
            logger.warning(f"Error reading position cache: {e}")
        return []

    def _set_cached_positions(self, cache_key: str, positions: list[TraderPosition]):
        """Store positions in Redis with TTL."""
        try:
            data = json.dumps([p.to_dict() for p in positions])
            self._redis.setex(f"{self.CACHE_PREFIX}{cache_key}", self.CACHE_TTL, data)
        except Exception as e:
            logger.warning(f"Error writing position cache: {e}")

    def _is_position_fresh(self, position: TraderPosition, max_age_seconds: int = MAX_POSITION_AGE_FOR_SIGNAL) -> bool:
        """
        Check if position was opened recently based on update_time.
        Used during warm-up to avoid copying stale positions after restart.

        IMPORTANT: If no timestamp available, consider STALE to avoid
        copying old positions that the API didn't provide open time for.
        """
        if not position.update_time:
            logger.debug(f"Position {position.symbol} has no timestamp - treating as STALE")
            return False  # No timestamp = assume STALE (safer)

        now = datetime.utcnow()
        age = (now - position.update_time).total_seconds()

        # Sanity check: if age is negative (future timestamp), treat as fresh but log warning
        if age < 0:
            logger.warning(f"Position {position.symbol} has future timestamp: {position.update_time} > {now}")
            return True

        is_fresh = age <= max_age_seconds
        if is_fresh:
            logger.info(f"Position {position.symbol} is FRESH: {age:.0f}s old (max: {max_age_seconds}s)")
        else:
            logger.debug(f"Position {position.symbol} is stale: {age:.0f}s old (max: {max_age_seconds}s)")
        return is_fresh

    async def _trigger_immediate_copy(self, db, whale: Whale, signal: WhaleSignal):
        """
        Queue signal for copy trade execution with priority scoring.

        NEW FLOW (fixes race conditions):
        1. Get eligible users (from cache)
        2. Early balance filter (Redis cache)
        3. Calculate priority and enqueue
        4. Trigger per-user queue processor

        Benefits:
        - Early balance validation reduces wasted work
        - Priority scoring ensures best signals processed first
        - Per-user serialization prevents race conditions
        """
        if not ENABLE_IMMEDIATE_EXECUTION:
            return

        try:
            import time
            start_time = time.time()

            from sqlalchemy import or_
            from app.services.signal_queue import get_signal_queue
            from app.config import MIN_TRADING_BALANCE_USDT
            from app.models.user import UserSettings

            # FAST PATH: Check Redis cache first (1-5ms vs 50-100ms DB query)
            has_eligible_users = check_whale_has_eligible_users_cached(whale.id)

            if not has_eligible_users:
                # Cache says no eligible users - skip without DB query
                logger.debug(f"FAST SKIP: Whale {whale.id} not in eligible cache")
                return

            # Get eligible users with auto-copy enabled
            result = await db.execute(
                select(UserWhaleFollow.user_id, User.subscription_tier)
                .join(User, UserWhaleFollow.user_id == User.id)
                .outerjoin(UserSettings, User.id == UserSettings.user_id)
                .where(
                    UserWhaleFollow.whale_id == whale.id,
                    User.is_active == True,
                    User.is_banned == False,
                    User.available_balance >= MIN_TRADING_BALANCE_USDT,
                    or_(
                        UserWhaleFollow.auto_copy_enabled == True,
                        UserSettings.auto_copy_enabled == True,
                    ),
                )
            )
            eligible_users = list(result.all())

            if not eligible_users:
                logger.debug(f"No eligible users for whale {whale.id}")
                return

            # Update signal status
            signal.status = SignalStatus.PROCESSING
            await db.commit()

            # Get queue service
            queue_service = get_signal_queue()

            # Enqueue for each eligible user with early balance filtering
            enqueued_count = 0
            filtered_count = 0

            for user_id, user_tier in eligible_users:
                # Early balance check + enqueue with priority
                success, reason = queue_service.enqueue_signal(
                    signal=signal,
                    whale=whale,
                    user_id=user_id,
                )

                if success:
                    enqueued_count += 1
                    # Trigger queue processing for this user (async via Celery)
                    from app.workers.tasks.trade_tasks import process_user_signal_queue
                    process_user_signal_queue.delay(user_id)
                else:
                    filtered_count += 1

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"QUEUE: Signal {signal.id} ({whale.name} {signal.cex_symbol}) - "
                f"enqueued={enqueued_count}, filtered={filtered_count}, "
                f"time={elapsed_ms:.0f}ms"
            )

        except Exception as e:
            # Don't fail signal creation if queue fails
            logger.error(f"Error in signal queue: {e}", exc_info=True)

    async def _trigger_immediate_close(self, db, whale: Whale, signal: WhaleSignal):
        """
        Trigger immediate position close for users who copied this whale's position.
        Called when whale closes a position for minimal close latency.
        """
        try:
            from app.workers.tasks.trade_tasks import close_position
            from app.models.trade import Position, PositionStatus
            from app.models.user import UserSettings

            # Find all user positions matching this whale's closed position
            positions_result = await db.execute(
                select(Position)
                .where(
                    Position.whale_id == whale.id,
                    Position.symbol == signal.cex_symbol,
                    Position.status == PositionStatus.OPEN,
                )
            )
            positions = positions_result.scalars().all()

            if not positions:
                logger.debug(f"No user positions to close for whale {whale.name} {signal.cex_symbol}")
                return

            closed_count = 0
            for position in positions:
                # Check if user has auto_close_on_whale_exit enabled
                settings_result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == position.user_id)
                )
                settings = settings_result.scalar_one_or_none()

                # Default to True if no settings or setting not explicitly disabled
                should_auto_close = True
                if settings and hasattr(settings, 'auto_close_on_whale_exit'):
                    should_auto_close = settings.auto_close_on_whale_exit

                if should_auto_close:
                    # Queue close with highest priority
                    # CRITICAL: Wrap in asyncio.to_thread() because apply_async() is synchronous
                    import asyncio
                    task_result = await asyncio.to_thread(
                        close_position.apply_async,
                        args=[position.user_id, position.id, "whale_exit"],
                        priority=0,  # Highest priority
                        countdown=0,  # No delay
                    )
                    closed_count += 1
                    logger.info(
                        f"FAST CLOSE: Position {position.id} queued for user {position.user_id} "
                        f"(whale {whale.name} closed {signal.cex_symbol}), task_id={task_result.id}"
                    )

            if closed_count > 0:
                logger.info(
                    f"FAST PATH: Queued {closed_count} position closes for whale exit "
                    f"({whale.name} {signal.cex_symbol})"
                )

        except Exception as e:
            # Don't fail signal creation if immediate close fails
            logger.error(f"Error triggering immediate close: {e}")

    async def close(self):
        await self.client.aclose()

    async def fetch_binance_trader_positions(self, encrypted_uid: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Binance trader.
        Fetches BOTH USD-M and COIN-M perpetual positions.
        """
        positions = []

        # Fetch both USD-M and COIN-M positions
        trade_types = [
            ("PERPETUAL", "USD-M"),      # USD-M perpetuals (BTCUSDT, etc.)
            ("DELIVERY", "COIN-M"),       # COIN-M perpetuals (BTCUSD_PERP, etc.)
        ]

        for trade_type, futures_type in trade_types:
            try:
                url = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getOtherPosition"

                payload = {
                    "encryptedUid": encrypted_uid,
                    "tradeType": trade_type
                }

                response = await self.client.post(url, json=payload)

                if response.status_code == 429:
                    logger.warning(f"Binance {futures_type} positions API rate limited (429)")
                    await asyncio.sleep(5)
                    continue

                if response.status_code != 200:
                    continue

                try:
                    data = response.json()
                except Exception:
                    continue

                if not data.get("success"):
                    continue

                # Handle None values - some traders have position sharing disabled
                data_obj = data.get("data") or {}
                position_list = data_obj.get("otherPositionRetList")
                if position_list is None:
                    continue

                for item in position_list:
                    try:
                        # Validate required fields
                        is_valid, missing = self._validate_position_data(item, "binance")
                        if not is_valid:
                            logger.warning(f"Binance position missing required fields: {missing}")
                            continue

                        symbol = item.get("symbol", "")

                        # Auto-detect futures type from symbol as fallback
                        detected_type = detect_futures_type(symbol, "binance")

                        position = TraderPosition(
                            symbol=symbol,
                            side="LONG" if item.get("amount", 0) > 0 else "SHORT",
                            entry_price=Decimal(str(item.get("entryPrice", 0))),
                            mark_price=Decimal(str(item.get("markPrice", 0))),
                            size=abs(Decimal(str(item.get("amount", 0)))),
                            pnl=Decimal(str(item.get("pnl", 0))),
                            roe=Decimal(str(item.get("roe", 0))) * 100,
                            leverage=int(item.get("leverage", 1)),
                            update_time=datetime.fromtimestamp(item.get("updateTimeStamp", 0) / 1000) if item.get("updateTimeStamp") else datetime.utcnow(),
                            futures_type=detected_type,  # Set futures type
                        )
                        positions.append(position)
                    except Exception as e:
                        logger.warning(f"Error parsing Binance position: {e}")

                # Small delay between USD-M and COIN-M requests
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching Binance {futures_type} positions: {e}")

        if positions:
            usdm_count = sum(1 for p in positions if p.futures_type == "USD-M")
            coinm_count = sum(1 for p in positions if p.futures_type == "COIN-M")
            logger.info(f"Fetched {len(positions)} positions for Binance trader {encrypted_uid[:8]}... (USD-M: {usdm_count}, COIN-M: {coinm_count})")

        return positions

    async def fetch_okx_trader_positions(self, unique_code: str) -> list[TraderPosition]:
        """
        Fetch current positions for an OKX copy trading leader.
        Uses retry logic for network resilience.
        """
        positions = []

        try:
            # OKX Copy Trading public positions API - working endpoint
            url = "https://www.okx.com/api/v5/copytrading/public-current-subpositions"

            params = {
                "uniqueCode": unique_code
            }

            # Wrap HTTP call with retry logic for network errors
            response = await retry_on_network_error(
                self.client.get,
                url,
                params=params
            )

            if response.status_code != 200:
                logger.debug(f"OKX positions API returned {response.status_code}")
                return positions

            data = response.json()
            position_list = data.get("data", [])

            # Safe Decimal conversion with fallback to 0
            def safe_decimal(value, default="0"):
                try:
                    if value is None or value == "":
                        return Decimal(default)
                    return Decimal(str(value))
                except Exception:
                    return Decimal(default)

            # Safe int conversion for leverage
            def safe_int(value, default=1):
                try:
                    if value is None or value == "":
                        return default
                    return int(float(str(value)))
                except Exception:
                    return default

            for item in position_list:
                try:
                    # Validate required fields
                    is_valid, missing = self._validate_position_data(item, "okx")
                    if not is_valid:
                        logger.warning(f"OKX position missing required fields: {missing}")
                        continue

                    # OKX uses 'posSide' (long/short)
                    pos_side = item.get("posSide", "").lower()
                    side = "LONG" if pos_side == "long" else "SHORT"

                    # Convert instId from "BTC-USDT-SWAP" to "BTCUSDT"
                    inst_id = item.get("instId", "")
                    symbol = inst_id.replace("-SWAP", "").replace("-", "")

                    # Skip if no symbol
                    if not symbol:
                        continue

                    # Detect futures type from original instId
                    futures_type = detect_futures_type(inst_id, "okx")

                    # Get position open time from OKX API
                    # openTime = when position was opened (primary source)
                    # cTime = creation time, uTime = update time (fallbacks)
                    position_time = None  # Will be None if API doesn't provide timestamp
                    for time_field in ["openTime", "cTime", "uTime"]:
                        if item.get(time_field):
                            try:
                                ts = int(item[time_field])
                                # Handle milliseconds (>1e12) vs seconds
                                if ts > 1e12:
                                    ts = ts / 1000
                                position_time = datetime.fromtimestamp(ts)
                                break
                            except (ValueError, TypeError):
                                pass

                    position = TraderPosition(
                        symbol=symbol,
                        side=side,
                        entry_price=safe_decimal(item.get("openAvgPx")),
                        mark_price=safe_decimal(item.get("markPx")),
                        size=abs(safe_decimal(item.get("subPos"))),
                        pnl=safe_decimal(item.get("upl")),
                        roe=safe_decimal(item.get("uplRatio")) * 100,
                        leverage=safe_int(item.get("lever")),
                        update_time=position_time,
                        futures_type=futures_type,
                    )
                    positions.append(position)
                except Exception as e:
                    logger.debug(f"Skipping OKX position due to parse error: {item.get('instId', 'unknown')} - {e}")

            if positions:
                logger.info(f"Fetched {len(positions)} positions for OKX trader {unique_code[:8]}...")

        except Exception as e:
            logger.error(
                f"Error fetching OKX trader positions for {unique_code[:8]}...: "
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            )

        return positions

    async def fetch_bitget_trader_positions(self, trader_uid: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Bitget copy trading master.
        Bitget copy traders ALWAYS share positions publicly.

        Uses circuit breaker + fallback strategy:
        1. Check circuit breaker - if open, fail fast
        2. Try direct API with retry logic
        3. If fails, try FlareSolverr fallback
        4. Record success/failure for circuit breaker
        """
        positions = []
        circuit_breaker = get_bitget_circuit_breaker()

        # Fast fail if circuit is open
        if circuit_breaker.is_open:
            logger.debug(
                f"Bitget circuit OPEN - skipping {trader_uid[:8]}... "
                f"(retry in {circuit_breaker.time_until_retry:.0f}s)"
            )
            return positions

        try:
            # Try direct API first
            positions = await self._fetch_bitget_positions_direct(trader_uid)

            if positions:
                circuit_breaker.record_success()
                return positions

            # Direct API returned empty - not a failure, could be no positions
            # Only record failure on actual errors/timeouts
            return positions

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            # Network error - try FlareSolverr fallback
            logger.warning(
                f"Bitget direct API failed for {trader_uid[:8]}...: {type(e).__name__}. "
                f"Trying FlareSolverr fallback..."
            )

            try:
                positions = await self._fetch_bitget_positions_flaresolverr(trader_uid)
                if positions:
                    circuit_breaker.record_success()
                    return positions
            except Exception as fallback_error:
                logger.debug(f"FlareSolverr fallback also failed: {fallback_error}")

            # Both methods failed - record failure
            circuit_breaker.record_failure()
            return positions

        except Exception as e:
            logger.error(f"Unexpected error fetching Bitget positions: {e}")
            circuit_breaker.record_failure()
            return positions

    async def _fetch_bitget_positions_direct(self, trader_uid: str) -> list[TraderPosition]:
        """Fetch Bitget positions via direct API call."""
        positions = []

        # Use trace API for positions
        url = "https://api.bitget.com/api/mix/v1/trace/currentTrack"

        params = {
            "traderUid": trader_uid,
            "pageNo": "1",
            "pageSize": "50"
        }

        # Use shorter timeout for circuit breaker pattern (fail fast)
        response = await retry_on_network_error(
            self.client.get,
            url,
            params=params,
            max_retries=2,  # Fewer retries for faster failure detection
        )

        if response.status_code != 200:
            logger.debug(f"Bitget positions API returned {response.status_code}")
            return positions

        data = response.json()
        position_list = data.get("data", {}).get("list", [])

        positions = self._parse_bitget_positions(position_list, trader_uid)
        return positions

    async def _fetch_bitget_positions_flaresolverr(self, trader_uid: str) -> list[TraderPosition]:
        """
        Fetch Bitget positions via FlareSolverr (Cloudflare bypass).
        Used as fallback when direct API fails.
        """
        positions = []

        try:
            # FlareSolverr request
            url = "https://api.bitget.com/api/mix/v1/trace/currentTrack"
            params = f"?traderUid={trader_uid}&pageNo=1&pageSize=50"

            payload = {
                "cmd": "request.get",
                "url": url + params,
                "maxTimeout": 30000,
            }

            async with httpx.AsyncClient(timeout=45.0) as flare_client:
                response = await flare_client.post(FLARESOLVERR_URL, json=payload)

                if response.status_code != 200:
                    logger.debug(f"FlareSolverr returned {response.status_code}")
                    return positions

                result = response.json()

                if result.get("status") != "ok":
                    logger.debug(f"FlareSolverr error: {result.get('message')}")
                    return positions

                # Parse the response body
                solution = result.get("solution", {})
                body = solution.get("response", "")

                # Try to parse as JSON
                try:
                    data = json.loads(body)
                    position_list = data.get("data", {}).get("list", [])
                    positions = self._parse_bitget_positions(position_list, trader_uid)

                    if positions:
                        logger.info(
                            f"FlareSolverr SUCCESS: Fetched {len(positions)} positions "
                            f"for Bitget trader {trader_uid[:8]}..."
                        )

                except json.JSONDecodeError:
                    logger.debug(f"FlareSolverr response not JSON: {body[:100]}")

        except Exception as e:
            logger.debug(f"FlareSolverr request failed: {e}")

        return positions

    def _parse_bitget_positions(self, position_list: list, trader_uid: str) -> list[TraderPosition]:
        """Parse Bitget position data into TraderPosition objects."""
        positions = []

        for item in position_list:
            try:
                # Validate required fields
                is_valid, missing = self._validate_position_data(item, "bitget")
                if not is_valid:
                    logger.warning(f"Bitget position missing required fields: {missing}")
                    continue

                # Bitget uses 'holdSide' for position side
                side = item.get("holdSide", "long").upper()
                if side not in ["LONG", "SHORT"]:
                    side = "LONG" if "long" in side.lower() else "SHORT"

                # Bitget achievedProfits - check if it's decimal or percentage format
                roe_raw = Decimal(str(item.get("achievedProfits", 0)))
                if abs(roe_raw) < Decimal("1.0") and roe_raw != 0:
                    roe_value = roe_raw * 100  # Convert decimal to percentage
                else:
                    roe_value = roe_raw  # Already percentage

                symbol = item.get("symbol", "").upper()
                futures_type = detect_futures_type(symbol, "bitget")

                # Get position open time from Bitget API
                position_time = datetime.utcnow()
                for time_field in ["cTime", "ctime", "openTime", "uTime", "utime"]:
                    if item.get(time_field):
                        try:
                            ts = int(item[time_field])
                            if ts > 1e12:
                                ts = ts / 1000
                            position_time = datetime.fromtimestamp(ts)
                            break
                        except (ValueError, TypeError):
                            pass

                position = TraderPosition(
                    symbol=symbol,
                    side=side,
                    entry_price=Decimal(str(item.get("openPriceAvg", item.get("averageOpenPrice", 0)))),
                    mark_price=Decimal(str(item.get("marketPrice", 0))),
                    size=Decimal(str(item.get("total", item.get("holdAmount", 0)))),
                    pnl=Decimal(str(item.get("unrealizedPL", 0))),
                    roe=roe_value,
                    leverage=int(float(item.get("leverage", 1))),
                    update_time=position_time,
                    futures_type=futures_type,
                )
                positions.append(position)
            except Exception as e:
                logger.warning(f"Error parsing Bitget position: {e}")

        if positions:
            logger.info(f"Fetched {len(positions)} positions for Bitget trader {trader_uid[:8]}...")

        return positions

    async def fetch_bybit_trader_positions(self, leader_mark: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Bybit copy trading master.

        NOTE: Bybit uses Akamai bot protection.
        This method uses browser-based fetching when Playwright is available,
        otherwise falls back to direct HTTP (which may be blocked).

        Args:
            leader_mark: The trader's unique identifier (URL-safe base64)

        Returns:
            List of TraderPosition objects
        """
        positions = []

        try:
            from app.services.exchanges.bybit_copy_trading import (
                BybitCopyTradingService,
                PLAYWRIGHT_AVAILABLE,
            )

            service = BybitCopyTradingService()

            try:
                # Use browser-based method if Playwright is available
                if PLAYWRIGHT_AVAILABLE:
                    bybit_positions = await service.fetch_positions_browser(leader_mark)
                else:
                    bybit_positions = await service.fetch_trader_positions(leader_mark)

                for bp in bybit_positions:
                    try:
                        # Convert Bybit side format to our format
                        side = "LONG" if bp.side == "Buy" else "SHORT"

                        # Calculate ROE if mark_price and entry_price available
                        roe = Decimal("0")
                        if bp.entry_price and bp.mark_price and bp.entry_price != 0:
                            price_change = (bp.mark_price - bp.entry_price) / bp.entry_price
                            roe = price_change * bp.leverage * 100
                            if side == "SHORT":
                                roe = -roe

                        position = TraderPosition(
                            symbol=bp.symbol,
                            side=side,
                            entry_price=bp.entry_price,
                            mark_price=bp.mark_price,
                            size=bp.size,
                            pnl=bp.unrealized_pnl,
                            roe=roe,
                            leverage=bp.leverage,
                            update_time=bp.created_time,  # Use created time as position open time
                            futures_type="USD-M",  # Bybit copy trading uses USDT perpetuals
                        )
                        positions.append(position)
                    except Exception as e:
                        logger.warning(f"Error parsing Bybit position: {e}")

                if positions:
                    logger.info(f"Fetched {len(positions)} positions for Bybit trader {leader_mark[:20]}...")

            finally:
                await service.close()

        except ImportError:
            logger.warning("Bybit service not available")
        except Exception as e:
            logger.error(f"Error fetching Bybit trader positions: {e}")

        return positions

    async def fetch_hyperliquid_trader_positions(self, address: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Hyperliquid OnChain whale.

        Hyperliquid is 100% OnChain - positions are ALWAYS public.
        No "sharing disabled" issues EVER!

        Uses clearinghouseState API to get real-time positions.

        Args:
            address: The trader's wallet address (0x...)

        Returns:
            List of TraderPosition objects
        """
        positions = []

        try:
            from app.services.discovery.onchain.hyperliquid import HyperliquidTracker

            tracker = HyperliquidTracker()

            try:
                # Fetch account state with positions
                account = await tracker.get_account_state(address)

                if account and account.positions:
                    for hp in account.positions:
                        try:
                            # Convert Hyperliquid position to our TraderPosition format
                            side = hp.side  # Already "LONG" or "SHORT"

                            # Calculate ROE from unrealized PnL and margin
                            roe = Decimal("0")
                            if hp.margin_used and hp.margin_used != 0:
                                roe = (hp.unrealized_pnl / hp.margin_used) * 100

                            # Hyperliquid uses simple coin names (BTC, ETH, SOL)
                            # Convert to standard format with USDT suffix
                            symbol = f"{hp.coin}USDT"

                            # Get current mark price from position value
                            mark_price = Decimal("0")
                            if hp.position_value and hp.abs_size and hp.abs_size != 0:
                                mark_price = hp.position_value / hp.abs_size

                            position = TraderPosition(
                                symbol=symbol,
                                side=side,
                                entry_price=hp.entry_price,
                                mark_price=mark_price,
                                size=hp.abs_size,
                                pnl=hp.unrealized_pnl,
                                roe=roe,
                                leverage=hp.leverage,
                                update_time=account.timestamp,
                                futures_type="USD-M",  # Hyperliquid uses USDC perpetuals
                            )
                            positions.append(position)
                        except Exception as e:
                            logger.warning(f"Error parsing Hyperliquid position: {e}")

                    if positions:
                        logger.debug(
                            f"Fetched {len(positions)} positions for Hyperliquid whale "
                            f"{address[:10]}... (acc value: ${account.account_value:,.0f})"
                        )

            finally:
                await tracker.close()

        except ImportError as e:
            logger.warning(f"Hyperliquid tracker not available: {e}")
        except Exception as e:
            logger.error(f"Error fetching Hyperliquid trader positions: {e}")

        return positions

    def _generate_tx_hash(self, whale_id: int, symbol: str, action: str, timestamp: datetime) -> str:
        """Generate a unique hash for the signal (since we don't have real tx hashes)."""
        data = f"{whale_id}:{symbol}:{action}:{timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:64]

    def _determine_confidence(self, position: TraderPosition, whale_score: int) -> SignalConfidence:
        """Determine signal confidence based on position and whale score."""
        # High ROE and high whale score = high confidence
        roe_abs = abs(position.roe)

        if whale_score >= 80 and roe_abs >= 10:
            return SignalConfidence.VERY_HIGH
        elif whale_score >= 60 and roe_abs >= 5:
            return SignalConfidence.HIGH
        elif whale_score >= 40:
            return SignalConfidence.MEDIUM
        else:
            return SignalConfidence.LOW

    def _calculate_confidence_score(self, position: TraderPosition, whale_score: int) -> Decimal:
        """Calculate numeric confidence score (0-100)."""
        # Base score from whale score (0-50 points)
        base_score = Decimal(whale_score) * Decimal("0.5")

        # ROE contribution (0-30 points)
        roe_abs = abs(position.roe)
        roe_score = min(Decimal("30"), roe_abs * Decimal("3"))

        # Leverage penalty (high leverage = lower confidence)
        leverage_penalty = min(Decimal("20"), Decimal(position.leverage) * Decimal("1.5"))

        total = base_score + roe_score - leverage_penalty
        return max(Decimal("10"), min(Decimal("100"), total))

    async def check_and_generate_signals(self, max_traders: int = 100) -> int:
        """
        Check traders for position changes and generate signals.

        Features:
        - Excludes SHARING_DISABLED whales (no signals possible)
        - Prioritizes Bitget (always public) and followed traders
        - Uses SharingValidator to detect and mark closed-status traders
        - Orders by priority_score for optimal signal generation

        Returns number of signals generated.
        """
        signals_generated = 0
        sharing_validator = get_sharing_validator()

        async with get_db_context() as db:
            # PRIORITY 1: Get traders that users are actually following (with notifications)
            # Only include ACTIVE whales (exclude SHARING_DISABLED)
            followed_result = await db.execute(
                select(Whale)
                .join(UserWhaleFollow, Whale.id == UserWhaleFollow.whale_id)
                .where(
                    Whale.is_active == True,
                    Whale.data_status == "ACTIVE",  # VARCHAR column, use string
                    UserWhaleFollow.notify_on_trade == True,
                    Whale.exchange.in_(["BINANCE", "OKX", "BITGET", "BYBIT"])
                )
                .distinct()
                .order_by(Whale.priority_score.desc())
                .limit(max_traders)
            )
            followed_whales = list(followed_result.scalars().all())
            followed_ids = {w.id for w in followed_whales}

            # PRIORITY 2: Fill remaining slots with top traders by priority_score
            # Bitget traders will be prioritized (priority_score=80)
            remaining_slots = max_traders - len(followed_whales)
            additional_whales = []

            if remaining_slots > 0:
                additional_result = await db.execute(
                    select(Whale).where(
                        Whale.is_active == True,
                        Whale.data_status == "ACTIVE",  # VARCHAR column, use string
                        Whale.id.notin_(followed_ids) if followed_ids else True,
                        Whale.exchange.in_(["BINANCE", "OKX", "BITGET", "BYBIT"])
                    ).order_by(
                        Whale.priority_score.desc(),
                        Whale.score.desc()
                    ).limit(remaining_slots)
                )
                additional_whales = list(additional_result.scalars().all())

            # Combine: followed traders first, then top traders by priority
            whales = followed_whales + additional_whales

            # Log breakdown by exchange
            exchange_counts = {}
            for w in whales:
                ex = w.exchange or "UNKNOWN"
                exchange_counts[ex] = exchange_counts.get(ex, 0) + 1

            logger.info(
                f"Checking {len(followed_whales)} followed + {len(additional_whales)} top traders = {len(whales)} total. "
                f"By exchange: {exchange_counts}"
            )

            traders_with_positions = 0
            total_positions = 0
            sharing_disabled_count = 0

            for whale in whales:
                fetch_error = None
                current_positions = []

                try:
                    # Use exchange field (new) or fallback to wallet_address parsing
                    exchange = whale.exchange
                    uid = whale.exchange_uid

                    # Fallback for old data without exchange field
                    if not exchange or not uid:
                        parts = whale.wallet_address.split("_", 1)
                        if len(parts) != 2:
                            continue
                        exchange = parts[0].upper()
                        uid = parts[1]

                    # Fetch current positions
                    try:
                        if exchange == "BINANCE":
                            current_positions = await self.fetch_binance_trader_positions(uid)
                        elif exchange == "OKX":
                            current_positions = await self.fetch_okx_trader_positions(uid)
                        elif exchange == "BITGET":
                            current_positions = await self.fetch_bitget_trader_positions(uid)
                        elif exchange == "BYBIT":
                            current_positions = await self.fetch_bybit_trader_positions(uid)
                        elif exchange == "HYPERLIQUID":
                            current_positions = await self.fetch_hyperliquid_trader_positions(uid)
                        else:
                            continue
                    except Exception as e:
                        fetch_error = e
                        logger.warning(f"Error fetching positions for {whale.name}: {e}")

                    # Update sharing status using SharingValidator
                    new_status = await sharing_validator.check_and_update_status(
                        whale, current_positions, fetch_error
                    )

                    if new_status == "SHARING_DISABLED":
                        sharing_disabled_count += 1
                        logger.info(
                            f"Whale {whale.name} ({whale.exchange}) marked as SHARING_DISABLED"
                        )
                        # Skip signal generation for disabled whales
                        continue

                    # Get previous positions from Redis cache
                    cache_key = whale.wallet_address
                    previous_positions = self._get_cached_positions(cache_key)

                    # WARM-UP MODE: If cache is empty, generate signals ONLY for fresh positions
                    # This prevents copying stale positions after restart while still catching new ones
                    if not previous_positions and current_positions:
                        fresh_count = 0
                        stale_count = 0
                        for pos in current_positions:
                            if self._is_position_fresh(pos, MAX_POSITION_AGE_FOR_SIGNAL):
                                # Fresh position - generate signal!
                                action = SignalAction.BUY if pos.side == "LONG" else SignalAction.SELL
                                signal = await self._create_signal(db, whale, pos, action)
                                if signal:
                                    signals_generated += 1
                                    fresh_count += 1
                                    logger.info(
                                        f"WARM-UP FRESH: Signal for {whale.name} {pos.symbol} "
                                        f"(age: {(datetime.utcnow() - pos.update_time).total_seconds():.0f}s)"
                                    )
                            else:
                                stale_count += 1
                        logger.info(
                            f"WARM-UP: {whale.name} - {fresh_count} fresh signals, "
                            f"{stale_count} stale positions cached"
                        )
                        self._set_cached_positions(cache_key, current_positions)
                        continue

                    # Compare positions
                    previous_symbols = {p.symbol for p in previous_positions}
                    current_symbols = {p.symbol for p in current_positions}

                    # New positions (BUY signals)
                    new_symbols = current_symbols - previous_symbols
                    for pos in current_positions:
                        if pos.symbol in new_symbols:
                            signal = await self._create_signal(
                                db, whale, pos,
                                SignalAction.BUY if pos.side == "LONG" else SignalAction.SELL
                            )
                            if signal:
                                signals_generated += 1
                                logger.info(f"Generated BUY signal for {whale.name}: {pos.symbol}")

                    # Closed positions (SELL signals for longs, BUY signals for shorts)
                    closed_symbols = previous_symbols - current_symbols
                    for prev_pos in previous_positions:
                        if prev_pos.symbol in closed_symbols:
                            # Closing a position = opposite action
                            action = SignalAction.SELL if prev_pos.side == "LONG" else SignalAction.BUY
                            signal = await self._create_signal(
                                db, whale, prev_pos, action, is_close=True
                            )
                            if signal:
                                signals_generated += 1
                                logger.info(f"Generated CLOSE signal for {whale.name}: {prev_pos.symbol}")

                    # Track statistics
                    if current_positions:
                        traders_with_positions += 1
                        total_positions += len(current_positions)

                    # Update Redis cache
                    self._set_cached_positions(cache_key, current_positions)

                    # Exchange-specific delays to avoid rate limits
                    # Bitget has stricter rate limits, so we use longer delays
                    if exchange == "BITGET":
                        await asyncio.sleep(1.5)  # 1.5s for Bitget (stricter limits)
                    elif exchange == "OKX":
                        await asyncio.sleep(0.5)  # 0.5s for OKX
                    else:
                        await asyncio.sleep(0.3)  # 0.3s for Binance/Bybit

                except Exception as e:
                    logger.error(f"Error checking trader {whale.name}: {e}")

            await db.commit()

            logger.info(
                f"Signal generation complete: "
                f"{traders_with_positions}/{len(whales)} traders with open positions, "
                f"{total_positions} total positions, "
                f"{signals_generated} signals generated, "
                f"{sharing_disabled_count} marked as sharing disabled"
            )

        return signals_generated

    async def _create_signal(
        self,
        db,
        whale: Whale,
        position: TraderPosition,
        action: SignalAction,
        is_close: bool = False
    ) -> Optional[WhaleSignal]:
        """Create a whale signal from a position."""
        try:
            now = datetime.utcnow()

            # Generate unique tx hash
            tx_hash = self._generate_tx_hash(whale.id, position.symbol, action.value, now)

            # Check if signal already exists
            existing = await db.execute(
                select(WhaleSignal).where(WhaleSignal.tx_hash == tx_hash)
            )
            if existing.scalar_one_or_none():
                return None

            # Calculate position value in USD
            position_value = position.size * position.mark_price

            # Determine CEX symbol (remove USDT suffix for our format)
            cex_symbol = position.symbol
            if not cex_symbol.endswith("USDT"):
                cex_symbol = f"{cex_symbol}USDT"

            # Create signal
            signal = WhaleSignal(
                whale_id=whale.id,
                tx_hash=tx_hash,
                block_number=0,  # Not applicable for CEX trades
                chain="CEX",  # Mark as centralized exchange
                action=action,
                dex=whale.wallet_address.split("_")[0].upper(),  # BINANCE or OKX
                token_in="USDT" if action == SignalAction.BUY else position.symbol.replace("USDT", ""),
                token_in_address="",
                token_in_amount=position_value if action == SignalAction.BUY else position.size,
                token_out=position.symbol.replace("USDT", "") if action == SignalAction.BUY else "USDT",
                token_out_address="",
                token_out_amount=position.size if action == SignalAction.BUY else position_value,
                amount_usd=position_value,
                price_at_signal=position.mark_price,
                cex_symbol=cex_symbol,
                cex_available=True,
                futures_type=position.futures_type,  # USD-M or COIN-M
                leverage=position.leverage,  # Trader's actual leverage for copy trading
                is_close_signal=is_close,  # Mark if this is a position close signal
                confidence=self._determine_confidence(position, whale.score or 50),
                confidence_score=self._calculate_confidence_score(position, whale.score or 50),
                status=SignalStatus.PENDING,
                detected_at=now,
                tx_timestamp=position.update_time,
            )

            db.add(signal)
            await db.flush()

            # Send Telegram notifications to followers
            await self._notify_followers(db, whale, signal, position, action)

            # FAST PATH: Trigger immediate execution
            # This bypasses the check_whale_positions queue for minimal latency
            if is_close:
                # Close signal - immediately queue close for all users with matching positions
                await self._trigger_immediate_close(db, whale, signal)
            else:
                # Open signal - immediately queue copy trade for eligible users
                await self._trigger_immediate_copy(db, whale, signal)

            return signal

        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return None

    async def _notify_followers(
        self,
        db,
        whale: Whale,
        signal: WhaleSignal,
        position: TraderPosition,
        action: SignalAction
    ):
        """Send alerts to all users following this whale with notifications enabled."""
        try:
            # Find all users who follow this whale with notify_on_trade=True
            result = await db.execute(
                select(UserWhaleFollow.user_id)
                .where(
                    UserWhaleFollow.whale_id == whale.id,
                    UserWhaleFollow.notify_on_trade == True
                )
            )
            follower_ids = [row[0] for row in result.all()]

            if not follower_ids:
                logger.debug(f"No followers with notifications enabled for {whale.name}")
                return

            # Import here to avoid circular imports
            from app.workers.tasks.notification_tasks import send_whale_alert

            # Prepare signal data for notification
            signal_data = {
                "signal_id": signal.id,
                "action": action.value,
                "symbol": position.symbol,
                "whale_name": whale.name,
                "amount_usd": float(position.size * position.mark_price),
                "confidence": signal.confidence.value,
                "leverage": position.leverage,
                "entry_price": float(position.entry_price),
                "roe": float(position.roe),
            }

            # Queue notification task
            # DISABLED: User only wants trade open/close notifications, not whale signal alerts
            # send_whale_alert.delay(follower_ids, signal_data)
            logger.debug(f"Whale alert disabled for {len(follower_ids)} followers of {whale.name}: {position.symbol} {action.value}")

        except Exception as e:
            # Don't fail the signal creation if notification fails
            logger.error(f"Error notifying followers: {e}")


async def generate_trader_signals() -> int:
    """
    Main function to generate signals from trader positions.
    Should be called periodically (e.g., every 2 minutes).
    """
    service = TraderSignalService()

    try:
        signals_count = await service.check_and_generate_signals()
        logger.info(f"Generated {signals_count} new signals from trader positions")
        return signals_count

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        return 0

    finally:
        await service.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(generate_trader_signals())
