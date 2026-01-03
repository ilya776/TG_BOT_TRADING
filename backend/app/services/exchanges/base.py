"""
Base Exchange Interface
Abstract base class for all exchange integrations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"  # For one-way mode


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"


@dataclass
class Balance:
    """Account balance for a specific asset."""

    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any], asset_key: str = "asset") -> "Balance":
        return cls(
            asset=data.get(asset_key, ""),
            free=Decimal(str(data.get("free", 0))),
            locked=Decimal(str(data.get("locked", 0))),
            total=Decimal(str(data.get("total", 0))),
        )


@dataclass
class OrderResult:
    """Result of an order execution."""

    order_id: str
    client_order_id: str | None
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    avg_fill_price: Decimal | None
    fee: Decimal
    fee_currency: str | None
    timestamp: int
    raw_response: dict[str, Any]

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_partially_filled(self) -> bool:
        return self.status == OrderStatus.PARTIALLY_FILLED

    @property
    def fill_percentage(self) -> Decimal:
        if self.quantity == 0:
            return Decimal("0")
        return (self.filled_quantity / self.quantity) * 100


@dataclass
class Position:
    """Open position information."""

    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: int
    liquidation_price: Decimal | None
    margin_type: str  # "cross" or "isolated"
    timestamp: int


class BaseExchange(ABC):
    """
    Abstract base class for exchange integrations.

    All exchange implementations must inherit from this class
    and implement all abstract methods.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._client: Any = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Exchange name."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the exchange client."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup."""
        pass

    # ==================== ACCOUNT ====================

    @abstractmethod
    async def get_account_balance(self) -> list[Balance]:
        """Get all account balances."""
        pass

    @abstractmethod
    async def get_asset_balance(self, asset: str) -> Balance | None:
        """Get balance for a specific asset."""
        pass

    # ==================== SPOT TRADING ====================

    @abstractmethod
    async def spot_market_buy(
        self,
        symbol: str,
        quantity: Decimal,
        quote_order_qty: Decimal | None = None,
    ) -> OrderResult:
        """
        Execute a spot market buy order.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            quantity: Amount of base asset to buy
            quote_order_qty: Amount of quote asset to spend (optional)

        Returns:
            Order result
        """
        pass

    @abstractmethod
    async def spot_market_sell(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """
        Execute a spot market sell order.

        Args:
            symbol: Trading pair
            quantity: Amount of base asset to sell

        Returns:
            Order result
        """
        pass

    @abstractmethod
    async def spot_limit_buy(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
    ) -> OrderResult:
        """Execute a spot limit buy order."""
        pass

    @abstractmethod
    async def spot_limit_sell(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
    ) -> OrderResult:
        """Execute a spot limit sell order."""
        pass

    # ==================== FUTURES TRADING ====================

    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        pass

    @abstractmethod
    async def get_leverage(self, symbol: str) -> int:
        """Get current leverage for a symbol."""
        pass

    @abstractmethod
    async def futures_market_long(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Open a long position with market order."""
        pass

    @abstractmethod
    async def futures_market_short(
        self,
        symbol: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Open a short position with market order."""
        pass

    @abstractmethod
    async def futures_close_position(
        self,
        symbol: str,
        position_side: PositionSide,
        quantity: Decimal | None = None,
    ) -> OrderResult:
        """
        Close a futures position.

        Args:
            symbol: Trading pair
            position_side: LONG or SHORT
            quantity: Amount to close (None = close all)

        Returns:
            Order result
        """
        pass

    @abstractmethod
    async def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        """Get open futures positions."""
        pass

    # ==================== ORDERS ====================

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> OrderResult | None:
        """Get order details by ID."""
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order."""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        """Get all open orders."""
        pass

    # ==================== MARKET DATA ====================

    @abstractmethod
    async def get_ticker_price(self, symbol: str) -> Decimal | None:
        """Get current price for a symbol."""
        pass

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol trading rules and info."""
        pass

    # ==================== UTILITY METHODS ====================

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for this exchange.
        Override in subclasses if needed.
        """
        return symbol.upper().replace("/", "").replace("-", "")

    async def validate_order_params(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validate order parameters against exchange rules.

        Returns:
            Tuple of (is_valid, error_message)
        """
        symbol_info = await self.get_symbol_info(symbol)
        if not symbol_info:
            return False, f"Symbol {symbol} not found"

        # Basic validation - override in subclasses for specific rules
        if quantity <= 0:
            return False, "Quantity must be positive"

        if price is not None and price <= 0:
            return False, "Price must be positive"

        return True, None

    def round_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """
        Round quantity to valid step size for the symbol.
        Override in subclasses with exchange-specific logic.
        """
        # Default: round to 8 decimal places
        return quantity.quantize(Decimal("0.00000001"))

    def round_price(self, symbol: str, price: Decimal) -> Decimal:
        """
        Round price to valid tick size for the symbol.
        Override in subclasses with exchange-specific logic.
        """
        # Default: round to 8 decimal places
        return price.quantize(Decimal("0.00000001"))
