"""
Exchange Integration Module
"""

from app.services.exchanges.base import BaseExchange, OrderResult, Balance, Position as ExchangePosition, PositionSide
from app.services.exchanges.binance_executor import BinanceExecutor
from app.services.exchanges.okx_executor import OKXExecutor
from app.services.exchanges.bybit_executor import BybitExecutor
from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    get_circuit_breaker,
    check_circuit,
)

__all__ = [
    "BaseExchange",
    "OrderResult",
    "Balance",
    "ExchangePosition",
    "PositionSide",
    "BinanceExecutor",
    "OKXExecutor",
    "BybitExecutor",
    "CircuitOpenError",
    "get_circuit_breaker",
    "check_circuit",
]


def get_exchange_executor(
    exchange_name: str,
    api_key: str,
    api_secret: str,
    passphrase: str | None = None,
    testnet: bool = False,
    check_circuit_breaker: bool = True,
) -> BaseExchange:
    """
    Factory function to get the appropriate exchange executor.

    Args:
        exchange_name: Name of the exchange (binance, okx, bybit)
        api_key: API key
        api_secret: API secret
        passphrase: API passphrase (OKX only)
        testnet: Use testnet/sandbox mode
        check_circuit_breaker: If True, check circuit breaker before returning

    Returns:
        Exchange executor instance

    Raises:
        CircuitOpenError: If circuit breaker is open for this exchange
        ValueError: If exchange is not supported
    """
    exchange_name = exchange_name.lower()

    # Check circuit breaker before creating executor
    if check_circuit_breaker:
        breaker = get_circuit_breaker(exchange_name)
        if not breaker.can_execute():
            raise CircuitOpenError(
                exchange_name,
                breaker.get_time_remaining()
            )

    if exchange_name == "binance":
        executor = BinanceExecutor(api_key, api_secret, testnet=testnet)
    elif exchange_name == "okx":
        executor = OKXExecutor(api_key, api_secret, passphrase or "", testnet=testnet)
    elif exchange_name == "bybit":
        executor = BybitExecutor(api_key, api_secret, testnet=testnet)
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")

    # Attach circuit breaker to executor for recording success/failure
    executor._circuit_breaker = get_circuit_breaker(exchange_name)
    return executor
