"""ExchangePort - abstract interface для інтеграції з біржами.

Це PORT в Hexagonal Architecture / INTERFACE в Dependency Inversion Principle.

Domain layer визначає ЩО потрібно (цей interface).
Infrastructure layer імплементує ЯК це зробити (adapters).

Dependency flow: Domain ← Infrastructure (arrows point inward)
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from ..value_objects import Balance, OrderResult


class ExchangePort(ABC):
    """Abstract interface для всіх бірж.

    Всі exchange adapters (Binance, Bybit, Bitget) мають імплементувати цей interface.
    Це забезпечує:
    - **Dependency Inversion**: Domain не залежить від конкретних бірж
    - **Testability**: Можна mock цей interface в tests
    - **Extensibility**: Легко додати нову біржу

    Example (Infrastructure implements):
        >>> class BinanceAdapter(ExchangePort):
        ...     async def execute_spot_buy(self, symbol, quantity):
        ...         # Binance-specific implementation
        ...         response = await self.client.order_market_buy(...)
        ...         return OrderResult(...)  # Normalize to domain VO

        >>> class BybitAdapter(ExchangePort):
        ...     async def execute_spot_buy(self, symbol, quantity):
        ...         # Bybit-specific implementation (different SDK!)
        ...         response = await self.ccxt_client.create_market_buy_order(...)
        ...         return OrderResult(...)  # Same VO!

    Example (Domain uses):
        >>> async def execute_trade(exchange: ExchangePort, ...):
        ...     # Domain code не знає яка саме біржа
        ...     result = await exchange.execute_spot_buy(symbol, quantity)
        ...     # result завжди OrderResult (normalized)
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize exchange connection.

        Load markets, setup session, тощо.
        Must be called before using exchange.

        Raises:
            ExchangeConnectionError: If connection failed.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close exchange connection.

        Cleanup resources, close HTTP sessions.
        """
        pass

    # --- SPOT TRADING ---

    @abstractmethod
    async def execute_spot_buy(self, symbol: str, quantity: Decimal) -> OrderResult:
        """Execute spot market buy order.

        Args:
            symbol: Trading pair (normalized, e.g., "BTCUSDT").
            quantity: Quantity to buy (в базовій валюті, e.g., BTC).

        Returns:
            OrderResult with execution details.

        Raises:
            InsufficientBalanceError: If not enough funds.
            ExchangeAPIError: If exchange API failed.
            RateLimitError: If rate limit exceeded.
        """
        pass

    @abstractmethod
    async def execute_spot_sell(self, symbol: str, quantity: Decimal) -> OrderResult:
        """Execute spot market sell order.

        Args:
            symbol: Trading pair (normalized).
            quantity: Quantity to sell.

        Returns:
            OrderResult with execution details.

        Raises:
            InsufficientBalanceError: If not enough balance to sell.
            ExchangeAPIError: If exchange API failed.
        """
        pass

    # --- FUTURES TRADING ---

    @abstractmethod
    async def execute_futures_long(
        self, symbol: str, quantity: Decimal, leverage: int
    ) -> OrderResult:
        """Open futures long position.

        Args:
            symbol: Trading pair (normalized).
            quantity: Position size (в USDT).
            leverage: Leverage (1-125).

        Returns:
            OrderResult with execution details.

        Raises:
            InsufficientBalanceError: If not enough margin.
            InvalidLeverageError: If leverage invalid for this pair.
            ExchangeAPIError: If exchange API failed.
        """
        pass

    @abstractmethod
    async def execute_futures_short(
        self, symbol: str, quantity: Decimal, leverage: int
    ) -> OrderResult:
        """Open futures short position.

        Args:
            symbol: Trading pair (normalized).
            quantity: Position size (в USDT).
            leverage: Leverage (1-125).

        Returns:
            OrderResult with execution details.
        """
        pass

    @abstractmethod
    async def close_futures_position(
        self, symbol: str, position_side: str
    ) -> OrderResult:
        """Close futures position.

        Args:
            symbol: Trading pair.
            position_side: "LONG" або "SHORT".

        Returns:
            OrderResult with execution details.

        Raises:
            PositionNotFoundError: If position not found.
        """
        pass

    # --- BALANCE & ACCOUNT ---

    @abstractmethod
    async def get_balances(self) -> list[Balance]:
        """Get all account balances.

        Returns:
            List of Balance objects для всіх assets.

        Example:
            >>> balances = await exchange.get_balances()
            >>> usdt_balance = next(b for b in balances if b.asset == "USDT")
            >>> usdt_balance.free  # Decimal("1000.5")
        """
        pass

    @abstractmethod
    async def get_balance(self, asset: str) -> Balance:
        """Get balance for specific asset.

        Args:
            asset: Asset name (e.g., "USDT").

        Returns:
            Balance object.

        Raises:
            AssetNotFoundError: If asset not found.
        """
        pass

    # --- SYMBOL INFO ---

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> dict:
        """Get trading rules for symbol.

        Returns info про:
        - Minimum order quantity
        - Price precision
        - Quantity precision
        - Minimum notional (min order value)

        Args:
            symbol: Trading pair.

        Returns:
            Dict with symbol info.
        """
        pass
