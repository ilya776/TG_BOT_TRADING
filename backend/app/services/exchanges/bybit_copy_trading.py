"""
Bybit Copy Trading Service
Fetches master traders and their positions from Bybit's internal copy trading API.

API Endpoints discovered via reverse engineering:
- Leaderboard: /x-api/fapi/beehive/public/v1/common/trader-leaderboard
- Positions: /x-api/fapi/beehive/public/v1/common/position/list
- Trader Info: /x-api/fapi/beehive/private/v1/pub-leader/info

NOTE: Bybit uses Akamai bot protection. Direct HTTP requests are blocked with 403.
This service supports two modes:
1. Browser-based (using Playwright) - RECOMMENDED, bypasses protection
2. Direct HTTP with proxy - Requires bypass proxy service

The browser-based mode should be used for initial data fetch and periodic sync,
while direct HTTP can be used if you have a working proxy/bypass solution.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Try to import Playwright (optional dependency)
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Bybit browser-based fetching disabled")


@dataclass
class BybitMasterTrader:
    """Represents a Bybit copy trading master trader."""
    leader_mark: str  # Unique identifier (URL-safe base64)
    nickname: str
    roi_7d: Decimal
    roi_30d: Decimal
    pnl_7d: Decimal
    pnl_total: Decimal
    win_rate: Decimal
    followers_count: int
    aum: Decimal  # Assets Under Management
    trading_days: int
    stability_index: Decimal
    rank: int


@dataclass
class BybitPosition:
    """Represents a position held by a Bybit master trader."""
    symbol: str
    side: str  # "Buy" (Long) or "Sell" (Short)
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: int
    unrealized_pnl: Decimal
    created_time: datetime
    updated_time: datetime


class BybitCopyTradingService:
    """
    Service to fetch copy trading data from Bybit.

    Uses Bybit's internal web API (x-api) which is public but undocumented.
    These endpoints power the Bybit copy trading leaderboard web interface.

    Rate Limits (estimated):
    - 10 requests per second
    - 500 requests per minute
    """

    BASE_URL = "https://www.bybit.com"

    # Ranking form types
    RANKING_TRADERS_PNL = "RANKING_FORM_TRADERS_PNL"  # By Master's P&L
    RANKING_FOLLOWERS_PNL = "RANKING_FORM_FOLLOWERS_PROFITS"  # By Followers' P&L
    RANKING_ROI = "RANKING_FORM_ROI"  # By ROI

    # Period types
    PERIOD_WEEK = "LEADERBOARD_PERIOD_WEEK"
    PERIOD_MONTH = "LEADERBOARD_PERIOD_MONTH"
    PERIOD_ALL = "LEADERBOARD_PERIOD_ALL"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.bybit.com/copyTrading/en/leaderboard-master",
                "Origin": "https://www.bybit.com",
            }
        )
        self._request_count = 0
        self._last_request_time = 0.0

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _rate_limit(self):
        """Simple rate limiting - max 10 req/s."""
        import time
        current_time = time.time()
        if current_time - self._last_request_time < 0.1:  # 100ms between requests
            await asyncio.sleep(0.1)
        self._last_request_time = time.time()

    async def fetch_leaderboard(
        self,
        ranking_form: str = RANKING_TRADERS_PNL,
        period: str = PERIOD_WEEK,
        limit: int = 100,
    ) -> list[BybitMasterTrader]:
        """
        Fetch the copy trading leaderboard.

        Args:
            ranking_form: Type of ranking (PNL, ROI, etc.)
            period: Time period (WEEK, MONTH, ALL)
            limit: Maximum number of traders to fetch

        Returns:
            List of BybitMasterTrader objects
        """
        traders = []

        try:
            await self._rate_limit()

            # Calculate end time (current week end timestamp in milliseconds * 1000)
            # The API uses endTimeE3 which is timestamp in milliseconds * 1000 (epoch * 10^6)
            import time
            # Round to start of current week (Sunday)
            now = int(time.time())
            # API seems to use a specific format, let's try without it first

            url = f"{self.BASE_URL}/x-api/fapi/beehive/public/v1/common/trader-leaderboard"
            params = {
                "rankingForm": ranking_form,
                "period": period,
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Bybit leaderboard API returned {response.status_code}: {response.text[:200]}")
                return traders

            data = response.json()

            if data.get("retCode") != 0:
                logger.warning(f"Bybit API error: {data.get('retMsg')}")
                return traders

            result = data.get("result", {})
            trader_list = result.get("list", [])

            for i, item in enumerate(trader_list[:limit]):
                try:
                    trader = BybitMasterTrader(
                        leader_mark=item.get("leaderMark", ""),
                        nickname=item.get("nickName", f"Bybit Trader #{i+1}"),
                        roi_7d=self._parse_decimal(item.get("roi", item.get("roiE4", 0)), divisor=10000 if "roiE4" in item else 1),
                        roi_30d=self._parse_decimal(item.get("roiMonth", 0)),
                        pnl_7d=self._parse_decimal(item.get("pnl", item.get("pnlE4", 0)), divisor=10000 if "pnlE4" in item else 1),
                        pnl_total=self._parse_decimal(item.get("totalPnl", 0)),
                        win_rate=self._parse_decimal(item.get("winRate", 0)) * 100,
                        followers_count=int(item.get("followerNum", item.get("copyTraderNum", 0))),
                        aum=self._parse_decimal(item.get("aum", item.get("aumE4", 0)), divisor=10000 if "aumE4" in item else 1),
                        trading_days=int(item.get("tradeDays", 0)),
                        stability_index=self._parse_decimal(item.get("stabilityIndex", 0)),
                        rank=i + 1,
                    )
                    traders.append(trader)
                except Exception as e:
                    logger.warning(f"Error parsing Bybit trader {i}: {e}")

            logger.info(f"Fetched {len(traders)} traders from Bybit leaderboard ({ranking_form})")

        except Exception as e:
            logger.error(f"Error fetching Bybit leaderboard: {e}")

        return traders

    async def fetch_trader_positions(
        self,
        leader_mark: str,
    ) -> list[BybitPosition]:
        """
        Fetch current open positions for a master trader.

        Args:
            leader_mark: The trader's unique identifier

        Returns:
            List of BybitPosition objects
        """
        positions = []

        try:
            await self._rate_limit()

            url = f"{self.BASE_URL}/x-api/fapi/beehive/public/v1/common/position/list"
            params = {"leaderMark": leader_mark}

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Bybit positions API returned {response.status_code}")
                return positions

            data = response.json()

            if data.get("retCode") != 0:
                logger.warning(f"Bybit positions API error: {data.get('retMsg')}")
                return positions

            result = data.get("result", {})
            position_list = result.get("list", [])

            for item in position_list:
                try:
                    # Parse timestamps
                    created_time = self._parse_timestamp(item.get("createdAtE3", item.get("createdAt", 0)))
                    updated_time = self._parse_timestamp(item.get("updatedAtE3", item.get("updatedAt", 0)))

                    position = BybitPosition(
                        symbol=item.get("symbol", ""),
                        side=item.get("side", ""),  # "Buy" or "Sell"
                        size=self._parse_decimal(item.get("size", item.get("sizeE4", 0)), divisor=10000 if "sizeE4" in item else 1),
                        entry_price=self._parse_decimal(item.get("entryPrice", item.get("entryPriceE4", 0)), divisor=10000 if "entryPriceE4" in item else 1),
                        mark_price=self._parse_decimal(item.get("markPrice", item.get("markPriceE4", 0)), divisor=10000 if "markPriceE4" in item else 1),
                        leverage=int(item.get("leverage", 1)),
                        unrealized_pnl=self._parse_decimal(item.get("unrealisedPnl", item.get("unrealisedPnlE4", 0)), divisor=10000 if "unrealisedPnlE4" in item else 1),
                        created_time=created_time,
                        updated_time=updated_time,
                    )
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Error parsing Bybit position: {e}")

            logger.debug(f"Fetched {len(positions)} positions for Bybit trader {leader_mark[:20]}...")

        except Exception as e:
            logger.error(f"Error fetching Bybit positions for {leader_mark[:20]}...: {e}")

        return positions

    async def fetch_trader_info(
        self,
        leader_mark: str,
    ) -> Optional[dict]:
        """
        Fetch detailed information about a master trader.

        Args:
            leader_mark: The trader's unique identifier

        Returns:
            Dict with trader details or None
        """
        try:
            await self._rate_limit()

            url = f"{self.BASE_URL}/x-api/fapi/beehive/private/v1/pub-leader/info"
            params = {"leaderMark": leader_mark}

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                return None

            data = response.json()

            if data.get("retCode") != 0:
                return None

            return data.get("result", {})

        except Exception as e:
            logger.error(f"Error fetching Bybit trader info: {e}")
            return None

    async def fetch_trader_subscribe_info(
        self,
        leader_mark: str,
    ) -> Optional[dict]:
        """
        Fetch subscription/copy trading settings for a master trader.

        Args:
            leader_mark: The trader's unique identifier

        Returns:
            Dict with subscription info or None
        """
        try:
            await self._rate_limit()

            url = f"{self.BASE_URL}/x-api/fapi/beehive/public/v1/common/subscribe-info"
            params = {"leaderMark": leader_mark}

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                return None

            data = response.json()

            if data.get("retCode") != 0:
                return None

            return data.get("result", {})

        except Exception as e:
            logger.error(f"Error fetching Bybit subscribe info: {e}")
            return None

    def _parse_decimal(self, value, divisor: int = 1) -> Decimal:
        """Parse a value to Decimal, handling E4 format."""
        if value is None:
            return Decimal("0")
        try:
            result = Decimal(str(value))
            if divisor != 1:
                result = result / Decimal(str(divisor))
            return result
        except:
            return Decimal("0")

    def _parse_timestamp(self, value) -> datetime:
        """Parse timestamp (milliseconds or E3 format)."""
        if not value:
            return datetime.utcnow()
        try:
            # Handle E3 format (milliseconds * 1000) or regular milliseconds
            ts = int(value)
            if ts > 10**15:  # E3 format
                ts = ts // 1000
            if ts > 10**12:  # Milliseconds
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts)
        except:
            return datetime.utcnow()

    # ============= BROWSER-BASED METHODS (Playwright) =============

    async def fetch_leaderboard_browser(
        self,
        limit: int = 100,
    ) -> list[BybitMasterTrader]:
        """
        Fetch leaderboard using browser automation (bypasses Akamai).

        This method uses Playwright to:
        1. Navigate to the leaderboard page
        2. Intercept the API response
        3. Parse the trader data

        Requires: playwright package installed
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available - cannot use browser-based fetching")
            return []

        traders = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            # Storage for intercepted data
            leaderboard_data = []

            async def handle_response(response):
                if "trader-leaderboard" in response.url:
                    try:
                        data = await response.json()
                        if data.get("retCode") == 0:
                            leaderboard_data.append(data)
                    except:
                        pass

            page.on("response", handle_response)

            try:
                await page.goto(
                    "https://www.bybit.com/copyTrading/en/leaderboard-master",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                # Wait for data to load
                await page.wait_for_timeout(5000)

                # Parse intercepted data - Bybit updated their API structure
                for data in leaderboard_data:
                    result = data.get("result", {})
                    # New structure: topTraderList or typeTraderList instead of list
                    trader_list = result.get("topTraderList", [])
                    if not trader_list:
                        trader_list = result.get("typeTraderList", [])
                    if not trader_list:
                        trader_list = result.get("list", [])  # Fallback to old structure

                    for i, item in enumerate(trader_list):
                        if len(traders) >= limit:
                            break
                        try:
                            # Parse with both old and new field names
                            leader_mark = item.get("leaderMark", "")
                            nickname = item.get("leaderNickname", item.get("nickName", f"Bybit Trader #{i+1}"))

                            # PNL data from new API - traderPnlData is string
                            pnl_raw = item.get("traderPnlData", item.get("pnl", "0"))
                            pnl_7d = self._parse_decimal(pnl_raw)

                            # Followers profits
                            followers_profit = item.get("followersProfitsData", "0")

                            trader = BybitMasterTrader(
                                leader_mark=leader_mark,
                                nickname=nickname,
                                roi_7d=self._parse_decimal(item.get("roi", item.get("roiData", 0))),
                                roi_30d=self._parse_decimal(item.get("roiMonth", 0)),
                                pnl_7d=pnl_7d,
                                pnl_total=self._parse_decimal(item.get("totalPnl", pnl_raw)),
                                win_rate=self._parse_decimal(item.get("winRate", 0)) * 100,
                                followers_count=int(item.get("followerNum", item.get("followersCount", 0))),
                                aum=self._parse_decimal(item.get("aum", "0") or "0"),
                                trading_days=int(item.get("tradeDays", 0)),
                                stability_index=self._parse_decimal(item.get("stabilityIndex", 0)),
                                rank=int(item.get("ranking", len(traders) + 1)),
                            )
                            traders.append(trader)
                        except Exception as e:
                            logger.warning(f"Error parsing trader: {e}")

                logger.info(f"Browser: Fetched {len(traders)} traders from Bybit")

            except Exception as e:
                logger.error(f"Browser fetch error: {e}")
            finally:
                await browser.close()

        return traders

    async def fetch_positions_browser(
        self,
        leader_mark: str,
    ) -> list[BybitPosition]:
        """
        Fetch trader positions using browser automation.

        Args:
            leader_mark: The trader's unique identifier

        Returns:
            List of BybitPosition objects
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return []

        positions = []
        import urllib.parse
        encoded_mark = urllib.parse.quote(leader_mark, safe='')

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--single-process']
            )
            context = await browser.new_context()
            page = await context.new_page()

            position_data = []

            async def handle_response(response):
                if "position/list" in response.url:
                    try:
                        data = await response.json()
                        if data.get("retCode") == 0:
                            position_data.append(data)
                    except:
                        pass

            page.on("response", handle_response)

            try:
                url = f"https://www.bybit.com/copyTrade/trade-center/detail?leaderMark={encoded_mark}"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                for data in position_data:
                    result = data.get("result", {})
                    for item in result.get("list", []):
                        try:
                            position = BybitPosition(
                                symbol=item.get("symbol", ""),
                                side=item.get("side", ""),
                                size=self._parse_decimal(item.get("size", 0)),
                                entry_price=self._parse_decimal(item.get("entryPrice", 0)),
                                mark_price=self._parse_decimal(item.get("markPrice", 0)),
                                leverage=int(item.get("leverage", 1)),
                                unrealized_pnl=self._parse_decimal(item.get("unrealisedPnl", 0)),
                                created_time=self._parse_timestamp(item.get("createdAtE3", 0)),
                                updated_time=self._parse_timestamp(item.get("updatedAtE3", 0)),
                            )
                            positions.append(position)
                        except Exception as e:
                            logger.warning(f"Error parsing position: {e}")

            except Exception as e:
                logger.error(f"Browser position fetch error: {e}")
            finally:
                await browser.close()

        return positions


async def test_bybit_api():
    """Test the Bybit copy trading API."""
    service = BybitCopyTradingService()

    try:
        # Try direct HTTP first (will fail without proxy)
        print("Testing direct HTTP (likely to fail with 403)...")
        traders = await service.fetch_leaderboard(limit=5)

        if not traders:
            print("Direct HTTP blocked. Trying browser-based method...")
            if PLAYWRIGHT_AVAILABLE:
                traders = await service.fetch_leaderboard_browser(limit=10)
            else:
                print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
                return

        print(f"Found {len(traders)} traders")

        for trader in traders[:5]:
            print(f"  #{trader.rank} {trader.nickname}: ROI={trader.roi_7d}%, PnL=${trader.pnl_7d}, Followers={trader.followers_count}, AUM=${trader.aum}")

        # Test positions for first trader
        if traders and traders[0].leader_mark:
            print(f"\nFetching positions for {traders[0].nickname}...")

            # Try browser-based for positions too
            if PLAYWRIGHT_AVAILABLE:
                positions = await service.fetch_positions_browser(traders[0].leader_mark)
            else:
                positions = await service.fetch_trader_positions(traders[0].leader_mark)

            print(f"Found {len(positions)} positions")

            for pos in positions[:5]:
                side = "LONG" if pos.side == "Buy" else "SHORT"
                print(f"  {pos.symbol} {side} size={pos.size} @ {pos.entry_price} (lev: {pos.leverage}x, PnL: {pos.unrealized_pnl})")

    finally:
        await service.close()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_bybit_api())
