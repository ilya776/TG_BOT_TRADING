"""
Bitget Copy Trading Service
Fetches master traders and their positions from Bitget's copy trading API.

NOTE: Bitget uses Cloudflare protection. This service supports:
1. Direct HTTP - for API endpoints (may fail if Cloudflare active)
2. FlareSolverr - Cloudflare bypass proxy (recommended)
3. Playwright - Browser automation (fallback)

FlareSolverr is the recommended method as it handles Cloudflare challenges automatically.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# FlareSolverr URL (running as Docker service)
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1")

# Try to import Playwright (optional dependency)
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Bitget browser-based fetching disabled")


@dataclass
class BitgetMasterTrader:
    """Represents a Bitget copy trading master trader."""
    uid: str
    nickname: str
    roi_7d: Decimal
    roi_30d: Decimal
    roi_total: Decimal
    pnl_7d: Decimal
    pnl_total: Decimal
    win_rate: Decimal
    followers_count: int
    total_trades: int
    rank: int


@dataclass
class BitgetPosition:
    """Represents a position held by a Bitget master trader."""
    symbol: str
    side: str  # "long" or "short"
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: int
    unrealized_pnl: Decimal
    margin_mode: str  # "cross" or "isolated"


class BitgetCopyTradingService:
    """
    Service to fetch copy trading data from Bitget.

    Bitget API Endpoints:
    - Official API: https://api.bitget.com/api/mix/v1/trace/traderList
    - Web API: https://www.bitget.com/v1/trigger/trace/public/traderRank

    Both may be protected by Cloudflare. Use browser method as fallback.
    """

    BASE_URL = "https://www.bitget.com"
    API_URL = "https://api.bitget.com"

    def __init__(self):
        # Stealth headers to avoid Cloudflare blocking
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.bitget.com",
                "Referer": "https://www.bitget.com/copy-trading/futures",
                "Content-Type": "application/json",
            }
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _parse_decimal(self, value, divisor: int = 1) -> Decimal:
        """Safely parse a value to Decimal."""
        try:
            if value is None:
                return Decimal("0")
            result = Decimal(str(value)) / Decimal(str(divisor))
            return result
        except:
            return Decimal("0")

    async def fetch_leaderboard(self, limit: int = 100) -> list[BitgetMasterTrader]:
        """
        Fetch leaderboard via new Web API (v1 API is decommissioned).
        Uses POST to www.bitget.com/v1/trigger/trace/public/topTraders
        May fail with 403 if Cloudflare protection is active.
        """
        traders = []

        try:
            # New endpoint - the old api.bitget.com/api/mix/v1/trace/traderList is decommissioned
            url = f"{self.BASE_URL}/v1/trigger/trace/public/topTraders"
            payload = {
                "pageNo": 1,
                "pageSize": min(limit, 100),
                "languageType": 0,  # 0 = English
            }

            response = await self.client.post(url, json=payload)

            if response.status_code == 403:
                logger.warning("Bitget API returned 403 - Cloudflare protection active")
                return traders

            if response.status_code != 200:
                logger.warning(f"Bitget API returned {response.status_code}")
                return traders

            data = response.json()

            # Check for API errors
            if data.get("code") and data.get("code") != "00000":
                logger.warning(f"Bitget API error: {data.get('msg')}")
                return traders

            # New API format: data.rows[].showColumnValue[] contains traders
            rows = data.get("data", {}).get("rows", [])
            seen_uids = set()
            rank = 0

            for row in rows:
                # Each row is a category (e.g., "trader_pro", "profit_rate")
                trader_list = row.get("showColumnValue", [])
                for item in trader_list:
                    # Extract UID from headPic URL or generate from displayName
                    uid = item.get("traderUid", "")
                    if not uid:
                        # Try to extract from profile URL or use displayName hash
                        uid = str(hash(item.get("displayName", "")))[:12]

                    if uid in seen_uids:
                        continue
                    seen_uids.add(uid)

                    rank += 1
                    trader = self._parse_trader_v2(item, rank)
                    if trader:
                        traders.append(trader)

                    if len(traders) >= limit:
                        break
                if len(traders) >= limit:
                    break

            logger.info(f"Fetched {len(traders)} traders from Bitget API")

        except Exception as e:
            logger.error(f"Error fetching Bitget leaderboard: {e}")

        return traders

    async def fetch_leaderboard_flaresolverr(self, limit: int = 100) -> list[BitgetMasterTrader]:
        """
        Fetch leaderboard using FlareSolverr to bypass Cloudflare.

        FlareSolverr is a proxy that solves Cloudflare challenges.
        Uses POST to the new www.bitget.com endpoint.
        """
        traders = []

        try:
            # FlareSolverr request payload - use POST with JSON body
            post_data = json.dumps({
                "pageNo": 1,
                "pageSize": min(limit, 100),
                "languageType": 0,
            })

            payload = {
                "cmd": "request.post",
                "url": "https://www.bitget.com/v1/trigger/trace/public/topTraders",
                "postData": post_data,
                "maxTimeout": 60000,
            }

            async with httpx.AsyncClient(timeout=90.0) as client:
                logger.info("Requesting Bitget data via FlareSolverr (POST)...")
                response = await client.post(FLARESOLVERR_URL, json=payload)

                if response.status_code != 200:
                    logger.warning(f"FlareSolverr returned {response.status_code}")
                    return traders

                result = response.json()

                if result.get("status") != "ok":
                    logger.warning(f"FlareSolverr error: {result.get('message')}")
                    return traders

                # Parse the response body
                solution = result.get("solution", {})
                body = solution.get("response", "")

                # Response might be wrapped in HTML, try to extract JSON
                if body.startswith("<"):
                    # Extract JSON from HTML wrapper
                    import re
                    json_match = re.search(r'\{.*\}', body, re.DOTALL)
                    if json_match:
                        body = json_match.group()

                # Try to parse as JSON (API response)
                try:
                    data = json.loads(body)

                    # Check for API errors
                    if data.get("code") and data.get("code") != "00000":
                        logger.warning(f"Bitget API error via FlareSolverr: {data.get('msg')}")
                        return traders

                    raw_list = data.get("data", [])
                    trader_list = raw_list.get("list", raw_list) if isinstance(raw_list, dict) else raw_list

                    for i, item in enumerate(trader_list[:limit]):
                        trader = self._parse_trader(item, i + 1)
                        if trader:
                            traders.append(trader)

                    logger.info(f"Fetched {len(traders)} traders from Bitget via FlareSolverr")

                except json.JSONDecodeError:
                    logger.warning(f"FlareSolverr response is not JSON: {body[:200]}")

        except Exception as e:
            logger.error(f"Error fetching Bitget leaderboard via FlareSolverr: {e}")

        return traders

    async def fetch_leaderboard_browser(self, limit: int = 100) -> list[BitgetMasterTrader]:
        """
        Fetch leaderboard using browser automation (bypasses Cloudflare).

        This method uses Playwright to:
        1. Navigate to the copy trading leaderboard page
        2. Intercept the API responses
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
                    '--single-process',
                    '--disable-gpu',
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Storage for intercepted data
            leaderboard_data = []

            async def handle_response(response):
                """Intercept API responses."""
                url = response.url
                if any(keyword in url for keyword in ["topTraders", "traderList", "traderRank", "trader-rank"]):
                    try:
                        data = await response.json()
                        leaderboard_data.append(data)
                        logger.debug(f"Intercepted Bitget data from: {url}")
                    except:
                        pass

            page.on("response", handle_response)

            try:
                # Navigate to copy trading leaderboard
                await page.goto(
                    "https://www.bitget.com/copy-trading/trader-ranking",
                    wait_until="networkidle",
                    timeout=45000,
                )

                # Wait for data to load
                await page.wait_for_timeout(5000)

                # Try scrolling to trigger more data loads
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 500)")
                    await page.wait_for_timeout(1000)

                # Parse intercepted data
                for data in leaderboard_data:
                    # Handle different response structures
                    if isinstance(data, dict):
                        raw_list = data.get("data", data.get("result", []))
                        if isinstance(raw_list, dict):
                            raw_list = raw_list.get("list", raw_list.get("traders", []))

                        if isinstance(raw_list, list):
                            for i, item in enumerate(raw_list):
                                if len(traders) >= limit:
                                    break
                                trader = self._parse_trader(item, len(traders) + 1)
                                if trader and trader.uid not in [t.uid for t in traders]:
                                    traders.append(trader)

                logger.info(f"Fetched {len(traders)} traders from Bitget via browser")

            except Exception as e:
                logger.error(f"Browser leaderboard fetch error: {e}")
            finally:
                await browser.close()

        return traders

    def _parse_trader(self, item: dict, rank: int) -> Optional[BitgetMasterTrader]:
        """Parse trader data from API response."""
        try:
            # Handle various field name formats
            uid = str(item.get("uid", item.get("traderUid", item.get("traderId", ""))))
            if not uid:
                return None

            nickname = item.get("nickName", item.get("traderName", f"Bitget Trader #{rank}"))

            # Parse ROI values
            roi_7d_raw = item.get("roi", item.get("weekRoi", item.get("roiWeek", 0)))
            roi_30d_raw = item.get("monthRoi", item.get("roiMonth", roi_7d_raw))
            roi_total_raw = item.get("totalRoi", 0)

            # Convert ROI - Bitget can return as decimal (0.15) or percentage (15.5)
            roi_7d = self._parse_decimal(roi_7d_raw)
            roi_30d = self._parse_decimal(roi_30d_raw)
            roi_total = self._parse_decimal(roi_total_raw)

            # If values look like decimals, convert to percentage
            if abs(roi_7d) < Decimal("1.0") and roi_7d != 0:
                roi_7d *= 100
            if abs(roi_30d) < Decimal("1.0") and roi_30d != 0:
                roi_30d *= 100
            if abs(roi_total) < Decimal("1.0") and roi_total != 0:
                roi_total *= 100

            # Parse win rate
            win_rate_raw = item.get("winRate", item.get("winRatio", 0))
            win_rate = self._parse_decimal(win_rate_raw)
            if win_rate <= 1:
                win_rate *= 100

            return BitgetMasterTrader(
                uid=uid,
                nickname=nickname,
                roi_7d=roi_7d,
                roi_30d=roi_30d,
                roi_total=roi_total,
                pnl_7d=self._parse_decimal(item.get("weekPnl", item.get("pnlWeek", 0))),
                pnl_total=self._parse_decimal(item.get("totalPnl", item.get("totalPL", 0))),
                win_rate=win_rate,
                followers_count=int(item.get("followerCount", item.get("copyCount", 0))),
                total_trades=int(item.get("totalTrade", item.get("tradeCount", 0))),
                rank=rank,
            )
        except Exception as e:
            logger.warning(f"Error parsing Bitget trader: {e}")
            return None

    def _parse_trader_v2(self, item: dict, rank: int) -> Optional[BitgetMasterTrader]:
        """Parse trader data from new API format (v2 topTraders endpoint)."""
        try:
            # Extract UID - try multiple sources
            uid = item.get("traderUid", "")
            if not uid:
                # Generate from displayName if no UID available
                display_name = item.get("displayName", f"Trader{rank}")
                uid = str(abs(hash(display_name)))[:12]

            nickname = item.get("displayName", f"Bitget Trader #{rank}")

            # Parse metrics from itemVoList
            roi_30d = Decimal("0")
            win_rate = Decimal("0")

            for metric in item.get("itemVoList", []):
                code = metric.get("showColumnCode", "")
                value = metric.get("comparedValue", "0")

                if code == "profit_rate":
                    roi_30d = self._parse_decimal(value)
                elif code == "win_rate":
                    win_rate = self._parse_decimal(value)

            followers_count = int(item.get("followCount", 0))

            return BitgetMasterTrader(
                uid=uid,
                nickname=nickname,
                roi_7d=Decimal("0"),  # Not available in this endpoint
                roi_30d=roi_30d,
                roi_total=Decimal("0"),  # Not available
                pnl_7d=Decimal("0"),
                pnl_total=Decimal("0"),
                win_rate=win_rate,
                followers_count=followers_count,
                total_trades=0,  # Not available
                rank=rank,
            )
        except Exception as e:
            logger.warning(f"Error parsing Bitget trader v2: {e}")
            return None

    async def fetch_trader_positions_browser(self, uid: str) -> list[BitgetPosition]:
        """
        Fetch positions for a specific trader using browser.
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return []

        positions = []

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
                    '--single-process',
                    '--disable-gpu',
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            position_data = []

            async def handle_response(response):
                url = response.url
                if "position" in url.lower() or "currentTrack" in url:
                    try:
                        data = await response.json()
                        position_data.append(data)
                    except:
                        pass

            page.on("response", handle_response)

            try:
                # Navigate to trader profile
                url = f"https://www.bitget.com/copy-trading/trader/{uid}"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                # Parse positions from intercepted data
                for data in position_data:
                    if isinstance(data, dict):
                        pos_list = data.get("data", data.get("result", []))
                        if isinstance(pos_list, dict):
                            pos_list = pos_list.get("list", [])

                        for item in pos_list if isinstance(pos_list, list) else []:
                            try:
                                position = BitgetPosition(
                                    symbol=item.get("symbol", ""),
                                    side=item.get("holdSide", item.get("side", "")).lower(),
                                    size=self._parse_decimal(item.get("holdVol", item.get("size", 0))),
                                    entry_price=self._parse_decimal(item.get("openAvgPrice", item.get("entryPrice", 0))),
                                    mark_price=self._parse_decimal(item.get("markPrice", 0)),
                                    leverage=int(item.get("leverage", 1)),
                                    unrealized_pnl=self._parse_decimal(item.get("unrealizedPL", item.get("unrealisedPnl", 0))),
                                    margin_mode=item.get("marginMode", "cross"),
                                )
                                positions.append(position)
                            except Exception as e:
                                logger.warning(f"Error parsing Bitget position: {e}")

            except Exception as e:
                logger.error(f"Browser position fetch error: {e}")
            finally:
                await browser.close()

        return positions


async def test_bitget_api():
    """Test the Bitget API."""
    logging.basicConfig(level=logging.INFO)

    service = BitgetCopyTradingService()

    try:
        print("Testing direct API...")
        traders = await service.fetch_leaderboard(limit=10)

        if not traders and PLAYWRIGHT_AVAILABLE:
            print("Direct API failed, trying browser method...")
            traders = await service.fetch_leaderboard_browser(limit=10)
        elif not traders:
            print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
            return

        print(f"Found {len(traders)} traders")

        for trader in traders[:5]:
            print(f"  #{trader.rank} {trader.nickname}: ROI={trader.roi_7d}%, Followers={trader.followers_count}")

    finally:
        await service.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_bitget_api())
