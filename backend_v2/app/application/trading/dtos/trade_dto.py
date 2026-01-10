"""Trade DTO - data transfer object for API responses."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class TradeDTO:
    """Trade data transfer object.

    Використовується для API responses та між layers.
    Immutable, без business logic.
    """

    id: int
    user_id: int
    signal_id: int | None
    symbol: str
    side: str
    trade_type: str
    status: str
    size_usdt: Decimal
    quantity: Decimal
    leverage: int
    executed_price: Decimal | None
    executed_quantity: Decimal | None
    exchange_order_id: str | None
    fee_amount: Decimal | None
    created_at: datetime
    executed_at: datetime | None
    error_message: str | None
