"""Position DTO - data transfer object for API responses."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class PositionDTO:
    """Position data transfer object."""

    id: int
    user_id: int
    symbol: str
    side: str
    status: str
    entry_price: Decimal
    quantity: Decimal
    leverage: int
    stop_loss_price: Decimal | None
    take_profit_price: Decimal | None
    entry_trade_id: int
    exit_price: Decimal | None
    exit_trade_id: int | None
    unrealized_pnl: Decimal
    realized_pnl: Decimal | None
    opened_at: datetime
    closed_at: datetime | None
