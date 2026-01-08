"""
Exchange Leaderboard Service
Fetches real top traders from exchange leaderboards (Binance, Bybit, OKX)
"""

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import get_db_context
from app.models.whale import Whale, WhaleChain, WhaleStats

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class TopTrader:
    """Represents a top trader from exchange leaderboard."""

    uid: str  # Exchange-specific user ID
    nickname: str
    exchange: str
    roi_7d: Decimal
    roi_30d: Decimal
    roi_90d: Decimal
    pnl_7d: Decimal
    pnl_30d: Decimal
    pnl_total: Decimal
    win_rate: Decimal
    total_trades: int
    followers_count: int
    rank: int


class ExchangeLeaderboardService:
    """
    Fetches top traders from exchange leaderboards.

    Supported exchanges:
    - Binance Futures Leaderboard
    - Bybit Copy Trading Leaderboard
    - OKX Copy Trading
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    async def close(self):
        await self.client.aclose()

    async def fetch_all_top_traders(self, limit: int = 100) -> list[TopTrader]:
        """Fetch top traders from all supported exchanges."""
        all_traders = []

        # Fetch from each exchange in parallel
        # Note: Bitget V2 API requires authentication, so we only use Binance and OKX
        results = await asyncio.gather(
            self.fetch_binance_leaderboard(limit=limit),
            self.fetch_okx_copy_traders(limit=limit),
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching leaderboard: {result}")
            else:
                all_traders.extend(result)

        # Sort by ROI and return top performers
        all_traders.sort(key=lambda x: x.roi_7d, reverse=True)
        return all_traders[:limit]

    async def fetch_binance_leaderboard(self, limit: int = 50) -> list[TopTrader]:
        """
        Fetch Binance Futures leaderboard.
        Uses the public leaderboard API.
        """
        traders = []

        try:
            # Binance Futures Leaderboard API
            url = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getLeaderboardRank"

            payload = {
                "isShared": True,
                "isTrader": True,
                "periodType": "WEEKLY",
                "statisticsType": "ROI",
                "tradeType": "PERPETUAL"
            }

            response = await self.client.post(url, json=payload)

            if response.status_code != 200:
                logger.warning(f"Binance leaderboard API returned {response.status_code}")
                return traders

            data = response.json()
            rank_list = data.get("data", [])

            for i, item in enumerate(rank_list[:limit]):
                try:
                    # API returns "value" field which is ROI multiplier (e.g., 3.5 = 350% ROI)
                    roi_value = Decimal(str(item.get("value", 0))) * 100  # Convert to percentage

                    trader = TopTrader(
                        uid=str(item.get("encryptedUid", "")),
                        nickname=item.get("nickName", f"Binance Trader #{i+1}"),
                        exchange="BINANCE",
                        roi_7d=roi_value,
                        roi_30d=roi_value,  # Same as 7d for now
                        roi_90d=Decimal("0"),
                        pnl_7d=Decimal(str(item.get("pnl", 0))),
                        pnl_30d=Decimal("0"),
                        pnl_total=Decimal("0"),
                        win_rate=Decimal("0"),  # Not available in basic response
                        total_trades=0,
                        followers_count=int(item.get("followerCount", 0)),
                        rank=int(item.get("rank", i + 1))  # Use actual rank from API
                    )
                    traders.append(trader)
                except Exception as e:
                    logger.warning(f"Error parsing Binance trader: {e}")

            logger.info(f"Fetched {len(traders)} traders from Binance leaderboard")

        except Exception as e:
            logger.error(f"Error fetching Binance leaderboard: {e}")

        return traders

    async def fetch_binance_trader_details(self, encrypted_uid: str) -> dict | None:
        """Fetch detailed stats for a specific Binance trader."""
        try:
            url = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getOtherPerformance"

            payload = {
                "encryptedUid": encrypted_uid,
                "tradeType": "PERPETUAL"
            }

            response = await self.client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})

        except Exception as e:
            logger.error(f"Error fetching Binance trader details: {e}")

        return None

    async def fetch_okx_copy_traders(self, limit: int = 50) -> list[TopTrader]:
        """
        Fetch OKX copy trading master traders.
        Uses the public copy trading API.
        """
        traders = []

        try:
            # OKX Copy Trading public API - working endpoint
            url = "https://www.okx.com/api/v5/copytrading/public-lead-traders"

            response = await self.client.get(url)

            if response.status_code != 200:
                logger.warning(f"OKX copy trading API returned {response.status_code}")
                return traders

            data = response.json()
            # OKX structure: data[0].ranks[] contains the traders
            raw_data = data.get("data", [])
            if raw_data and isinstance(raw_data, list) and len(raw_data) > 0:
                trader_list = raw_data[0].get("ranks", [])
            else:
                trader_list = []

            for i, item in enumerate(trader_list[:limit]):
                try:
                    # OKX returns ROI as decimal string (1.3259 = 132.59%)
                    roi_raw = Decimal(str(item.get("pnlRatio", 0)))
                    roi_7d = roi_raw * 100  # Convert to percentage

                    win_rate_raw = item.get("winRatio", 0)
                    win_rate = Decimal(str(win_rate_raw)) * 100  # Convert to percentage

                    trader = TopTrader(
                        uid=str(item.get("uniqueCode", "")),
                        nickname=item.get("nickName", f"OKX Master #{i+1}"),
                        exchange="OKX",
                        roi_7d=roi_7d,
                        roi_30d=roi_7d,  # Use same as 7d
                        roi_90d=roi_7d,  # Use same
                        pnl_7d=Decimal(str(item.get("pnl", 0))),
                        pnl_30d=Decimal(str(item.get("pnl", 0))),
                        pnl_total=Decimal(str(item.get("pnl", 0))),
                        win_rate=win_rate,
                        total_trades=int(item.get("leadDays", 0)) * 5,  # Estimate from days
                        followers_count=int(item.get("copyTraderNum", item.get("accCopyTraderNum", 0))),
                        rank=i + 1
                    )
                    traders.append(trader)
                except Exception as e:
                    logger.warning(f"Error parsing OKX trader: {e}")

            logger.info(f"Fetched {len(traders)} traders from OKX copy trading")

        except Exception as e:
            logger.error(f"Error fetching OKX copy traders: {e}")

        return traders

    async def fetch_bitget_copy_traders(self, limit: int = 50) -> list[TopTrader]:
        """
        Fetch Bitget copy trading master traders.
        These traders ALWAYS share positions publicly.
        """
        traders = []

        try:
            # Bitget Copy Trading public API - traderList endpoint
            url = "https://api.bitget.com/api/mix/v1/trace/traderList"

            params = {
                "sortRule": "roi",  # Sort by ROI (options: composite, roi, totalPL, aum)
                "sortFlag": "desc",  # Descending order
                "fullStatus": "all",  # All traders
                "languageType": "en-US"
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Bitget copy trading API returned {response.status_code}")
                return traders

            data = response.json()
            # Handle both list directly or nested under "list"
            raw_list = data.get("data", [])
            trader_list = raw_list.get("list", raw_list) if isinstance(raw_list, dict) else raw_list

            for i, item in enumerate(trader_list[:limit]):
                try:
                    # Bitget returns ROI - handle various field names from different endpoints
                    # traderList uses: roi, weekRoi, monthRoi
                    roi_7d_raw = item.get("roi", item.get("weekRoi", item.get("roiWeek", 0)))
                    roi_30d_raw = item.get("monthRoi", item.get("roiMonth", roi_7d_raw))

                    # Convert ROI - Bitget API returns ROI as percentage (15.5 = 15.5%)
                    # Only convert if clearly in decimal format (< 1.0 means fraction like 0.15)
                    roi_7d = Decimal(str(roi_7d_raw))
                    if abs(roi_7d) < Decimal("1.0") and roi_7d != 0:
                        # Definitely decimal format (0.15 = 15%)
                        roi_7d = roi_7d * 100
                        logger.debug(f"Bitget ROI converted from decimal: {roi_7d_raw} -> {roi_7d}%")

                    roi_30d = Decimal(str(roi_30d_raw))
                    if abs(roi_30d) < Decimal("1.0") and roi_30d != 0:
                        roi_30d = roi_30d * 100

                    win_rate_raw = item.get("winRate", item.get("winRatio", 0))
                    win_rate = Decimal(str(win_rate_raw)) * 100 if float(win_rate_raw) <= 1 else Decimal(str(win_rate_raw))

                    trader = TopTrader(
                        uid=str(item.get("uid", item.get("traderUid", item.get("traderId", "")))),
                        nickname=item.get("nickName", item.get("traderName", f"Bitget Master #{i+1}")),
                        exchange="BITGET",
                        roi_7d=roi_7d,
                        roi_30d=roi_30d,
                        roi_90d=Decimal(str(item.get("totalRoi", 0))) * 100 if abs(float(item.get("totalRoi", 0))) < 1.0 else Decimal(str(item.get("totalRoi", 0))),
                        pnl_7d=Decimal(str(item.get("weekPnl", item.get("pnlWeek", item.get("totalPL", 0))))),
                        pnl_30d=Decimal(str(item.get("monthPnl", 0))),
                        pnl_total=Decimal(str(item.get("totalPnl", item.get("totalPL", 0)))),
                        win_rate=win_rate,
                        total_trades=int(item.get("totalTrade", item.get("tradeCount", item.get("orderNum", 0)))),
                        followers_count=int(item.get("followerCount", item.get("copyCount", item.get("copyTradeNum", 0)))),
                        rank=i + 1
                    )
                    traders.append(trader)
                except Exception as e:
                    logger.warning(f"Error parsing Bitget trader: {e}")

            logger.info(f"Fetched {len(traders)} traders from Bitget copy trading")

        except Exception as e:
            logger.error(f"Error fetching Bitget copy traders: {e}")

        return traders

    async def sync_to_database(self, traders: list[TopTrader]) -> int:
        """
        Sync top traders to database as whales.
        Creates new whales or updates existing ones.
        """
        synced_count = 0

        async with get_db_context() as db:
            for trader in traders:
                try:
                    # Generate a unique wallet address for exchange traders
                    # Format: exchange_uid (used for identification)
                    wallet_address = f"{trader.exchange.lower()}_{trader.uid}"

                    # Check if whale exists
                    result = await db.execute(
                        select(Whale).where(Whale.wallet_address == wallet_address)
                    )
                    existing_whale = result.scalar_one_or_none()

                    # Calculate score based on ROI (0-100 scale)
                    # Higher ROI = higher score, capped at 100
                    roi_score = min(100, max(0, int(50 + float(trader.roi_7d) * 2)))

                    # Estimate win_rate from ROI (rough approximation)
                    # Positive ROI suggests win_rate > 50%
                    estimated_win_rate = min(Decimal("85"), max(Decimal("45"),
                        Decimal("55") + trader.roi_7d / Decimal("5")))

                    if existing_whale:
                        # Update existing whale
                        existing_whale.name = trader.nickname
                        existing_whale.tags = f"{trader.exchange},TOP_TRADER,LEADERBOARD"
                        existing_whale.score = roi_score
                        whale_id = existing_whale.id
                    else:
                        # Create new whale
                        whale = Whale(
                            wallet_address=wallet_address,
                            name=trader.nickname,
                            chain=WhaleChain.ETHEREUM,  # Default, not relevant for CEX traders
                            is_active=True,
                            is_public=True,
                            score=roi_score,
                            tags=f"{trader.exchange},TOP_TRADER,LEADERBOARD",
                        )
                        db.add(whale)
                        await db.flush()
                        whale_id = whale.id

                    # Update or create whale stats
                    stats_result = await db.execute(
                        select(WhaleStats).where(WhaleStats.whale_id == whale_id)
                    )
                    existing_stats = stats_result.scalar_one_or_none()

                    # Estimate total_trades from followers (more followers = more experienced)
                    estimated_trades = max(50, trader.followers_count * 2 + trader.rank * 3)

                    if existing_stats:
                        existing_stats.win_rate = estimated_win_rate
                        existing_stats.profit_7d = trader.pnl_7d
                        existing_stats.profit_30d = trader.pnl_30d if trader.pnl_30d else trader.pnl_7d * 3
                        existing_stats.profit_90d = trader.roi_90d if trader.roi_90d else trader.roi_7d * 2
                        existing_stats.total_profit_usd = trader.pnl_total if trader.pnl_total else trader.pnl_7d * 10
                        existing_stats.total_trades = trader.total_trades if trader.total_trades else estimated_trades
                        existing_stats.avg_profit_percent = trader.roi_7d
                    else:
                        stats = WhaleStats(
                            whale_id=whale_id,
                            win_rate=estimated_win_rate,
                            profit_7d=trader.pnl_7d,
                            profit_30d=trader.pnl_30d if trader.pnl_30d else trader.pnl_7d * 3,
                            profit_90d=trader.roi_90d if trader.roi_90d else trader.roi_7d * 2,
                            total_profit_usd=trader.pnl_total if trader.pnl_total else trader.pnl_7d * 10,
                            total_trades=trader.total_trades if trader.total_trades else estimated_trades,
                            avg_profit_percent=trader.roi_7d,
                        )
                        db.add(stats)

                    synced_count += 1

                except Exception as e:
                    logger.error(f"Error syncing trader {trader.nickname}: {e}")

            await db.commit()

        logger.info(f"Synced {synced_count} traders to database")
        return synced_count


async def sync_exchange_leaderboards():
    """
    Main function to sync exchange leaderboards to database.
    Should be called periodically (e.g., every 5 minutes).
    """
    service = ExchangeLeaderboardService()

    try:
        # Fetch top traders from all exchanges
        traders = await service.fetch_all_top_traders(limit=100)

        # Sync to database
        synced = await service.sync_to_database(traders)

        logger.info(f"Leaderboard sync complete: {synced} traders updated")
        return synced

    except Exception as e:
        logger.error(f"Leaderboard sync failed: {e}")
        return 0

    finally:
        await service.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(sync_exchange_leaderboards())
