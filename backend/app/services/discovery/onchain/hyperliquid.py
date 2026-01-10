"""
Hyperliquid OnChain Tracker Service

Tracks whale positions on Hyperliquid DEX using their public API.
Hyperliquid is fully OnChain - all positions are public by design.
NO "sharing disabled" issues - 100% transparent!

API Endpoints:
- POST https://api.hyperliquid.xyz/info
  - type: "clearinghouseState" - Get user's positions and margin
  - type: "meta" - Get available perpetual markets
  - type: "webData2" - Get comprehensive user data

- GET https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
  - Public leaderboard with 28k+ traders
  - Full wallet addresses, PnL, ROI, volume data
  - No authentication required!
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HyperliquidPosition:
    """Represents a position on Hyperliquid."""
    coin: str  # Symbol like "BTC", "ETH", "SOL"
    size: Decimal  # Position size (negative = short)
    entry_price: Decimal
    leverage: int
    leverage_type: str  # "isolated" or "cross"
    unrealized_pnl: Decimal
    margin_used: Decimal
    liquidation_price: Optional[Decimal] = None
    position_value: Optional[Decimal] = None
    max_leverage: int = 50

    @property
    def side(self) -> str:
        """Get position side based on size."""
        return "LONG" if self.size > 0 else "SHORT"

    @property
    def abs_size(self) -> Decimal:
        """Get absolute position size."""
        return abs(self.size)


@dataclass
class HyperliquidAccount:
    """Represents a Hyperliquid account state."""
    address: str
    account_value: Decimal
    total_margin_used: Decimal
    withdrawable: Decimal
    positions: list[HyperliquidPosition] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_open_positions(self) -> bool:
        return len(self.positions) > 0


@dataclass
class HyperliquidTrader:
    """Represents a top trader discovered from leaderboard."""
    address: str
    display_name: Optional[str] = None
    account_value: Decimal = Decimal("0")
    # Daily performance
    pnl_1d: Decimal = Decimal("0")
    roi_1d: Decimal = Decimal("0")
    volume_1d: Decimal = Decimal("0")
    # Weekly performance
    pnl_7d: Decimal = Decimal("0")
    roi_7d: Decimal = Decimal("0")
    volume_7d: Decimal = Decimal("0")
    # Monthly performance (30d)
    pnl_30d: Decimal = Decimal("0")
    roi_30d: Decimal = Decimal("0")
    volume_30d: Decimal = Decimal("0")
    # All time performance
    pnl_all_time: Decimal = Decimal("0")
    roi_all_time: Decimal = Decimal("0")
    volume_all_time: Decimal = Decimal("0")

    @property
    def is_profitable_30d(self) -> bool:
        return self.pnl_30d > 0

    @property
    def roi_30d_percent(self) -> float:
        """ROI as percentage (e.g., 0.15 -> 15%)"""
        return float(self.roi_30d) * 100


class HyperliquidTracker:
    """
    Service for tracking whale positions on Hyperliquid.

    Hyperliquid is a decentralized perpetuals exchange where all
    positions are OnChain and publicly visible - no "sharing disabled" issues.

    Usage:
        tracker = HyperliquidTracker()

        # Get positions for a known whale address
        account = await tracker.get_account_state("0x...")

        # Get top traders from curated list
        traders = await tracker.get_known_whales()

        # Fetch positions for multiple addresses
        accounts = await tracker.fetch_multiple_accounts(addresses)
    """

    BASE_URL = "https://api.hyperliquid.xyz"
    LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

    # Rate limits: Hyperliquid is generally permissive
    # but we should still be respectful
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests
    MAX_CONCURRENT = 10

    # Leaderboard cache TTL (5 minutes)
    LEADERBOARD_CACHE_TTL = 300

    # Known whale addresses (curated list - fallback if leaderboard fails)
    KNOWN_WHALE_ADDRESSES = [
        ("0x87f9cd15f5050a9283b8896300f7c8cf69ece2cf", "TopTrader1"),  # $76M account
        ("0x50b39f20fc0387d3e69e3a7e5e26768a2ad3e8c6", "TopTrader2"),  # 379% ROI
        ("0xffbd16b0e8a7e53e7519c07cf7b4c1f76ddb1628", "TopTrader3"),  # $34M account
        ("0x152e68caf43f46b2f7a0f8e98f5b82ce5c7c9dc", "TopTrader4"),  # $24M account
        ("0xb3179a9ca1b883ae8fbd0ef8a6d4b89e7e2a83ae", "TopTrader5"),  # $233M account
    ]

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0
        # Leaderboard cache
        self._leaderboard_cache: list[HyperliquidTrader] = []
        self._leaderboard_cache_time: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        return self._client

    async def _rate_limit(self):
        """Apply rate limiting."""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _post(self, data: dict) -> dict:
        """Make POST request to Hyperliquid API."""
        client = await self._get_client()
        await self._rate_limit()

        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    f"{self.BASE_URL}/info",
                    json=data
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Hyperliquid API error (attempt {attempt + 1}): "
                    f"{e.response.status_code}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    raise
            except httpx.RequestError as e:
                logger.warning(
                    f"Hyperliquid request error (attempt {attempt + 1}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    raise

        return {}

    async def _get(self, url: str) -> dict:
        """Make GET request."""
        client = await self._get_client()
        await self._rate_limit()

        for attempt in range(self.max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Hyperliquid GET error (attempt {attempt + 1}): "
                    f"{e.response.status_code}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    raise
            except httpx.RequestError as e:
                logger.warning(
                    f"Hyperliquid GET request error (attempt {attempt + 1}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    raise
        return {}

    async def fetch_leaderboard(
        self,
        limit: int = 500,
        min_account_value: Decimal = Decimal("100000"),
        min_pnl_30d: Decimal = Decimal("0"),
        use_cache: bool = True
    ) -> list[HyperliquidTrader]:
        """
        Fetch top traders from Hyperliquid leaderboard.

        The leaderboard API returns ~28k traders with full performance data.
        No authentication required!

        Args:
            limit: Maximum number of traders to return
            min_account_value: Minimum account value filter
            min_pnl_30d: Minimum 30d PnL filter (positive = profitable only)
            use_cache: Use cached data if available and fresh

        Returns:
            List of HyperliquidTrader objects sorted by 30d PnL
        """
        import time

        # Check cache
        if use_cache and self._leaderboard_cache:
            age = time.time() - self._leaderboard_cache_time
            if age < self.LEADERBOARD_CACHE_TTL:
                logger.debug(f"Using cached leaderboard (age: {age:.0f}s)")
                # Apply filters to cached data
                filtered = [
                    t for t in self._leaderboard_cache
                    if t.account_value >= min_account_value
                    and t.pnl_30d >= min_pnl_30d
                ]
                return filtered[:limit]

        try:
            data = await self._get(self.LEADERBOARD_URL)
            rows = data.get("leaderboardRows", [])

            traders = []
            for row in rows:
                # Parse window performances
                perfs = {p[0]: p[1] for p in row.get("windowPerformances", [])}

                day = perfs.get("day", {})
                week = perfs.get("week", {})
                month = perfs.get("month", {})
                all_time = perfs.get("allTime", {})

                trader = HyperliquidTrader(
                    address=row["ethAddress"],
                    display_name=row.get("displayName"),
                    account_value=Decimal(str(row.get("accountValue", "0"))),
                    # Daily
                    pnl_1d=Decimal(str(day.get("pnl", "0"))),
                    roi_1d=Decimal(str(day.get("roi", "0"))),
                    volume_1d=Decimal(str(day.get("vlm", "0"))),
                    # Weekly
                    pnl_7d=Decimal(str(week.get("pnl", "0"))),
                    roi_7d=Decimal(str(week.get("roi", "0"))),
                    volume_7d=Decimal(str(week.get("vlm", "0"))),
                    # Monthly (30d)
                    pnl_30d=Decimal(str(month.get("pnl", "0"))),
                    roi_30d=Decimal(str(month.get("roi", "0"))),
                    volume_30d=Decimal(str(month.get("vlm", "0"))),
                    # All time
                    pnl_all_time=Decimal(str(all_time.get("pnl", "0"))),
                    roi_all_time=Decimal(str(all_time.get("roi", "0"))),
                    volume_all_time=Decimal(str(all_time.get("vlm", "0"))),
                )
                traders.append(trader)

            # Sort by 30d PnL (descending)
            traders.sort(key=lambda t: t.pnl_30d, reverse=True)

            # Update cache with full unfiltered data
            self._leaderboard_cache = traders
            self._leaderboard_cache_time = time.time()

            logger.info(f"Fetched {len(traders)} traders from Hyperliquid leaderboard")

            # Apply filters
            filtered = [
                t for t in traders
                if t.account_value >= min_account_value
                and t.pnl_30d >= min_pnl_30d
            ]

            return filtered[:limit]

        except Exception as e:
            logger.error(f"Error fetching Hyperliquid leaderboard: {e}")
            # Return cached data if available
            if self._leaderboard_cache:
                logger.info("Returning cached leaderboard data after error")
                return self._leaderboard_cache[:limit]
            return []

    async def discover_top_traders(
        self,
        limit: int = 100,
        min_account_value: Decimal = Decimal("500000"),
        min_roi_30d: Decimal = Decimal("0.05"),  # 5%+
        only_profitable: bool = True
    ) -> list[HyperliquidTrader]:
        """
        Discover top traders suitable for copy trading.

        Applies stricter filters for quality whale discovery:
        - High account value (serious traders)
        - Positive ROI (actually profitable)
        - Recent activity (has 30d stats)

        Args:
            limit: Max traders to return
            min_account_value: Minimum account value ($500k default)
            min_roi_30d: Minimum 30d ROI (0.05 = 5%)
            only_profitable: Only include traders with positive 30d PnL

        Returns:
            List of qualified traders
        """
        min_pnl = Decimal("0") if only_profitable else Decimal("-999999999")

        traders = await self.fetch_leaderboard(
            limit=limit * 2,  # Fetch extra to filter
            min_account_value=min_account_value,
            min_pnl_30d=min_pnl,
            use_cache=True
        )

        # Additional filtering by ROI
        qualified = [
            t for t in traders
            if t.roi_30d >= min_roi_30d
        ]

        logger.info(
            f"Discovered {len(qualified)} qualified Hyperliquid traders "
            f"(min ${min_account_value}, min ROI {float(min_roi_30d)*100:.1f}%)"
        )

        return qualified[:limit]

    async def get_meta(self) -> dict:
        """Get Hyperliquid market metadata."""
        return await self._post({"type": "meta"})

    async def get_account_state(
        self,
        address: str,
        dex: str = ""
    ) -> Optional[HyperliquidAccount]:
        """
        Get account state including positions for a wallet address.

        Args:
            address: Ethereum address (0x...)
            dex: Perp dex name (default: main perps)

        Returns:
            HyperliquidAccount with positions or None if error
        """
        try:
            data = await self._post({
                "type": "clearinghouseState",
                "user": address.lower(),
                "dex": dex
            })

            if not data:
                return None

            # Parse margin summary
            margin = data.get("marginSummary", {})
            account_value = Decimal(str(margin.get("accountValue", "0")))
            total_margin = Decimal(str(margin.get("totalMarginUsed", "0")))
            withdrawable = Decimal(str(data.get("withdrawable", "0")))

            # Parse positions
            positions = []
            for pos_data in data.get("assetPositions", []):
                pos = pos_data.get("position", {})
                if not pos:
                    continue

                # Size is signed: positive = long, negative = short
                size = Decimal(str(pos.get("szi", "0")))
                if size == 0:
                    continue  # Skip zero positions

                leverage_info = pos.get("leverage", {})

                position = HyperliquidPosition(
                    coin=pos.get("coin", ""),
                    size=size,
                    entry_price=Decimal(str(pos.get("entryPx", "0"))),
                    leverage=int(leverage_info.get("value", 1)),
                    leverage_type=leverage_info.get("type", "cross"),
                    unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", "0"))),
                    margin_used=Decimal(str(pos.get("marginUsed", "0"))),
                    liquidation_price=Decimal(str(pos.get("liquidationPx", "0"))) if pos.get("liquidationPx") else None,
                    position_value=Decimal(str(pos.get("positionValue", "0"))) if pos.get("positionValue") else None,
                    max_leverage=int(pos.get("maxLeverage", 50)),
                )
                positions.append(position)

            return HyperliquidAccount(
                address=address,
                account_value=account_value,
                total_margin_used=total_margin,
                withdrawable=withdrawable,
                positions=positions,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Error fetching Hyperliquid account {address}: {e}")
            return None

    async def get_webdata2(self, address: str) -> Optional[dict]:
        """
        Get comprehensive user data via webData2 endpoint.
        Includes positions, open orders, and more.
        """
        try:
            return await self._post({
                "type": "webData2",
                "user": address.lower()
            })
        except Exception as e:
            logger.error(f"Error fetching webData2 for {address}: {e}")
            return None

    async def fetch_multiple_accounts(
        self,
        addresses: list[str],
        max_concurrent: int = None
    ) -> list[HyperliquidAccount]:
        """
        Fetch account states for multiple addresses concurrently.

        Args:
            addresses: List of wallet addresses
            max_concurrent: Max concurrent requests (default: self.MAX_CONCURRENT)

        Returns:
            List of HyperliquidAccount objects (excluding errors)
        """
        max_concurrent = max_concurrent or self.MAX_CONCURRENT
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(address: str):
            async with semaphore:
                return await self.get_account_state(address)

        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        accounts = []
        for addr, result in zip(addresses, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch {addr}: {result}")
            elif result is not None:
                accounts.append(result)

        return accounts

    async def get_known_whales(self) -> list[tuple[str, str]]:
        """
        Get list of known whale addresses.

        Returns:
            List of (address, name) tuples
        """
        return list(self.KNOWN_WHALE_ADDRESSES)

    async def discover_active_whales(
        self,
        min_account_value: Decimal = Decimal("10000"),
        min_positions: int = 1
    ) -> list[HyperliquidAccount]:
        """
        Find whales from known addresses that have active positions.

        Args:
            min_account_value: Minimum account value in USD
            min_positions: Minimum number of open positions

        Returns:
            List of active whale accounts
        """
        addresses = [addr for addr, _ in self.KNOWN_WHALE_ADDRESSES]
        accounts = await self.fetch_multiple_accounts(addresses)

        active_whales = [
            acc for acc in accounts
            if acc.account_value >= min_account_value
            and len(acc.positions) >= min_positions
        ]

        logger.info(
            f"Discovered {len(active_whales)} active Hyperliquid whales "
            f"(min ${min_account_value}, min {min_positions} positions)"
        )

        return active_whales

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Convenience functions for use without instantiating class
_default_tracker: Optional[HyperliquidTracker] = None


def get_tracker() -> HyperliquidTracker:
    """Get or create default tracker instance."""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = HyperliquidTracker()
    return _default_tracker


async def fetch_hyperliquid_positions(address: str) -> Optional[HyperliquidAccount]:
    """Convenience function to fetch positions for an address."""
    tracker = get_tracker()
    return await tracker.get_account_state(address)


async def fetch_hyperliquid_whales() -> list[HyperliquidAccount]:
    """Convenience function to fetch all known whales."""
    tracker = get_tracker()
    return await tracker.discover_active_whales()


async def fetch_hyperliquid_leaderboard(
    limit: int = 100,
    min_account_value: Decimal = Decimal("100000")
) -> list[HyperliquidTrader]:
    """Convenience function to fetch leaderboard traders."""
    tracker = get_tracker()
    return await tracker.fetch_leaderboard(
        limit=limit,
        min_account_value=min_account_value
    )


async def discover_hyperliquid_top_traders(
    limit: int = 50,
    min_roi_30d: float = 0.05
) -> list[HyperliquidTrader]:
    """Convenience function to discover top traders for copy trading."""
    tracker = get_tracker()
    return await tracker.discover_top_traders(
        limit=limit,
        min_roi_30d=Decimal(str(min_roi_30d))
    )
