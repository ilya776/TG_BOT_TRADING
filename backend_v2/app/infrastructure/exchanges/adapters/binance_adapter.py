"""Binance Exchange Adapter - implements ExchangePort interface.

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


class BinanceAdapter(ExchangePort):
    """Binance exchange adapter з retry logic та circuit breaker.

    Example:
        >>> adapter = BinanceAdapter(
        ...     api_key="your_api_key",
        ...     api_secret="your_secret",
        ...     testnet=True
        ... )
        >>> await adapter.initialize()
        >>> 
        >>> # Execute trade з автоматичним retry
        >>> result = await adapter.execute_spot_buy("BTCUSDT", Decimal("0.001"))
        >>> print(result.order_id)  # "12345"
        >>> 
        >>> await adapter.close()
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        enable_rate_limit: bool = True,
    ) -> None:
        """Initialize Binance adapter.

        Args:
            api_key: Binance API key.
            api_secret: Binance API secret.
            testnet: Use testnet (default: False).
            enable_rate_limit: Enable CCXT rate limiting (default: True).
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # Initialize CCXT client
        self._client = ccxt.binance(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": enable_rate_limit,
                "options": {
                    "defaultType": "spot",  # Default to spot trading
                    "adjustForTimeDifference": True,  # Auto-sync time
                },
            }
        )

        if testnet:
            self._client.set_sandbox_mode(True)
            logger.info("binance.testnet_enabled")

    async def initialize(self) -> None:
        """Initialize Binance connection."""
        try:
            # Load markets
            await self._client.load_markets()
            logger.info(
                "binance.initialized",
                extra={"markets_count": len(self._client.markets), "testnet": self.testnet},
            )
        except Exception as e:
            logger.error("binance.initialization_failed", extra={"error": str(e)})
            raise ExchangeConnectionError(f"Failed to initialize Binance: {e}") from e

    async def close(self) -> None:
        """Close Binance connection."""
        await self._client.close()
        logger.info("binance.closed")

    # --- SPOT TRADING ---

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_spot_buy(self, symbol: str, quantity: Decimal) -> OrderResult:
        """Execute spot market buy order.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").
            quantity: Quantity to buy in base currency.

        Returns:
            OrderResult з execution details.

        Raises:
            InsufficientBalanceError: Not enough USDT.
            ExchangeAPIError: Binance API error.
            RateLimitError: Rate limit exceeded (triggers retry).
        """
        try:
            logger.info(
                "binance.spot_buy.start",
                extra={"symbol": symbol, "quantity": str(quantity)},
            )

            # CCXT create_market_buy_order
            order = await self._client.create_market_buy_order(
                symbol=symbol,
                amount=float(quantity),
            )

            # Normalize to OrderResult
            result = self._normalize_order_result(order, symbol)

            logger.info(
                "binance.spot_buy.success",
                extra={
                    "symbol": symbol,
                    "order_id": result.order_id,
                    "filled_quantity": str(result.filled_quantity),
                    "avg_price": str(result.avg_fill_price),
                },
            )

            return result

        except ccxt.InsufficientFunds as e:
            logger.warning("binance.insufficient_funds", extra={"symbol": symbol, "error": str(e)})
            raise InsufficientBalanceError(f"Insufficient USDT balance: {e}") from e

        except ccxt.RateLimitExceeded as e:
            logger.warning("binance.rate_limit", extra={"symbol": symbol})
            raise RetryableError(f"Binance rate limit exceeded: {e}") from e

        except ccxt.NetworkError as e:
            logger.warning("binance.network_error", extra={"symbol": symbol, "error": str(e)})
            raise RetryableError(f"Binance network error: {e}") from e

        except Exception as e:
            logger.error("binance.spot_buy.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Binance API error: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_spot_sell(self, symbol: str, quantity: Decimal) -> OrderResult:
        """Execute spot market sell order."""
        try:
            logger.info(
                "binance.spot_sell.start",
                extra={"symbol": symbol, "quantity": str(quantity)},
            )

            order = await self._client.create_market_sell_order(
                symbol=symbol,
                amount=float(quantity),
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "binance.spot_sell.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient balance to sell: {e}") from e

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Binance rate limit exceeded: {e}") from e

        except ccxt.NetworkError as e:
            raise RetryableError(f"Binance network error: {e}") from e

        except Exception as e:
            logger.error("binance.spot_sell.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Binance API error: {e}") from e

    # --- FUTURES TRADING ---

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_futures_long(
        self, symbol: str, quantity: Decimal, leverage: int
    ) -> OrderResult:
        """Open futures long position."""
        try:
            # Switch to futures mode
            self._client.options["defaultType"] = "future"

            # Set leverage
            await self._client.fapiPrivate_post_leverage(
                {"symbol": symbol.replace("/", ""), "leverage": leverage}
            )

            logger.info(
                "binance.futures_long.start",
                extra={"symbol": symbol, "quantity": str(quantity), "leverage": leverage},
            )

            # Open long position
            order = await self._client.create_market_buy_order(
                symbol=symbol,
                amount=float(quantity),
                params={"positionSide": "LONG"},
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "binance.futures_long.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient margin: {e}") from e

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Binance rate limit exceeded: {e}") from e

        except ccxt.BadRequest as e:
            if "leverage" in str(e).lower():
                raise InvalidLeverageError(f"Invalid leverage for {symbol}: {e}") from e
            raise ExchangeAPIError(f"Binance API error: {e}") from e

        except Exception as e:
            logger.error("binance.futures_long.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Binance API error: {e}") from e

        finally:
            # Switch back to spot
            self._client.options["defaultType"] = "spot"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def execute_futures_short(
        self, symbol: str, quantity: Decimal, leverage: int
    ) -> OrderResult:
        """Open futures short position."""
        try:
            self._client.options["defaultType"] = "future"

            # Set leverage
            await self._client.fapiPrivate_post_leverage(
                {"symbol": symbol.replace("/", ""), "leverage": leverage}
            )

            logger.info(
                "binance.futures_short.start",
                extra={"symbol": symbol, "quantity": str(quantity), "leverage": leverage},
            )

            # Open short position (sell to short)
            order = await self._client.create_market_sell_order(
                symbol=symbol,
                amount=float(quantity),
                params={"positionSide": "SHORT"},
            )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "binance.futures_short.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(f"Insufficient margin: {e}") from e

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Binance rate limit exceeded: {e}") from e

        except ccxt.BadRequest as e:
            if "leverage" in str(e).lower():
                raise InvalidLeverageError(f"Invalid leverage for {symbol}: {e}") from e
            raise ExchangeAPIError(f"Binance API error: {e}") from e

        except Exception as e:
            logger.error("binance.futures_short.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Binance API error: {e}") from e

        finally:
            self._client.options["defaultType"] = "spot"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker_protected(failure_threshold=5, timeout_seconds=60)
    async def close_futures_position(self, symbol: str, position_side: str) -> OrderResult:
        """Close futures position."""
        try:
            self._client.options["defaultType"] = "future"

            logger.info(
                "binance.close_position.start",
                extra={"symbol": symbol, "position_side": position_side},
            )

            # Get current position size
            positions = await self._client.fapiPrivate_get_positionrisk(
                {"symbol": symbol.replace("/", "")}
            )

            position = next(
                (p for p in positions if p["positionSide"] == position_side.upper()), None
            )

            if not position or float(position["positionAmt"]) == 0:
                raise PositionNotFoundError(f"No {position_side} position found for {symbol}")

            position_amt = abs(float(position["positionAmt"]))

            # Close position (reverse order)
            if position_side.upper() == "LONG":
                # Close long = sell
                order = await self._client.create_market_sell_order(
                    symbol=symbol,
                    amount=position_amt,
                    params={"positionSide": "LONG", "reduceOnly": True},
                )
            else:
                # Close short = buy
                order = await self._client.create_market_buy_order(
                    symbol=symbol,
                    amount=position_amt,
                    params={"positionSide": "SHORT", "reduceOnly": True},
                )

            result = self._normalize_order_result(order, symbol)

            logger.info(
                "binance.close_position.success",
                extra={"symbol": symbol, "order_id": result.order_id},
            )

            return result

        except PositionNotFoundError:
            raise

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Binance rate limit exceeded: {e}") from e

        except Exception as e:
            logger.error("binance.close_position.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Binance API error: {e}") from e

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
                if float(amounts) > 0:  # Фільтруємо нульові баланси
                    balances.append(
                        Balance(
                            asset=asset,
                            free=Decimal(str(balance_response["free"].get(asset, 0))),
                            locked=Decimal(str(balance_response["used"].get(asset, 0))),
                        )
                    )

            logger.info(
                "binance.balances.fetched",
                extra={"balances_count": len(balances)},
            )

            return balances

        except ccxt.RateLimitExceeded as e:
            raise RetryableError(f"Binance rate limit exceeded: {e}") from e

        except Exception as e:
            logger.error("binance.balances.failed", extra={"error": str(e)})
            raise ExchangeAPIError(f"Binance API error: {e}") from e

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
            logger.error("binance.symbol_info.failed", extra={"symbol": symbol, "error": str(e)})
            raise ExchangeAPIError(f"Failed to get symbol info: {e}") from e

    # --- PRIVATE HELPERS ---

    def _normalize_order_result(self, order: dict[str, Any], symbol: str) -> OrderResult:
        """Normalize CCXT order response to OrderResult value object.

        Args:
            order: Raw CCXT order response.
            symbol: Trading pair.

        Returns:
            Normalized OrderResult.
        """
        # Map CCXT status to our OrderStatus
        status_map = {
            "closed": OrderStatus.FILLED,
            "open": OrderStatus.PARTIALLY_FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }

        status = status_map.get(order.get("status", "closed"), OrderStatus.FILLED)

        # Extract fee (може бути в різних форматах)
        fee_amount = Decimal("0")
        if order.get("fee"):
            fee_amount = Decimal(str(order["fee"].get("cost", 0)))
        elif order.get("fees"):
            # Сума всіх fees
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
