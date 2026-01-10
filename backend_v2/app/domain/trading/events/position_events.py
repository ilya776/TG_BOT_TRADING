"""Domain Events для Position lifecycle."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.shared import DomainEvent


@dataclass(frozen=True)
class PositionOpenedEvent(DomainEvent):
    """Event: Position відкрита.

    Subscribers можуть:
    - Відправити notification "Position opened"
    - Записати в audit log
    - Почати monitoring SL/TP
    """

    position_id: int
    user_id: int
    symbol: str
    side: str  # "long" або "short"
    entry_price: Decimal
    quantity: Decimal
    leverage: int
    entry_trade_id: int


@dataclass(frozen=True)
class PositionClosedEvent(DomainEvent):
    """Event: Position закрита.

    Critical event - позиція реалізована (profit/loss зафіксований).
    """

    position_id: int
    user_id: int
    symbol: str
    side: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    realized_pnl: Decimal
    exit_trade_id: int


@dataclass(frozen=True)
class PositionLiquidatedEvent(DomainEvent):
    """Event: Position ліквідована біржею.

    Critical event - означає margin call, зазвичай повна втрата.
    Потребує негайного alert.
    """

    position_id: int
    user_id: int
    symbol: str
    liquidation_price: Decimal
    realized_pnl: Decimal


@dataclass(frozen=True)
class StopLossTriggeredEvent(DomainEvent):
    """Event: Stop-loss triggered.

    Потребує негайного закриття позиції.
    """

    position_id: int
    user_id: int
    symbol: str
    current_price: Decimal
    stop_loss_price: Decimal


@dataclass(frozen=True)
class TakeProfitTriggeredEvent(DomainEvent):
    """Event: Take-profit triggered.

    Потребує закриття позиції для фіксації profit.
    """

    position_id: int
    user_id: int
    symbol: str
    current_price: Decimal
    take_profit_price: Decimal
