"""Signal DTOs для API responses."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class SignalDTO:
    """Signal Data Transfer Object.

    Використовується для передачі signal даних між layers.
    """

    id: int
    whale_id: int | None
    source: str
    status: str
    priority: str
    symbol: str
    side: str
    trade_type: str
    entry_price: Decimal | None
    quantity: Decimal | None
    leverage: int | None
    detected_at: datetime
    processed_at: datetime | None
    trades_executed: int
    error_message: str | None


@dataclass(frozen=True)
class SignalProcessingResultDTO:
    """Result of signal processing.

    Містить інформацію про результат обробки signal.
    """

    signal_id: int
    signal: SignalDTO
    trades_executed: int
    successful_trades: int
    failed_trades: int
    total_volume_usdt: Decimal
    errors: list[str]
