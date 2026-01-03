"""
OKX Exchange Integration
Supports both Spot and Futures trading via CCXT
"""

import time
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt

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


class OKXExecutor(BaseExchange):
    """OKX exchange executor for spot and futures trading."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        testnet: bool = False,
    ):
        super().__init__(api_key, api_secret, testnet)
        self.passphrase = passphrase
        self._client: ccxt.okx | None = None
        self._markets_cache: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "okx"

    async def initialize(self) -> None:
        """Initialize OKX client via CCXT."""
        self._client = ccxt.okx(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "password": self.passphrase,
                "sandbox": self.testnet,
                "options": {
                    "defaultType": "spot",
                },
            }
        )

        # Load markets
        await self._client.load_markets()
        self._markets_cache = self._client.markets

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None

    def _ensure_client(self) -> ccxt.okx:
        """Ensure client is initialized."""
        if not self._client:
            raise RuntimeError("OKX client not initialized. Call initialize() first.")
        return self._client

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to OKX format (BTC/USDT)."""
        symbol = symbol.upper().replace("-", "/")
        if "/" not in symbol:
            # Add slash for common pairs
            for quote in ["USDT", "USDC", "BTC", "ETH"]:
                if symbol.endswith(quote):
                    return f"{symbol[:-len(quote)]}/{quote}"
        return symbol

    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse CCXT order status to our enum."""
        status_map = {
            "open": OrderStatus.NEW,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
        }
        return status_map.get(status.lower(), OrderStatus.NEW)

    def _parse_order_result(self, response: dict[str, Any]) -> OrderResult:
        """Parse CCXT order response to OrderResult."""
        fee = response.get("fee", {})
        fee_cost = Decimal(str(fee.get("cost", 0))) if fee.get("cost") else Decimal("0")

        return OrderResult(
            order_id=str(response.get("id", "")),
            client_order_id=response.get("clientOrderId"),
            symbol=response.get("symbol", ""),
            side=OrderSide.BUY if response.get("side") == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if response.get("type") == "market" else OrderType.LIMIT,
            status=self._parse_order_status(response.get("status", "open")),
            quantity=Decimal(str(response.get("amount", 0))),
            filled_quantity=Decimal(str(response.get("filled", 0))),
            price=Decimal(str(response["price"])) if response.get("price") else None,
            avg_fill_price=Decimal(str(response["average"])) if response.get("average") else None,
            fee=fee_cost,
            fee_currency=fee.get("currency"),
            timestamp=response.get("timestamp", int(time.time() * 1000)),
            raw_response=response,
        )

    # ==================== ACCOUNT ====================

    async def get_account_balance(self) -> list[Balance]:
        """Get all account balances."""
        client = self._ensure_client()
        balance = await client.fetch_balance()

        balances = []
        for asset, data in balance.get("total", {}).items():
            total = Decimal(str(data)) if data else Decimal("0")
            if total > 0:
                free = Decimal(str(balance.get("free", {}).get(asset, 0)))
                used = Decimal(str(balance.get("used", {}).get(asset, 0)))
                balances.append(
                    Balance(
                        asset=asset,
                        free=free,
                        locked=used,
                        total=total,
                    )
                )

        return balances

    async def get_asset_balance(self, asset: str) -> Balance | None:
        """Get balance for a specific asset."""
        client = self._ensure_client()
        balance = await client.fetch_balance()

        total = balance.get("total", {}).get(asset.upper())
        if not total:
            return None

        return Balance(
            asset=asset.upper(),
            free=Decimal(str(balance.get("free", {}).get(asset.upper(), 0))),
            locked=Decimal(str(balance.get("used", {}).get(asset.upper(), 0))),
            total=Decimal(str(total)),
        )

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
            params = {"tdMode": "cash"}
            if quote_order_qty:
                # OKX uses 'cost' for quote order quantity in market orders
                response = await client.create_market_buy_order(
                    symbol,
                    float(quantity),
                    params={**params, "quoteOrderQty": str(quote_order_qty)},
                )
            else:
                response = await client.create_market_buy_order(
                    symbol,
                    float(quantity),
                    params=params,
                )
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            raise RuntimeError(f"OKX spot buy failed: {str(e)}") from e

    async def spot_market_sell(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Execute spot market sell."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.create_market_sell_order(
                symbol,
                float(quantity),
                params={"tdMode": "cash"},
            )
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            raise RuntimeError(f"OKX spot sell failed: {str(e)}") from e

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
            response = await client.create_limit_buy_order(
                symbol,
                float(quantity),
                float(price),
                params={"tdMode": "cash"},
            )
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            raise RuntimeError(f"OKX limit buy failed: {str(e)}") from e

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
            response = await client.create_limit_sell_order(
                symbol,
                float(quantity),
                float(price),
                params={"tdMode": "cash"},
            )
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            raise RuntimeError(f"OKX limit sell failed: {str(e)}") from e

    # ==================== FUTURES TRADING ====================

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a futures symbol."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            await client.set_leverage(leverage, symbol, params={"mgnMode": "cross"})
            return True
        except ccxt.BaseError:
            return False

    async def get_leverage(self, symbol: str) -> int:
        """Get current leverage for a symbol."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            positions = await client.fetch_positions([symbol])
            if positions:
                return int(positions[0].get("leverage", 1))
            return 1
        except ccxt.BaseError:
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
            # Set to swap mode
            client.options["defaultType"] = "swap"
            response = await client.create_market_buy_order(
                symbol,
                float(quantity),
                params={
                    "tdMode": "cross",
                    "posSide": "long",
                },
            )
            client.options["defaultType"] = "spot"
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            client.options["defaultType"] = "spot"
            raise RuntimeError(f"OKX futures long failed: {str(e)}") from e

    async def futures_market_short(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Open a short position with market order."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            client.options["defaultType"] = "swap"
            response = await client.create_market_sell_order(
                symbol,
                float(quantity),
                params={
                    "tdMode": "cross",
                    "posSide": "short",
                },
            )
            client.options["defaultType"] = "spot"
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            client.options["defaultType"] = "spot"
            raise RuntimeError(f"OKX futures short failed: {str(e)}") from e

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
                if pos.side == position_side:
                    quantity = pos.quantity
                    break

            if quantity is None:
                raise RuntimeError(f"No open {position_side.value} position found for {symbol}")

        try:
            client.options["defaultType"] = "swap"

            if position_side == PositionSide.LONG:
                response = await client.create_market_sell_order(
                    symbol,
                    float(quantity),
                    params={
                        "tdMode": "cross",
                        "posSide": "long",
                        "reduceOnly": True,
                    },
                )
            else:
                response = await client.create_market_buy_order(
                    symbol,
                    float(quantity),
                    params={
                        "tdMode": "cross",
                        "posSide": "short",
                        "reduceOnly": True,
                    },
                )

            client.options["defaultType"] = "spot"
            return self._parse_order_result(response)
        except ccxt.BaseError as e:
            client.options["defaultType"] = "spot"
            raise RuntimeError(f"OKX close position failed: {str(e)}") from e

    async def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        """Get open futures positions."""
        client = self._ensure_client()

        try:
            client.options["defaultType"] = "swap"
            if symbol:
                positions = await client.fetch_positions([self.normalize_symbol(symbol)])
            else:
                positions = await client.fetch_positions()
            client.options["defaultType"] = "spot"

            result = []
            for pos in positions:
                contracts = Decimal(str(pos.get("contracts", 0)))
                if contracts == 0:
                    continue

                side_str = pos.get("side", "long")
                side = PositionSide.LONG if side_str == "long" else PositionSide.SHORT

                result.append(
                    Position(
                        symbol=pos["symbol"],
                        side=side,
                        quantity=abs(contracts),
                        entry_price=Decimal(str(pos.get("entryPrice", 0))),
                        mark_price=Decimal(str(pos.get("markPrice", 0))),
                        unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", 0))),
                        leverage=int(pos.get("leverage", 1)),
                        liquidation_price=Decimal(str(pos["liquidationPrice"])) if pos.get("liquidationPrice") else None,
                        margin_type=pos.get("marginMode", "cross"),
                        timestamp=pos.get("timestamp", int(time.time() * 1000)),
                    )
                )

            return result
        except ccxt.BaseError:
            client.options["defaultType"] = "spot"
            return []

    # ==================== ORDERS ====================

    async def get_order(self, symbol: str, order_id: str) -> OrderResult | None:
        """Get order details by ID."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            response = await client.fetch_order(order_id, symbol)
            return self._parse_order_result(response)
        except ccxt.BaseError:
            return None

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            await client.cancel_order(order_id, symbol)
            return True
        except ccxt.BaseError:
            return False

    async def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        """Get all open orders."""
        client = self._ensure_client()

        try:
            if symbol:
                orders = await client.fetch_open_orders(self.normalize_symbol(symbol))
            else:
                orders = await client.fetch_open_orders()

            return [self._parse_order_result(o) for o in orders]
        except ccxt.BaseError:
            return []

    # ==================== MARKET DATA ====================

    async def get_ticker_price(self, symbol: str) -> Decimal | None:
        """Get current price for a symbol."""
        client = self._ensure_client()
        symbol = self.normalize_symbol(symbol)

        try:
            ticker = await client.fetch_ticker(symbol)
            return Decimal(str(ticker["last"]))
        except ccxt.BaseError:
            return None

    async def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol trading rules."""
        symbol = self.normalize_symbol(symbol)
        return self._markets_cache.get(symbol)

    # ==================== UTILITY ====================

    def round_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """Round quantity to valid step size."""
        symbol = self.normalize_symbol(symbol)
        market = self._markets_cache.get(symbol)

        if market:
            precision = market.get("precision", {}).get("amount")
            if precision:
                return Decimal(str(round(float(quantity), precision)))

        return quantity.quantize(Decimal("0.00001"))

    def round_price(self, symbol: str, price: Decimal) -> Decimal:
        """Round price to valid tick size."""
        symbol = self.normalize_symbol(symbol)
        market = self._markets_cache.get(symbol)

        if market:
            precision = market.get("precision", {}).get("price")
            if precision:
                return Decimal(str(round(float(price), precision)))

        return price.quantize(Decimal("0.01"))
