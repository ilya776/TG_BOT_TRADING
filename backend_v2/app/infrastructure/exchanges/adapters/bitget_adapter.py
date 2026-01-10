"""Bitget Exchange Adapter - implements ExchangePort interface.

Використовує CCXT для unified API access.
Включає retry logic та circuit breaker protection.
"""

import logging
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt

from app.domain.exchanges.exceptions import (
    AssetNotFoundError,
    ExchangeAPIError,
    ExchangeConnectionError,
    InsufficientBalanceError,
    InvalidLeverageError,
    PositionNotFoundError,
    RateLimitError,
)
from app.domain.exchanges.ports import ExchangePort
from app.domain.exchanges.value_objects import Balance, OrderResult, OrderStatus
from app.infrastructure.exchanges.circuit_breakers import circuit_breaker_protected
from app.infrastructure.exchanges.retry import RetryableError, retry_with_backoff

logger = logging.getLogger(__name__)


class BitgetAdapter(ExchangePort):
    """Bitget exchange adapter з retry logic та circuit breaker.

    Example:
        >>> adapter = BitgetAdapter(
        ...     api_key="your_api_key",
        ...     api_secret="your_secret",
        ...     passphrase="your_passphrase",
        ...     testnet=True
        ... )
        >>> await adapter.initialize()
        >>> result = await adapter.execute_spot_buy("BTCUSDT", Decimal("0.001"))
        >>> await adapter.close()
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        testnet: bool = False,
        enable_rate_limit: bool = True,
    ) -> None:
        """Initialize Bitget adapter.

        Args:
            api_key: Bitget API key.
            api_secret: Bitget API secret.
            passphrase: Bitget API passphrase (required by Bitget).
            testnet: Use testnet (default: False).
            enable_rate_limit: Enable CCXT rate limiting (default: True).
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.testnet = testnet

        # Initialize CCXT client
        self._client = ccxt.bitget(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "password": passphrase,  # Bitget requires passphrase
                "enableRateLimit": enable_rate_limit,
                "options": {
                    "defaultType": "spot",
                },
            }
        )

        if testnet:
            self._client.set_sandbox_mode(True)
            logger.info("bitget.testnet_enabled")

    async def initialize(self) -> None:
        """Initialize Bitget connection."""
        try:
            await self._client.load_markets()
            logger.info(
                "bitget.initialized",
                extra={"markets_count": len(self._client.markets), "testnet": self.testnet},
            )
        except Exception as e:
            logger.error("bitget.initialization_failed", extra={"error": str(e)})
            raise ExchangeConnectionError(f"Failed to initialize Bitget: {e}") from e

    async def close(self) -> None:
        """Close Bitget connection."""
        await self._client.close()
        logger.info("bitget.closed")

    # --- SPOT TRADING ---

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_spot_buy(self, symbol: str, quantity: Decimal) -> OrderResult:
        """Execute spot market buy order."""
        try:
            logger.info(
                "bitget.spot_buy.start",
                extra={"symbol": symbol, "quantity": str(quantity)},
            )

            order = await self._client.create_market_buy_order(
                symbol=symbol,
                amount=float(quantity),
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "bitget.spot_buy.success",
                extra={
                    "symbol": symbol,
                    "order_id": result.order_id,
                    "filled_quantity": str(result.filled_quantity),
                },
            )

            return result

        except ccxt.InsufficientFunds as e:
            logger.warning("bitget.insufficient_funds", extra={"symbol": symbol})
            raise InsufficientBalanceError(f"Insufficient USDT balance: {e}") from e

        except ccxt.RateLimitExceeded as e:
            logger.warning("bitget.rate_limit", extra={"symbol": symbol})
            raise RetryableError(f"Bitget rate limit exceeded: {e}") from e

        except ccxt.NetworkError as e:
            logger.warning("bitget.network_error", extra={"symbol": symbol})
            raise RetryableError(f"Bitget network error: {e}") from e

        except Exception as e:
            logger.error("bitget.spot_buy.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_spot_sell(self, symbol: str, quantity: Decimal) -> OrderResult:
        """Execute spot market sell order."""
        try:
            logger.info(
                "bitget.spot_sell.start",
                extra={"symbol": symbol, "quantity": str(quantity)},
            )

            order = await self._client.create_market_sell_order(
                symbol=symbol,
                amount=float(quantity),
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "bitget.spot_sell.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient balance to sell: {e}") from e

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Bitget rate limit exceeded: {e}") from e

        except ccxt.NetworkError as e:
            raise RetryableError(f"Bitget network error: {e}") from e

        except Exception as e:
            logger.error("bitget.spot_sell.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

    # --- FUTURES TRADING ---

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_futures_long(
        self, symbol: str, quantity: Decimal, leverage: int
    ) -> OrderResult:
        """Open futures long position."""
        try:
            # Switch to futures (USDT-M)
            self._client.options["defaultType"] = "swap"

            # Set leverage
            await self._client.set_leverage(leverage, symbol)

            logger.info(
                "bitget.futures_long.start",
                extra={"symbol": symbol, "quantity": str(quantity), "leverage": leverage},
            )

            # Open long position
            order = await self._client.create_market_buy_order(
                symbol=symbol,
                amount=float(quantity),
                params={"holdSide": "long"},  # Bitget hedge mode
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "bitget.futures_long.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient margin: {e}") from e

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Bitget rate limit exceeded: {e}") from e

        except ccxt.BadRequest as e:
            if "leverage" in str(e).lower():
                raise InvalidLeverageError(f"Invalid leverage for {symbol}: {e}") from e
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

        except Exception as e:
            logger.error("bitget.futures_long.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

        finally:
            self._client.options["defaultType"] = "spot"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_futures_short(
        self, symbol: str, quantity: Decimal, leverage: int
    ) -> OrderResult:
        """Open futures short position."""
        try:
            self._client.options["defaultType"] = "swap"

            await self._client.set_leverage(leverage, symbol)

            logger.info(
                "bitget.futures_short.start",
                extra={"symbol": symbol, "quantity": str(quantity), "leverage": leverage},
            )

            # Open short position
            order = await self._client.create_market_sell_order(
                symbol=symbol,
                amount=float(quantity),
                params={"holdSide": "short"},
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "bitget.futures_short.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient margin: {e}") from e

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Bitget rate limit exceeded: {e}") from e

        except ccxt.BadRequest as e:
            if "leverage" in str(e).lower():
                raise InvalidLeverageError(f"Invalid leverage for {symbol}: {e}") from e
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

        except Exception as e:
            logger.error("bitget.futures_short.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

        finally:
            self._client.options["defaultType"] = "spot"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def close_futures_position(self, symbol: str, position_side: str) -> OrderResult:
        """Close futures position."""
        try:
            self._client.options["defaultType"] = "swap"

            logger.info(
                "bitget.close_position.start",
                extra={"symbol": symbol, "position_side": position_side},
            )

            # Get current position
            positions = await self._client.fetch_positions([symbol])
            
            hold_side = position_side.lower()
            position = next(
                (p for p in positions if p["info"].get("holdSide") == hold_side), 
                None
            )

            if not position or float(position["contracts"]) == 0:
                raise PositionNotFoundError(f"No {position_side} position found for {symbol}")

            position_size = abs(float(position["contracts"]))

            # Close position (reverse order)
            if position_side.upper() == "LONG":
                order = await self._client.create_market_sell_order(
                    symbol=symbol,
                    amount=position_size,
                    params={"holdSide": "long", "reduceOnly": True},
                )
            else:
                order = await self._client.create_market_buy_order(
                    symbol=symbol,
                    amount=position_size,
                    params={"holdSide": "short", "reduceOnly": True},
                )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "bitget.close_position.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except PositionNotFoundError:
            raise

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Bitget rate limit exceeded: {e}") from e

        except Exception as e:
            logger.error("bitget.close_position.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

        finally:
            self._client.options["defaultType"] = "spot"

    # --- BALANCE & ACCOUNT ---

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def get_balances(self) -> list[Balance]:
        """Get all account balances."""
        try:
            balance_response = await self._client.fetch_balance()

            balances = []
            for asset, amounts in balance_response.get("total", {}).items():
                if float(amounts) > 0:
                    balances.append(
                        Balance(
                            asset=asset,
                            free=Decimal(str(balance_response["free"].get(asset, 0))),
                            locked=Decimal(str(balance_response["used"].get(asset, 0))),
                        )
                    )

            logger.info(
                "bitget.balances.fetched",
                extra={"balances_count": len(balances)},
            )

            return balances

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Bitget rate limit exceeded: {e}") from e

        except Exception as e:
            logger.error("bitget.balances.failed", extra={"error": str(e)})
            raise ExchangeAPIError(f"Bitget API error: {e}") from e

    async def get_balance(self, asset: str) -> Balance:
        """Get balance for specific asset."""
        balances = await self.get_balances()

        balance = next((b for b in balances if b.asset == asset), None)

        if balance is None:
            raise AssetNotFoundError(f"Asset {asset} not found in balances")

        return balance

    # --- SYMBOL INFO ---

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Get trading rules for symbol."""
        try:
            market = self._client.market(symbol)

            return {
                "symbol": symbol,
                "base_asset": market["base"],
                "quote_asset": market["quote"],
                "min_quantity": Decimal(str(market["limits"]["amount"]["min"] or 0)),
                "max_quantity": Decimal(str(market["limits"]["amount"]["max"] or 0)),
                "min_notional": Decimal(str(market["limits"]["cost"]["min"] or 0)),
                "price_precision": market["precision"]["price"],
                "quantity_precision": market["precision"]["amount"],
            }

        except Exception as e:
            logger.error("bitget.symbol_info.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Failed to get symbol info: {e}") from e

    # --- PRIVATE HELPERS ---

    def _normalize_order_result(self, order: dict[str, Any], symbol: str) -> OrderResult:
        """Normalize CCXT order response to OrderResult value object."""
        status_map = {
            "closed": OrderStatus.FILLED,
            "open": OrderStatus.PARTIALLY_FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }

        status = status_map.get(order.get("status", "closed"), OrderStatus.FILLED)

        fee_amount = Decimal("0")
        if order.get("fee"):
            fee_amount = Decimal(str(order["fee"].get("cost", 0)))
        elif order.get("fees"):
            fee_amount = sum(Decimal(str(f.get("cost", 0))) for f in order["fees"])

        return OrderResult(
            order_id=str(order["id"]),
            status=status,
            symbol=symbol,
            filled_quantity=Decimal(str(order.get("filled", 0))),
            avg_fill_price=Decimal(str(order.get("average") or order.get("price", 0))),
            total_cost=Decimal(str(order.get("cost", 0))),
            fee_amount=fee_amount,
            fee_currency=order.get("fee", {}).get("currency", "USDT"),
        )
