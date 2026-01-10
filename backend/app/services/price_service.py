"""
Real-time Price Service
Fetches current prices from exchanges for PnL calculation.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Optional
import httpx
import redis
import json
import os

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PRICE_CACHE_TTL = 10  # Cache prices for 10 seconds


class PriceService:
    """
    Fetches real-time prices from exchanges.
    Uses Redis for caching to reduce API calls.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self._redis = redis.from_url(REDIS_URL, decode_responses=True)

    async def close(self):
        await self.client.aclose()

    async def get_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get current price for a symbol.
        Checks cache first, then fetches from exchange.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")

        Returns:
            Current price or None if not available
        """
        # Normalize symbol
        symbol = symbol.upper().replace("-", "").replace("_", "")
        if not symbol.endswith("USDT") and not symbol.endswith("USD"):
            symbol = f"{symbol}USDT"

        # Check cache
        cache_key = f"price:{symbol}"
        cached = self._redis.get(cache_key)
        if cached:
            try:
                return Decimal(cached)
            except:
                pass

        # Fetch from Binance (fastest, most reliable)
        price = await self._fetch_binance_price(symbol)

        # Fallback to OKX if Binance fails
        if price is None:
            price = await self._fetch_okx_price(symbol)

        # Cache the result
        if price:
            self._redis.setex(cache_key, PRICE_CACHE_TTL, str(price))

        return price

    async def get_prices_batch(self, symbols: list[str]) -> dict[str, Decimal]:
        """
        Get prices for multiple symbols efficiently.

        Returns dict mapping symbol -> price
        """
        results = {}
        uncached = []

        # Check cache first
        for symbol in symbols:
            symbol = symbol.upper().replace("-", "").replace("_", "")
            if not symbol.endswith("USDT") and not symbol.endswith("USD"):
                symbol = f"{symbol}USDT"

            cache_key = f"price:{symbol}"
            cached = self._redis.get(cache_key)
            if cached:
                try:
                    results[symbol] = Decimal(cached)
                except:
                    uncached.append(symbol)
            else:
                uncached.append(symbol)

        # Fetch uncached prices in parallel
        if uncached:
            tasks = [self.get_price(s) for s in uncached]
            prices = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, price in zip(uncached, prices):
                if isinstance(price, Decimal):
                    results[symbol] = price

        return results

    async def _fetch_binance_price(self, symbol: str) -> Optional[Decimal]:
        """Fetch price from Binance Futures API."""
        try:
            url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()
                return Decimal(str(data.get("price", 0)))

        except Exception as e:
            logger.debug(f"Binance price fetch failed for {symbol}: {e}")

        return None

    async def _fetch_okx_price(self, symbol: str) -> Optional[Decimal]:
        """Fetch price from OKX API."""
        try:
            # Convert symbol format: BTCUSDT -> BTC-USDT-SWAP
            base = symbol.replace("USDT", "").replace("USD", "")
            inst_id = f"{base}-USDT-SWAP"

            url = f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}"
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()
                tickers = data.get("data", [])
                if tickers:
                    return Decimal(str(tickers[0].get("last", 0)))

        except Exception as e:
            logger.debug(f"OKX price fetch failed for {symbol}: {e}")

        return None


# Singleton instance
_price_service: Optional[PriceService] = None


def get_price_service() -> PriceService:
    """Get singleton PriceService instance."""
    global _price_service
    if _price_service is None:
        _price_service = PriceService()
    return _price_service


async def get_current_price(symbol: str) -> Optional[Decimal]:
    """Convenience function to get current price."""
    service = get_price_service()
    return await service.get_price(symbol)


async def get_current_prices(symbols: list[str]) -> dict[str, Decimal]:
    """Convenience function to get multiple prices."""
    service = get_price_service()
    return await service.get_prices_batch(symbols)
