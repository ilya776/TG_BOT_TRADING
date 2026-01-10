"""Signal Domain Events."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.shared import DomainEvent


@dataclass(frozen=True)
class SignalDetectedEvent(DomainEvent):
    """Signal was detected and created.

    Published when:
    - Whale activity detected
    - Manual signal created by user
    - Indicator generated signal

    Subscribers can:
    - Send notification to followers
    - Log signal for analytics
    - Trigger auto-copy for followers
    """

    signal_id: int
    whale_id: int | None
    source: str
    symbol: str
    side: str
    price: Decimal
    size: Decimal
    priority: str


@dataclass(frozen=True)
class SignalProcessingStartedEvent(DomainEvent):
    """Signal processing started.

    Published when:
    - Signal picked from queue
    - Processing begins (copying to followers)

    Subscribers can:
    - Update signal status in UI
    - Start timeout timer
    - Log processing start
    """

    signal_id: int
    symbol: str
    source: str


@dataclass(frozen=True)
class SignalProcessedEvent(DomainEvent):
    """Signal successfully processed.

    Published when:
    - All follower trades executed
    - Signal marked as PROCESSED

    Subscribers can:
    - Send success notification
    - Update analytics (success rate)
    - Archive signal
    """

    signal_id: int
    symbol: str
    trades_executed: int


@dataclass(frozen=True)
class SignalFailedEvent(DomainEvent):
    """Signal processing failed.

    Published when:
    - Trade execution failed
    - Validation failed
    - Timeout occurred

    Subscribers can:
    - Send error notification
    - Log failure for debugging
    - Retry signal (if applicable)
    """

    signal_id: int
    symbol: str
    error_message: str
