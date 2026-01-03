"""
Exchange Integration Module
"""

from app.services.exchanges.base import BaseExchange, OrderResult, Balance, Position as ExchangePosition
from app.services.exchanges.binance_executor import BinanceExecutor
from app.services.exchanges.okx_executor import OKXExecutor
from app.services.exchanges.bybit_executor import BybitExecutor

__all__ = [
    "BaseExchange",
    "OrderResult",
    "Balance",
    "ExchangePosition",
    "BinanceExecutor",
    "OKXExecutor",
    "BybitExecutor",
]


def get_exchange_executor(
    exchange_name: str,
    api_key: str,
    api_secret: str,
    passphrase: str | None = None,
    testnet: bool = False,
) -> BaseExchange:
    """
    Factory function to get the appropriate exchange executor.

    Args:
        exchange_name: Name of the exchange (binance, okx, bybit)
        api_key: API key
        api_secret: API secret
        passphrase: API passphrase (OKX only)
        testnet: Use testnet/sandbox mode

    Returns:
        Exchange executor instance
    """
    exchange_name = exchange_name.lower()

    if exchange_name == "binance":
        return BinanceExecutor(api_key, api_secret, testnet=testnet)
    elif exchange_name == "okx":
        return OKXExecutor(api_key, api_secret, passphrase or "", testnet=testnet)
    elif exchange_name == "bybit":
        return BybitExecutor(api_key, api_secret, testnet=testnet)
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")
