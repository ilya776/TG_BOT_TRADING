"""ExecuteCopyTrade Command - виконати copy trade на біржі.

Це core use case всієї системи.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.application.shared import Command


@dataclass(frozen=True)
class ExecuteCopyTradeCommand(Command):
    """Command для виконання copy trade.

    Orchestrates:
    1. Create trade в PENDING (Phase 1: RESERVE funds)
    2. Execute на exchange (з retry + circuit breaker)
    3. Update trade to FILLED/FAILED (Phase 2: CONFIRM/ROLLBACK)
    4. Create position якщо success
    5. Publish domain events

    Example:
        >>> command = ExecuteCopyTradeCommand(
        ...     user_id=1,
        ...     signal_id=100,
        ...     exchange_name="binance",
        ...     symbol="BTCUSDT",
        ...     side="buy",
        ...     size_usdt=Decimal("100"),
        ...     leverage=1,
        ... )
        >>> result = await handler.handle(command)
        >>> # Trade executed, position created, events published!
    """

    user_id: int
    """ID користувача який робить trade."""

    signal_id: int
    """ID whale signal який копіюємо."""

    exchange_name: str
    """Назва біржі (binance, bybit, bitget)."""

    symbol: str
    """Trading pair (e.g., BTCUSDT)."""

    side: str
    """Trade side (buy або sell)."""

    trade_type: str
    """Trade type (spot, futures_long, futures_short)."""

    size_usdt: Decimal
    """Розмір trade в USDT."""

    leverage: int = 1
    """Leverage (1 для spot, 1-125 для futures)."""

    stop_loss_percentage: Decimal | None = None
    """Stop-loss % від entry price (optional)."""

    take_profit_percentage: Decimal | None = None
    """Take-profit % від entry price (optional)."""
