"""
Binance Exchange Integration
Supports both Spot and Futures (USDT-M) trading
"""

import asyncio
import time
from decimal import Decimal
from typing import Any

from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException

from app.services.exchanges.base import (
    Balance,
    BaseExchange,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
)


class BinanceExecutor(BaseExchange):
    """Binance exchange executor for spot and futures trading."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
    ):
        super().__init__(api_key, api_secret, testnet)
        self._client: AsyncClient | None = None
        self._symbol_info_cache: dict[str, dict] = {}
        self._futures_symbol_info_cache: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "binance"

    async def initialize(self) -> None:
        """Initialize Binance async client."""
        self._client = await AsyncClient.create(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet,
        )
        # Pre-cache exchange info
        await self._load_exchange_info()

    async def _load_exchange_info(self) -> None:
        """Load and cache exchange symbol information."""
        if not self._client:
            return

        try:
            # Spot exchange info
            spot_info = await self._client.get_exchange_info()
            for symbol_info in spot_info.get("symbols", []):
                self._symbol_info_cache[symbol_info["symbol"]] = symbol_info

            # Futures exchange info
            futures_info = await self._client.futures_exchange_info()
            for symbol_info in futures_info.get("symbols", []):
                self._futures_symbol_info_cache[symbol_info["symbol"]] = symbol_info
        except Exception:
            pass  # Non-critical, will be loaded on demand

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.close_connection()
            self._client = None

    def _ensure_client(self) -> AsyncClient:
        """Ensure client is initialized."""
        if not self._client:
            raise RuntimeError("Binance client not initialized. Call initialize() first.")
        return self._client

    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse Binance order status to our enum."""
        status_map = {
            "NEW": OrderStatus.NEW,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
            "PENDING_CANCEL": OrderStatus.PENDING,
        }
        return status_map.get(status, OrderStatus.NEW)

    def _parse_order_result(self, response: dict[str, Any], is_futures: bool = False) -> OrderResult:
        """Parse Binance order response to OrderResult."""
        # Handle fills for fee calculation
        fills = response.get("fills", [])
        total_fee = Decimal("0")
        fee_currency = None
        if fills:
            for fill in fills:
                total_fee += Decimal(str(fill.get("commission", 0)))
                fee_currency = fill.get("commissionAsset")

        # Calculate average fill price
        avg_price = None
        if response.get("avgPrice"):
            avg_price = Decimal(str(response["avgPrice"]))
        elif response.get("cummulativeQuoteQty") and response.get("executedQty"):
            cum_quote = Decimal(str(response["cummulativeQuoteQty"]))
            exec_qty = Decimal(str(response["executedQty"]))
            if exec_qty > 0:
                avg_price = cum_quote / exec_qty

        return OrderResult(
            order_id=str(response.get("orderId", "")),
            client_order_id=response.get("clientOrderId"),
            symbol=response.get("symbol", ""),
            side=OrderSide.BUY if response.get("side") == "BUY" else OrderSide.SELL,
            order_type=OrderType(response.get("type", "MARKET")),
            status=self._parse_order_status(response.get("status", "NEW")),
            quantity=Decimal(str(response.get("origQty", 0))),
            filled_quantity=Decimal(str(response.get("executedQty", 0))),
            price=Decimal(str(response["price"])) if response.get("price") else None,
            avg_fill_price=avg_price,
            fee=total_fee,
            fee_currency=fee_currency,
            timestamp=response.get("transactTime", response.get("updateTime", int(time.time() * 1000))),
            raw_response=response,
        )

    # ==================== ACCOUNT ====================

    async def get_account_balance(self) -> list[Balance]:
        """Get all spot account balances."""
        client = self._ensure_client()
        account = await client.get_account()

        balances = []
        for b in account.get("balances", []):
            free = Decimal(str(b.get("free", 0)))
            locked = Decimal(str(b.get("locked", 0)))
            total = free + locked

            if total > 0:  # Only include non-zero balances
                balances.append(
                    Balance(
                        asset=b["asset"],
                        free=free,
                        locked=locked,
                        total=total,
                    )
                )

        return balances

    async def get_asset_balance(self, asset: str) -> Balance | None:
        """Get balance for a specific asset."""
        client = self._ensure_client()
        balance = await client.get_asset_balance(asset=asset.upper())

        if not balance:
            return None

        free = Decimal(str(balance.get("free", 0)))
        locked = Decimal(str(balance.get("locked", 0)))

        return Balance(
            asset=balance["asset"],
            free=free,
            locked=locked,
            total=free + locked,
        )

    async def get_futures_balance(self) -> list[Balance]:
        """Get futures account balances."""
        client = self._ensure_client()
        account = await client.futures_account_balance()

        balances = []
        for b in account:
            balance = Decimal(str(b.get("balance", 0)))
            if balance > 0:
                balances.append(
                    Balance(
                        asset=b["asset"],
                        free=Decimal(str(b.get("availableBalance", 0))),
                        locked=balance - Decimal(str(b.get("availableBalance", 0))),
                        total=balance,
                    )
                )

        return balances

    async def transfer_spot_to_futures(self, amount: Decimal, asset: str = "USDT") -> bool:
        """Transfer funds from spot to USDT-M futures wallet.

        Args:
            amount: Amount to transfer
            asset: Asset to transfer (default USDT)

        Returns:
            True if successful, raises on error
        """
        client = self._ensure_client()

        try:
            # Type 1: Spot to USDT-M Futures
            await client.futures_account_transfer(
                asset=asset,
                amount=str(amount),
                type=1,  # 1 = Spot to USDT-M Futures
            )
            return True
        except BinanceAPIException as e:
            raise RuntimeError(f"Transfer to futures failed: {e.message}") from e

    async def transfer_futures_to_spot(self, amount: Decimal, asset: str = "USDT") -> bool:
        """Transfer funds from USDT-M futures to spot wallet.

        Args:
            amount: Amount to transfer
            asset: Asset to transfer (default USDT)

        Returns:
            True if successful, raises on error
        """
        client = self._ensure_client()

        try:
            # Type 2: USDT-M Futures to Spot
            await client.futures_account_transfer(
                asset=asset,
                amount=str(amount),
                type=2,  # 2 = USDT-M Futures to Spot
            )
            return True
        except BinanceAPIException as e:
            raise RuntimeError(f"Transfer to spot failed: {e.message}") from e

    # ==================== SPOT TRADING ====================

    async def spot_market_buy(
        self,
        symbol: str,
        quantity: Decimal,
        quote_order_qty: Decimal | None = None,
    ) -> OrderResult:
        """Execute spot market buy."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            if quote_order_qty:
                # Buy with specific USDT amount
                response = await client.order_market_buy(
                    symbol=symbol,
                    quoteOrderQty=str(quote_order_qty),
                )
            else:
                response = await client.order_market_buy(
                    symbol=symbol,
                    quantity=str(self.round_quantity(symbol, quantity)),
                )
            return self._parse_order_result(response)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance spot buy failed: {e.message}") from e

    async def spot_market_sell(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Execute spot market sell."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.order_market_sell(
                symbol=symbol,
                quantity=str(self.round_quantity(symbol, quantity)),
            )
            return self._parse_order_result(response)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance spot sell failed: {e.message}") from e

    async def spot_limit_buy(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
    ) -> OrderResult:
        """Execute spot limit buy."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.order_limit_buy(
                symbol=symbol,
                quantity=str(self.round_quantity(symbol, quantity)),
                price=str(self.round_price(symbol, price)),
            )
            return self._parse_order_result(response)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance limit buy failed: {e.message}") from e

    async def spot_limit_sell(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
    ) -> OrderResult:
        """Execute spot limit sell."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.order_limit_sell(
                symbol=symbol,
                quantity=str(self.round_quantity(symbol, quantity)),
                price=str(self.round_price(symbol, price)),
            )
            return self._parse_order_result(response)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance limit sell failed: {e.message}") from e

    # ==================== FUTURES TRADING ====================

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a futures symbol."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            await client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage,
            )
            return True
        except BinanceAPIException as e:
            if "No need to change leverage" in str(e):
                return True  # Already at desired leverage
            raise RuntimeError(f"Failed to set leverage: {e.message}") from e

    async def get_leverage(self, symbol: str) -> int:
        """Get current leverage for a symbol."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            positions = await client.futures_position_information(symbol=symbol)
            if positions:
                return int(positions[0].get("leverage", 1))
            return 1
        except BinanceAPIException:
            return 1

    async def futures_market_long(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Open a long position with market order."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.futures_create_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quantity=str(self.round_quantity(symbol, quantity, is_futures=True)),
            )
            # Re-query order to get fill data (create response may be incomplete)
            order_id = response.get("orderId")
            if order_id:
                await asyncio.sleep(0.2)  # Brief pause for order to fill
                response = await client.futures_get_order(symbol=symbol, orderId=order_id)
            return self._parse_order_result(response, is_futures=True)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance futures long failed: {e.message}") from e

    async def futures_market_short(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Open a short position with market order."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.futures_create_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=str(self.round_quantity(symbol, quantity, is_futures=True)),
            )
            # Re-query order to get fill data (create response may be incomplete)
            order_id = response.get("orderId")
            if order_id:
                await asyncio.sleep(0.2)  # Brief pause for order to fill
                response = await client.futures_get_order(symbol=symbol, orderId=order_id)
            return self._parse_order_result(response, is_futures=True)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance futures short failed: {e.message}") from e

    async def futures_close_position(
        self,
        symbol: str,
        position_side: PositionSide,
        quantity: Decimal | None = None,
    ) -> OrderResult:
        """Close a futures position."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        # Get current position if quantity not specified
        if quantity is None:
            positions = await self.get_open_positions(symbol)
            for pos in positions:
                if pos.side == position_side or (
                    position_side == PositionSide.LONG and pos.quantity > 0
                ) or (
                    position_side == PositionSide.SHORT and pos.quantity < 0
                ):
                    quantity = abs(pos.quantity)
                    break

            if quantity is None:
                raise RuntimeError(f"No open {position_side.value} position found for {symbol}")

        # Close by opening opposite position
        side = "SELL" if position_side == PositionSide.LONG else "BUY"

        try:
            response = await client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=str(self.round_quantity(symbol, quantity, is_futures=True)),
                reduceOnly=True,
            )
            return self._parse_order_result(response, is_futures=True)
        except BinanceAPIException as e:
            raise RuntimeError(f"Binance close position failed: {e.message}") from e

    async def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        """Get open futures positions."""
        client = self._ensure_client()

        try:
            if symbol:
                positions = await client.futures_position_information(
                    symbol=self.normalize_symbol(symbol)
                )
            else:
                positions = await client.futures_position_information()

            result = []
            for pos in positions:
                qty = Decimal(str(pos.get("positionAmt", 0)))
                if qty == 0:
                    continue  # Skip empty positions

                side = PositionSide.LONG if qty > 0 else PositionSide.SHORT

                result.append(
                    Position(
                        symbol=pos["symbol"],
                        side=side,
                        quantity=abs(qty),
                        entry_price=Decimal(str(pos.get("entryPrice", 0))),
                        mark_price=Decimal(str(pos.get("markPrice", 0))),
                        unrealized_pnl=Decimal(str(pos.get("unRealizedProfit", 0))),
                        leverage=int(pos.get("leverage", 1)),
                        liquidation_price=Decimal(str(pos["liquidationPrice"])) if pos.get("liquidationPrice") else None,
                        margin_type=pos.get("marginType", "cross"),
                        timestamp=int(pos.get("updateTime", time.time() * 1000)),
                    )
                )

            return result
        except BinanceAPIException as e:
            raise RuntimeError(f"Failed to get positions: {e.message}") from e

    # ==================== ORDERS ====================

    async def get_order(self, symbol: str, order_id: str) -> OrderResult | None:
        """Get order details by ID."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.get_order(
                symbol=symbol,
                orderId=int(order_id),
            )
            return self._parse_order_result(response)
        except BinanceAPIException:
            return None

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            await client.cancel_order(
                symbol=symbol,
                orderId=int(order_id),
            )
            return True
        except BinanceAPIException:
            return False

    async def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        """Get all open orders."""
        client = self._ensure_client()

        try:
            if symbol:
                orders = await client.get_open_orders(
                    symbol=self.normalize_symbol(symbol)
                )
            else:
                orders = await client.get_open_orders()

            return [self._parse_order_result(o) for o in orders]
        except BinanceAPIException:
            return []

    # ==================== MARKET DATA ====================

    async def get_ticker_price(self, symbol: str) -> Decimal | None:
        """Get current price for a symbol."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            return Decimal(str(ticker["price"]))
        except BinanceAPIException:
            return None

    async def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol trading rules."""
        symbol = self.normalize_symbol(symbol)

        # Check cache first
        if symbol in self._symbol_info_cache:
            return self._symbol_info_cache[symbol]

        # Fetch from API
        client = self._ensure_client()
        try:
            info = await client.get_exchange_info()
            for s in info.get("symbols", []):
                self._symbol_info_cache[s["symbol"]] = s
                if s["symbol"] == symbol:
                    return s
        except BinanceAPIException:
            pass

        return None

    # ==================== UTILITY ====================

    # Known step sizes for common Binance futures symbols
    FUTURES_STEP_SIZES = {
        "BTCUSDT": Decimal("0.001"),
        "ETHUSDT": Decimal("0.001"),
        "BNBUSDT": Decimal("0.01"),
        "SOLUSDT": Decimal("0.1"),
        "XRPUSDT": Decimal("0.1"),
        "DOGEUSDT": Decimal("1"),
        "ADAUSDT": Decimal("1"),
        "MATICUSDT": Decimal("1"),
        "LINKUSDT": Decimal("0.1"),
        "AVAXUSDT": Decimal("0.1"),
        "DOTUSDT": Decimal("0.1"),
        "LTCUSDT": Decimal("0.001"),
        "ATOMUSDT": Decimal("0.01"),
        "NEARUSDT": Decimal("0.1"),
        "APTUSDT": Decimal("0.1"),
        "ARBUSDT": Decimal("1"),
        "OPUSDT": Decimal("0.1"),
    }

    def round_quantity(self, symbol: str, quantity: Decimal, is_futures: bool = False) -> Decimal:
        """Round quantity to valid step size.

        Args:
            symbol: Trading symbol
            quantity: Quantity to round
            is_futures: Whether this is for futures trading (uses futures cache first)

        Returns:
            Rounded quantity. Raises ValueError if result is zero.
        """
        symbol = self.normalize_symbol(symbol)

        # Check the appropriate cache first based on order type
        if is_futures:
            info = self._futures_symbol_info_cache.get(symbol) or self._symbol_info_cache.get(symbol)
        else:
            info = self._symbol_info_cache.get(symbol) or self._futures_symbol_info_cache.get(symbol)

        result = quantity
        step_size = None

        if info:
            for f in info.get("filters", []):
                if f["filterType"] == "LOT_SIZE":
                    step_size = Decimal(str(f["stepSize"]))
                    if step_size > 0:
                        result = (quantity // step_size) * step_size
                        break

        # Fallback to known futures step sizes (only for futures)
        if result == quantity and is_futures and symbol in self.FUTURES_STEP_SIZES:
            step_size = self.FUTURES_STEP_SIZES[symbol]
            result = (quantity // step_size) * step_size

        # Default precision if no step size found
        if result == quantity:
            result = quantity.quantize(Decimal("0.001"))

        # CRITICAL: Check for zero quantity - would cause order failure
        if result <= 0:
            raise ValueError(
                f"Quantity {quantity} rounds to zero for {symbol} "
                f"(step_size={step_size or 'default 0.001'}). "
                f"Increase trade size or use different symbol."
            )

        return result

    async def get_min_notional(self, symbol: str, is_futures: bool = False) -> Decimal:
        """Get minimum notional value for a symbol.

        Args:
            symbol: Trading symbol
            is_futures: Whether to check futures minimums

        Returns:
            Minimum notional value in quote currency (usually USDT)
        """
        symbol = self.normalize_symbol(symbol)

        # Check appropriate cache
        if is_futures:
            info = self._futures_symbol_info_cache.get(symbol)
        else:
            info = self._symbol_info_cache.get(symbol)

        # If not in cache, try to fetch
        if not info:
            client = self._ensure_client()
            try:
                if is_futures:
                    exchange_info = await client.futures_exchange_info()
                else:
                    exchange_info = await client.get_exchange_info()

                for s in exchange_info.get("symbols", []):
                    if is_futures:
                        self._futures_symbol_info_cache[s["symbol"]] = s
                    else:
                        self._symbol_info_cache[s["symbol"]] = s
                    if s["symbol"] == symbol:
                        info = s
            except Exception:
                pass

        # Extract MIN_NOTIONAL from filters
        if info:
            for f in info.get("filters", []):
                if f["filterType"] == "MIN_NOTIONAL":
                    return Decimal(str(f.get("minNotional", f.get("notional", "5"))))
                # Futures may use NOTIONAL filter instead
                if f["filterType"] == "NOTIONAL":
                    return Decimal(str(f.get("notional", "5")))

        # Default minimums based on exchange documentation
        # USD-M Futures: 5 USDT, Spot: 5 USDT (for most USDT pairs)
        return Decimal("5")

    def round_price(self, symbol: str, price: Decimal) -> Decimal:
        """Round price to valid tick size."""
        symbol = self.normalize_symbol(symbol)
        info = self._symbol_info_cache.get(symbol) or self._futures_symbol_info_cache.get(symbol)

        if info:
            for f in info.get("filters", []):
                if f["filterType"] == "PRICE_FILTER":
                    tick_size = Decimal(str(f["tickSize"]))
                    if tick_size > 0:
                        return (price // tick_size) * tick_size

        # Default precision
        return price.quantize(Decimal("0.01"))

    # ==================== STOP LOSS ORDERS ====================

    async def place_stop_loss_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL" - the position side, not the SL order side
        quantity: Decimal,
        stop_price: Decimal,
        is_futures: bool = True,
    ) -> dict:
        """Place a Stop Market order on Binance.

        For a LONG position (side="BUY"), SL order will SELL to close.
        For a SHORT position (side="SELL"), SL order will BUY to close.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: The position side ("BUY" for long, "SELL" for short)
            quantity: Position quantity to protect
            stop_price: Price at which to trigger the stop
            is_futures: Whether this is a futures position

        Returns:
            Order response dict with orderId
        """
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)
        rounded_stop = self.round_price(symbol, stop_price)

        # SL order side is opposite of position side
        sl_side = "SELL" if side == "BUY" else "BUY"

        try:
            if is_futures:
                # Binance Futures STOP_MARKET order
                # Uses MARK_PRICE for more stability (prevents manipulation)
                response = await client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type="STOP_MARKET",
                    stopPrice=str(rounded_stop),
                    quantity=str(self.round_quantity(symbol, quantity, is_futures=True)),
                    workingType="MARK_PRICE",  # Trigger on mark price, not last price
                    reduceOnly=True,  # Only reduce position, don't open new one
                )
            else:
                # Spot STOP_LOSS_LIMIT order (spot doesn't have pure stop market)
                # Use stop price as both trigger and limit for market-like execution
                response = await client.create_order(
                    symbol=symbol,
                    side=sl_side,
                    type="STOP_LOSS_LIMIT",
                    stopPrice=str(rounded_stop),
                    price=str(rounded_stop),  # Limit price = stop price for immediate fill
                    quantity=str(self.round_quantity(symbol, quantity)),
                    timeInForce="GTC",
                )

            logger.info(
                f"Placed SL order for {symbol}: {sl_side} {quantity} @ stop {rounded_stop}, "
                f"orderId={response.get('orderId')}"
            )
            return response

        except BinanceAPIException as e:
            logger.error(f"Failed to place stop loss order: {e.message}")
            raise RuntimeError(f"Stop loss order failed: {e.message}") from e

    async def cancel_stop_loss_order(
        self,
        symbol: str,
        order_id: str,
        is_futures: bool = True,
    ) -> bool:
        """Cancel an existing stop loss order.

        Args:
            symbol: Trading symbol
            order_id: The order ID to cancel
            is_futures: Whether this is a futures order

        Returns:
            True if cancelled successfully
        """
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            if is_futures:
                await client.futures_cancel_order(
                    symbol=symbol,
                    orderId=int(order_id),
                )
            else:
                await client.cancel_order(
                    symbol=symbol,
                    orderId=int(order_id),
                )
            logger.info(f"Cancelled SL order {order_id} for {symbol}")
            return True

        except BinanceAPIException as e:
            if "Unknown order" in str(e) or "UNKNOWN_ORDER" in str(e):
                # Order already cancelled or executed
                return True
            logger.error(f"Failed to cancel stop loss order: {e.message}")
            return False

    async def modify_stop_loss_order(
        self,
        symbol: str,
        old_order_id: str,
        side: str,
        quantity: Decimal,
        new_stop_price: Decimal,
        is_futures: bool = True,
    ) -> dict | None:
        """Modify a stop loss by cancelling old and placing new.

        Binance doesn't support order modification, so we cancel and re-place.

        Args:
            symbol: Trading symbol
            old_order_id: Current SL order ID to cancel
            side: Position side ("BUY" or "SELL")
            quantity: New quantity
            new_stop_price: New stop price
            is_futures: Whether this is futures

        Returns:
            New order response, or None if failed
        """
        # Cancel existing order
        cancelled = await self.cancel_stop_loss_order(symbol, old_order_id, is_futures)

        if not cancelled:
            logger.warning(f"Could not cancel old SL order {old_order_id}, placing new anyway")

        # Place new order
        return await self.place_stop_loss_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            stop_price=new_stop_price,
            is_futures=is_futures,
        )

    def calculate_stop_loss_price(
        self,
        entry_price: Decimal,
        side: str,
        stop_loss_percent: Decimal,
    ) -> Decimal:
        """Calculate stop loss price based on entry and percentage.

        Args:
            entry_price: Position entry price
            side: Position side ("BUY" for long, "SELL" for short)
            stop_loss_percent: Stop loss percentage (e.g., 10 for 10%)

        Returns:
            Stop loss trigger price
        """
        sl_decimal = stop_loss_percent / Decimal("100")

        if side == "BUY":
            # Long position: SL below entry
            return entry_price * (Decimal("1") - sl_decimal)
        else:
            # Short position: SL above entry
            return entry_price * (Decimal("1") + sl_decimal)
