"""Enums для Trading bounded context."""

from enum import Enum


class TradeStatus(str, Enum):
    """Trade lifecycle status.

    State machine:
        PENDING → EXECUTING → FILLED
        PENDING → FAILED
        EXECUTING → FAILED
        EXECUTING → NEEDS_RECONCILIATION (якщо exchange call успішний але DB update failed)
    """

    PENDING = "pending"
    """Trade створений, funds reserved, очікує execution на біржі."""

    EXECUTING = "executing"
    """Trade відправлений на біржу, очікуємо результату."""

    FILLED = "filled"
    """Trade успішно виконаний на біржі."""

    FAILED = "failed"
    """Trade failed (недостатньо балансу, exchange error, etc)."""

    NEEDS_RECONCILIATION = "needs_reconciliation"
    """Exchange call успішний але DB update failed - потребує reconciliation."""


class TradeSide(str, Enum):
    """Trade direction."""

    BUY = "buy"
    """Купівля (spot або long futures)."""

    SELL = "sell"
    """Продаж (spot або short futures)."""


class TradeType(str, Enum):
    """Trade type (spot vs futures)."""

    SPOT = "spot"
    """Spot trading (купівля/продаж активу)."""

    FUTURES_LONG = "futures_long"
    """Futures long position (bet що ціна зросте)."""

    FUTURES_SHORT = "futures_short"
    """Futures short position (bet що ціна впаде)."""


class PositionStatus(str, Enum):
    """Position lifecycle status."""

    OPEN = "open"
    """Позиція відкрита, активна."""

    CLOSING = "closing"
    """Позиція закривається (trade відправлений на біржу)."""

    CLOSED = "closed"
    """Позиція закрита."""

    LIQUIDATED = "liquidated"
    """Позиція ліквідована біржею."""


class PositionSide(str, Enum):
    """Position direction (для futures)."""

    LONG = "long"
    """Long position (profit якщо ціна зростає)."""

    SHORT = "short"
    """Short position (profit якщо ціна падає)."""
