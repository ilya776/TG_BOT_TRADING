"""
Parallel Position Fetcher
Fetches trader positions in parallel across multiple proxies.

This service enables high-throughput position fetching by:
- Distributing requests across proxy pool
- Parallel execution with semaphore limiting
- Automatic retry with proxy rotation on failures
- Rate limit handling per-proxy
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx

from app.models.proxy import Proxy
from app.models.whale import Whale
from app.services.polling.proxy_manager import ProxyManager, get_proxy_manager
from app.services.polling.rate_limit_manager import RateLimitManager, get_rate_limit_manager

logger = logging.getLogger(__name__)

# Default concurrency limits - AGGRESSIVE for real-time
DEFAULT_MAX_CONCURRENT = 25  # Increased from 10 for faster polling
DEFAULT_TIMEOUT_SECONDS = 15  # Reduced from 30 for faster failure detection
DEFAULT_RETRY_COUNT = 1  # Reduced from 2 - faster fail-over

# Per-exchange concurrency limits to avoid rate limiting
# Bitget and OKX are more aggressive with blocking
EXCHANGE_CONCURRENCY = {
    "BINANCE": 10,  # Binance can handle more
    "OKX": 3,  # OKX is stricter
    "BITGET": 3,  # Bitget blocks quickly
    "BYBIT": 5,
    "HYPERLIQUID": 10,  # On-chain, no limits
}


@dataclass
class FetchResult:
    """Result of a position fetch attempt."""
    whale_id: int
    success: bool
    positions: list  # List of TraderPosition
    error: Optional[str] = None
    response_time_ms: int = 0
    proxy_id: Optional[int] = None
    rate_limited: bool = False


class ParallelPositionFetcher:
    """
    Fetches positions in parallel across multiple proxies.

    Usage:
        fetcher = ParallelPositionFetcher(proxy_manager)
        results = await fetcher.fetch_all(whales)
        for whale_id, result in results.items():
            if result.success:
                process_positions(result.positions)
    """

    def __init__(
        self,
        proxy_manager: Optional[ProxyManager] = None,
        rate_limit_manager: Optional[RateLimitManager] = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.proxy_manager = proxy_manager or get_proxy_manager()
        self.rate_limit_manager = rate_limit_manager or get_rate_limit_manager()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout_seconds

        # Per-exchange semaphores to prevent rate limiting
        self.exchange_semaphores = {
            exchange: asyncio.Semaphore(limit)
            for exchange, limit in EXCHANGE_CONCURRENCY.items()
        }
        self.default_exchange_semaphore = asyncio.Semaphore(5)

        # Import here to avoid circular imports
        from app.services.trader_signals import TraderSignalService
        self.signal_service = TraderSignalService()

    async def fetch_all(
        self,
        whales: list[Whale],
    ) -> dict[int, FetchResult]:
        """
        Fetch positions for all whales in parallel.

        Args:
            whales: List of whales to fetch positions for

        Returns:
            Dict mapping whale_id -> FetchResult
        """
        if not whales:
            return {}

        # Group whales by exchange for optimal proxy distribution
        by_exchange = self._group_by_exchange(whales)

        tasks = []
        for whale in whales:
            task = self._fetch_with_semaphore(whale)
            tasks.append(task)

        # Execute all fetches in parallel
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        results = {}
        for whale, result in zip(whales, results_list):
            if isinstance(result, Exception):
                results[whale.id] = FetchResult(
                    whale_id=whale.id,
                    success=False,
                    positions=[],
                    error=str(result),
                )
            else:
                results[whale.id] = result

        # Log summary
        success_count = sum(1 for r in results.values() if r.success)
        rate_limited_count = sum(1 for r in results.values() if r.rate_limited)
        logger.info(
            f"Parallel fetch complete: {success_count}/{len(whales)} success, "
            f"{rate_limited_count} rate limited"
        )

        return results

    async def fetch_by_exchange(
        self,
        whales: list[Whale],
        exchange: str,
    ) -> dict[int, FetchResult]:
        """Fetch positions for whales from a specific exchange."""
        filtered = [w for w in whales if w.exchange == exchange]
        return await self.fetch_all(filtered)

    async def _fetch_with_semaphore(self, whale: Whale) -> FetchResult:
        """Fetch with semaphore to limit concurrency per-exchange."""
        exchange = whale.exchange or "UNKNOWN"
        exchange_semaphore = self.exchange_semaphores.get(
            exchange, self.default_exchange_semaphore
        )

        # Use both global and per-exchange semaphore
        async with self.semaphore:
            async with exchange_semaphore:
                return await self._fetch_with_retry(whale)

    async def _fetch_with_retry(
        self,
        whale: Whale,
        retry_count: int = DEFAULT_RETRY_COUNT,
    ) -> FetchResult:
        """Fetch with automatic retry, rate limit handling, and proxy rotation."""
        last_error = None
        exchange = whale.exchange or "UNKNOWN"
        uid = whale.exchange_uid

        # Fallback for old data
        if not exchange or not uid:
            parts = whale.wallet_address.split("_", 1)
            if len(parts) != 2:
                return FetchResult(
                    whale_id=whale.id,
                    success=False,
                    positions=[],
                    error="Invalid wallet_address format",
                )
            exchange = parts[0].upper()
            uid = parts[1]

        # Check rate limit before starting
        if not await self.rate_limit_manager.can_proceed(exchange):
            # Wait for cooldown if needed
            waited = await self.rate_limit_manager.wait_if_needed(exchange)
            if waited > 0:
                logger.debug(f"Waited {waited:.1f}s for {exchange} rate limit cooldown")

        for attempt in range(retry_count + 1):
            proxy = await self.proxy_manager.get_best_proxy(exchange)

            start_time = time.time()
            result = await self._do_fetch(whale, exchange, uid, proxy)
            elapsed_ms = int((time.time() - start_time) * 1000)

            result.response_time_ms = elapsed_ms
            result.proxy_id = proxy.id if proxy else None

            # Record request outcome for proxy manager
            if proxy:
                await self.proxy_manager.record_request(
                    proxy=proxy,
                    exchange=exchange,
                    success=result.success,
                    response_time_ms=elapsed_ms,
                    rate_limited=result.rate_limited,
                )

            if result.success:
                # Record success with rate limit manager
                await self.rate_limit_manager.record_success(exchange)
                return result

            last_error = result.error

            # If rate limited, record and wait for backoff
            if result.rate_limited:
                backoff_time = await self.rate_limit_manager.record_rate_limit(exchange)
                logger.warning(
                    f"Rate limited for {whale.name} on {exchange}, "
                    f"backing off {backoff_time:.1f}s (attempt {attempt + 1}/{retry_count + 1})"
                )
                if attempt < retry_count:
                    await asyncio.sleep(min(backoff_time, 10))  # Cap retry wait at 10s
                continue

            # Other errors - retry with exponential backoff
            if attempt < retry_count:
                await asyncio.sleep(0.5 * (attempt + 1))

        return FetchResult(
            whale_id=whale.id,
            success=False,
            positions=[],
            error=last_error or "Max retries exceeded",
            rate_limited=result.rate_limited if result else False,
        )

    async def _do_fetch(
        self,
        whale: Whale,
        exchange: str,
        uid: str,
        proxy: Optional[Proxy],
    ) -> FetchResult:
        """Execute the actual fetch request."""
        try:
            # Build httpx client with proxy if available
            proxies = proxy.url if proxy else None

            # Connection limits to prevent exhaustion
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=15.0,
            )
            timeout = httpx.Timeout(
                connect=5.0,  # Quick fail on connect
                read=self.timeout,
                write=5.0,
                pool=10.0,
            )

            async with httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                proxies=proxies,
            ) as client:
                # Temporarily replace client in signal service
                original_client = self.signal_service.client
                self.signal_service.client = client

                try:
                    if exchange == "BINANCE":
                        positions = await self.signal_service.fetch_binance_trader_positions(uid)
                    elif exchange == "OKX":
                        positions = await self.signal_service.fetch_okx_trader_positions(uid)
                    elif exchange == "BITGET":
                        positions = await self.signal_service.fetch_bitget_trader_positions(uid)
                    elif exchange == "HYPERLIQUID":
                        # Hyperliquid uses wallet address (0x...) as uid
                        positions = await self.signal_service.fetch_hyperliquid_trader_positions(uid)
                    else:
                        return FetchResult(
                            whale_id=whale.id,
                            success=False,
                            positions=[],
                            error=f"Unsupported exchange: {exchange}",
                        )

                    return FetchResult(
                        whale_id=whale.id,
                        success=True,
                        positions=positions,
                    )

                finally:
                    self.signal_service.client = original_client

        except httpx.HTTPStatusError as e:
            # Detect rate limit from various indicators
            rate_limited = e.response.status_code in (429, 418, 403)  # 418 = I'm a teapot (some use for rate limit)
            error_text = str(e.response.text)[:200]

            # Some exchanges return rate limit as 200 with error code
            if "rate" in error_text.lower() or "limit" in error_text.lower():
                rate_limited = True
            if "-1015" in error_text:  # Binance rate limit
                rate_limited = True
            if "50011" in error_text:  # OKX rate limit
                rate_limited = True

            return FetchResult(
                whale_id=whale.id,
                success=False,
                positions=[],
                error=f"HTTP {e.response.status_code}: {error_text}",
                rate_limited=rate_limited,
            )

        except httpx.TimeoutException:
            return FetchResult(
                whale_id=whale.id,
                success=False,
                positions=[],
                error="Timeout",
            )

        except Exception as e:
            error_str = str(e)
            # Check for rate limit in exception message
            rate_limited = any(term in error_str.lower() for term in ["rate", "limit", "too many", "429"])

            return FetchResult(
                whale_id=whale.id,
                success=False,
                positions=[],
                error=error_str,
                rate_limited=rate_limited,
            )

    def _group_by_exchange(self, whales: list[Whale]) -> dict[str, list[Whale]]:
        """Group whales by exchange for optimal proxy distribution."""
        by_exchange = {}
        for whale in whales:
            exchange = whale.exchange or "UNKNOWN"
            if exchange not in by_exchange:
                by_exchange[exchange] = []
            by_exchange[exchange].append(whale)
        return by_exchange


# Singleton instance
_fetcher: Optional[ParallelPositionFetcher] = None


def get_position_fetcher() -> ParallelPositionFetcher:
    """Get singleton ParallelPositionFetcher instance."""
    global _fetcher
    if _fetcher is None:
        _fetcher = ParallelPositionFetcher()
    return _fetcher
