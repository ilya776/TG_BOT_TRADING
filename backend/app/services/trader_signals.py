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
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
import redis
from sqlalchemy import select

from app.database import get_db_context
from app.models.signal import SignalAction, SignalConfidence, SignalStatus, WhaleSignal
from app.models.whale import Whale

logger = logging.getLogger(__name__)

# Redis client for persistent position cache
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for position caching."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


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
        )


class TraderSignalService:
    """
    Monitors top traders on Binance/Bybit and generates signals
    when they open or close positions.
    """

    CACHE_PREFIX = "trader_positions:"
    CACHE_TTL = 300  # 5 minutes - positions older than this are considered stale

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
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

    async def close(self):
        await self.client.aclose()

    async def fetch_binance_trader_positions(self, encrypted_uid: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Binance trader.
        Uses the public position history API.
        """
        positions = []

        try:
            url = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getOtherPosition"

            payload = {
                "encryptedUid": encrypted_uid,
                "tradeType": "PERPETUAL"
            }

            response = await self.client.post(url, json=payload)

            if response.status_code == 429:
                # Rate limited - wait and don't return empty (caller should retry later)
                logger.warning(f"Binance positions API rate limited (429) - backing off")
                await asyncio.sleep(5)  # Extra delay on rate limit
                return positions

            if response.status_code != 200:
                logger.warning(f"Binance positions API returned {response.status_code}")
                return positions

            try:
                data = response.json()
            except Exception:
                logger.warning(f"Failed to parse Binance positions response")
                return positions

            if not data.get("success"):
                return positions

            # Handle None values - some traders have position sharing disabled
            data_obj = data.get("data") or {}
            position_list = data_obj.get("otherPositionRetList")
            if position_list is None:
                # Trader has position sharing disabled
                return positions

            for item in position_list:
                try:
                    position = TraderPosition(
                        symbol=item.get("symbol", ""),
                        side="LONG" if item.get("amount", 0) > 0 else "SHORT",
                        entry_price=Decimal(str(item.get("entryPrice", 0))),
                        mark_price=Decimal(str(item.get("markPrice", 0))),
                        size=abs(Decimal(str(item.get("amount", 0)))),
                        pnl=Decimal(str(item.get("pnl", 0))),
                        roe=Decimal(str(item.get("roe", 0))) * 100,  # Convert to percentage
                        leverage=int(item.get("leverage", 1)),
                        update_time=datetime.fromtimestamp(item.get("updateTimeStamp", 0) / 1000) if item.get("updateTimeStamp") else datetime.utcnow()
                    )
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Error parsing Binance position: {e}")

            if positions:
                logger.info(f"Fetched {len(positions)} positions for Binance trader {encrypted_uid[:8]}...")
            else:
                logger.debug(f"No positions for Binance trader {encrypted_uid[:8]}... (sharing may be disabled)")

        except Exception as e:
            logger.error(f"Error fetching Binance trader positions: {e}")

        return positions

    async def fetch_bybit_trader_positions(self, leader_mark: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Bybit copy trading leader.
        Uses V5 API.
        """
        positions = []

        try:
            # New V5 API endpoint
            url = "https://api.bybit.com/v5/copy-trading/public/leader/positions"

            params = {
                "leaderMark": leader_mark,
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                logger.debug(f"Bybit positions API returned {response.status_code}")
                return positions

            data = response.json()
            result = data.get("result", {})
            position_list = result.get("list", []) if isinstance(result, dict) else []

            for item in position_list:
                try:
                    # Handle different field names
                    size_val = item.get("size", item.get("qty", "0"))
                    position = TraderPosition(
                        symbol=item.get("symbol", ""),
                        side=item.get("side", "Buy").upper().replace("BUY", "LONG").replace("SELL", "SHORT"),
                        entry_price=Decimal(str(item.get("avgEntryPrice", item.get("entryPrice", 0)))),
                        mark_price=Decimal(str(item.get("markPrice", 0))),
                        size=Decimal(str(size_val)),
                        pnl=Decimal(str(item.get("unrealisedPnl", 0))),
                        roe=Decimal(str(item.get("cumRealisedPnl", 0))),
                        leverage=int(float(item.get("leverage", 1))),
                        update_time=datetime.utcnow()
                    )
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Error parsing Bybit position: {e}")

            if positions:
                logger.info(f"Fetched {len(positions)} positions for Bybit trader {leader_mark[:8]}...")

        except Exception as e:
            logger.error(f"Error fetching Bybit trader positions: {e}")

        return positions

    async def fetch_bitget_trader_positions(self, trader_uid: str) -> list[TraderPosition]:
        """
        Fetch current positions for a Bitget copy trading master.
        Bitget copy traders ALWAYS share positions publicly.
        """
        positions = []

        try:
            url = "https://api.bitget.com/api/mix/v1/copytrade/public/trader/current-track"

            params = {
                "traderUid": trader_uid,
                "pageNo": "1",
                "pageSize": "50"
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                logger.debug(f"Bitget positions API returned {response.status_code}")
                return positions

            data = response.json()
            position_list = data.get("data", {}).get("list", [])

            for item in position_list:
                try:
                    # Bitget uses 'holdSide' for position side
                    side = item.get("holdSide", "long").upper()
                    if side not in ["LONG", "SHORT"]:
                        side = "LONG" if "long" in side.lower() else "SHORT"

                    position = TraderPosition(
                        symbol=item.get("symbol", "").upper(),
                        side=side,
                        entry_price=Decimal(str(item.get("openPriceAvg", item.get("averageOpenPrice", 0)))),
                        mark_price=Decimal(str(item.get("marketPrice", 0))),
                        size=Decimal(str(item.get("total", item.get("holdAmount", 0)))),
                        pnl=Decimal(str(item.get("unrealizedPL", 0))),
                        roe=Decimal(str(item.get("achievedProfits", 0))) * 100,
                        leverage=int(float(item.get("leverage", 1))),
                        update_time=datetime.utcnow()
                    )
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Error parsing Bitget position: {e}")

            if positions:
                logger.info(f"Fetched {len(positions)} positions for Bitget trader {trader_uid[:8]}...")

        except Exception as e:
            logger.error(f"Error fetching Bitget trader positions: {e}")

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

    async def check_and_generate_signals(self, max_traders: int = 20) -> int:
        """
        Check top traders for position changes and generate signals.
        Only checks a limited number of traders per run to avoid rate limits.
        Returns number of signals generated.
        """
        signals_generated = 0

        async with get_db_context() as db:
            # Get top active whales that are exchange traders (sorted by score)
            result = await db.execute(
                select(Whale).where(
                    Whale.is_active == True,
                    Whale.wallet_address.like("binance_%") |
                    Whale.wallet_address.like("bybit_%") |
                    Whale.wallet_address.like("bitget_%")
                ).order_by(Whale.score.desc()).limit(max_traders)
            )
            whales = result.scalars().all()

            logger.info(f"Checking top {len(whales)} exchange traders for position changes")

            traders_with_positions = 0
            total_positions = 0

            for whale in whales:
                try:
                    # Determine exchange and UID
                    parts = whale.wallet_address.split("_", 1)
                    if len(parts) != 2:
                        continue

                    exchange, uid = parts

                    # Fetch current positions
                    if exchange == "binance":
                        current_positions = await self.fetch_binance_trader_positions(uid)
                    elif exchange == "bybit":
                        current_positions = await self.fetch_bybit_trader_positions(uid)
                    elif exchange == "bitget":
                        current_positions = await self.fetch_bitget_trader_positions(uid)
                    else:
                        continue

                    # Get previous positions from Redis cache
                    cache_key = whale.wallet_address
                    previous_positions = self._get_cached_positions(cache_key)

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

                    # Delay to avoid rate limits (1.5 seconds between traders)
                    # With 20 traders, this gives ~30s per full cycle, runs every 60s
                    await asyncio.sleep(1.5)

                except Exception as e:
                    logger.error(f"Error checking trader {whale.name}: {e}")

            await db.commit()

            logger.info(
                f"Signal generation complete: "
                f"{traders_with_positions}/{len(whales)} traders with open positions, "
                f"{total_positions} total positions, "
                f"{signals_generated} signals generated"
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
                dex=whale.wallet_address.split("_")[0].upper(),  # BINANCE or BYBIT
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
                confidence=self._determine_confidence(position, whale.score or 50),
                confidence_score=self._calculate_confidence_score(position, whale.score or 50),
                status=SignalStatus.PENDING,
                detected_at=now,
                tx_timestamp=position.update_time,
            )

            db.add(signal)
            await db.flush()

            return signal

        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return None


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
