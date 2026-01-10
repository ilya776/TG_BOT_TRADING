"""Signal Entity - Aggregate Root для trading signals.

Signal represents a trading signal detected from various sources
(whale activity, indicators, manual input) that can be automatically
copied by followers.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Union

from app.domain.shared import AggregateRoot
from app.domain.signals.value_objects import SignalPriority, SignalSource, SignalStatus


def _normalize_enum_value(value: Union[str, Enum]) -> str:
    """Convert enum to string value, pass strings through."""
    if isinstance(value, Enum):
        return value.value
    return value


class Signal(AggregateRoot):
    """Signal Aggregate Root.

    Responsibilities:
    - Track signal lifecycle (pending → processing → processed/failed)
    - Calculate signal priority
    - Validate signal data
    - Emit domain events (SignalDetected, SignalProcessed, etc.)
    - Check if signal expired

    Business Rules:
    - Signal cannot be processed if not PENDING
    - Signal cannot be marked complete if not PROCESSING
    - Signal expires after 60 seconds (configurable)
    - Priority determines processing order

    Example:
        >>> signal = Signal.create_whale_signal(
        ...     whale_id=123,
        ...     symbol="BTCUSDT",
        ...     side="buy",
        ...     price=Decimal("50000"),
        ...     size=Decimal("1000"),
        ... )
        >>> signal.start_processing()
        >>> signal.mark_processed(trades_executed=5)
    """

    def __init__(
        self,
        *,
        id: int | None = None,
        whale_id: int | None,
        user_id: int | None,
        source: SignalSource,
        symbol: str,
        side: str,
        trade_type: str,
        price: Decimal,
        size: Decimal,
        priority: SignalPriority,
        status: SignalStatus,
        detected_at: datetime,
        processing_started_at: datetime | None = None,
        processed_at: datetime | None = None,
        trades_executed: int = 0,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Initialize Signal entity.

        Args:
            id: Signal ID (None for new signals).
            whale_id: Whale ID (if source is WHALE).
            user_id: User ID (if source is MANUAL).
            source: Signal source (whale, indicator, manual, etc.).
            symbol: Trading pair (e.g., BTCUSDT).
            side: Trade side (buy or sell).
            trade_type: Trade type (spot or futures).
            price: Signal price.
            size: Signal size in USDT.
            priority: Processing priority (high, medium, low).
            status: Current status.
            detected_at: When signal was detected.
            processing_started_at: When processing started (if processing).
            processed_at: When processing completed (if processed).
            trades_executed: Number of trades executed from this signal.
            error_message: Error message (if failed).
            metadata: Additional metadata (exchange, indicators, etc.).
        """
        super().__init__(id=id)
        self.whale_id = whale_id
        self.user_id = user_id
        self.source = source
        self.symbol = symbol
        self.side = _normalize_enum_value(side)
        self.trade_type = _normalize_enum_value(trade_type)
        self.price = price
        self.size = size
        self.priority = priority
        self.status = status
        self.detected_at = detected_at
        self.processing_started_at = processing_started_at
        self.processed_at = processed_at
        self.trades_executed = trades_executed
        self.error_message = error_message
        self.metadata = metadata or {}

    @classmethod
    def create_whale_signal(
        cls,
        *,
        whale_id: int,
        symbol: str,
        side: Union[str, Enum],
        signal_type: Union[str, Enum] | None = None,
        trade_type: Union[str, Enum] | None = None,
        price: Decimal,
        size: Decimal,
        whale_tier: str = "regular",
        metadata: dict | None = None,
    ) -> "Signal":
        """Create signal від whale activity.

        Args:
            whale_id: Whale ID.
            symbol: Trading pair.
            side: Trade side (buy/sell or TradeSide enum).
            signal_type: Signal/trade type (spot/futures or SignalType/TradeType enum).
                        Alias for trade_type for semantic clarity.
            trade_type: Trade type (deprecated, use signal_type).
            price: Execution price.
            size: Position size in USDT.
            whale_tier: Whale tier (vip, premium, regular).
            metadata: Additional metadata.

        Returns:
            New Signal entity with PENDING status.
        """
        # Support both signal_type and trade_type (signal_type preferred)
        actual_trade_type = signal_type or trade_type or "spot"

        priority = SignalPriority.from_whale_tier(whale_tier)

        signal = cls(
            whale_id=whale_id,
            user_id=None,
            source=SignalSource.WHALE,
            symbol=symbol,
            side=side,
            trade_type=actual_trade_type,
            price=price,
            size=size,
            priority=priority,
            status=SignalStatus.PENDING,
            detected_at=datetime.now(timezone.utc),
            metadata=metadata,
        )

        # Emit SignalDetectedEvent
        from ..events import SignalDetectedEvent

        signal.add_domain_event(
            SignalDetectedEvent(
                signal_id=signal.id or 0,
                whale_id=whale_id,
                source=SignalSource.WHALE.value,
                symbol=symbol,
                side=side,
                price=price,
                size=size,
                priority=priority.value,
            )
        )

        return signal

    @classmethod
    def create_manual_signal(
        cls,
        *,
        user_id: int,
        symbol: str,
        side: Union[str, Enum],
        signal_type: Union[str, Enum] | None = None,
        trade_type: Union[str, Enum] | None = None,
        price: Decimal,
        size: Decimal,
        priority: SignalPriority = SignalPriority.MEDIUM,
        metadata: dict | None = None,
    ) -> "Signal":
        """Create manual signal від користувача.

        Args:
            user_id: User ID who created signal.
            symbol: Trading pair.
            side: Trade side (buy/sell or TradeSide enum).
            signal_type: Signal/trade type (spot/futures or SignalType/TradeType enum).
            trade_type: Trade type (deprecated, use signal_type).
            price: Target price.
            size: Position size.
            priority: Priority (default MEDIUM).
            metadata: Additional metadata.

        Returns:
            New Signal entity with PENDING status.
        """
        # Support both signal_type and trade_type (signal_type preferred)
        actual_trade_type = signal_type or trade_type or "spot"

        signal = cls(
            whale_id=None,
            user_id=user_id,
            source=SignalSource.MANUAL,
            symbol=symbol,
            side=side,
            trade_type=actual_trade_type,
            price=price,
            size=size,
            priority=priority,
            status=SignalStatus.PENDING,
            detected_at=datetime.now(timezone.utc),
            metadata=metadata,
        )

        # Emit SignalDetectedEvent
        from ..events import SignalDetectedEvent

        signal.add_domain_event(
            SignalDetectedEvent(
                signal_id=signal.id or 0,
                whale_id=None,
                source=SignalSource.MANUAL.value,
                symbol=symbol,
                side=side,
                price=price,
                size=size,
                priority=priority.value,
            )
        )

        return signal

    def start_processing(self) -> None:
        """Start signal processing.

        Raises:
            ValueError: If signal is not PENDING.
        """
        if self.status != SignalStatus.PENDING:
            raise ValueError(
                f"Cannot start processing signal in status {self.status.value}"
            )

        self.status = SignalStatus.PROCESSING
        self.processing_started_at = datetime.now(timezone.utc)

        # Emit SignalProcessingStartedEvent
        from ..events import SignalProcessingStartedEvent

        self.add_domain_event(
            SignalProcessingStartedEvent(
                signal_id=self.id or 0,
                symbol=self.symbol,
                source=self.source.value,
            )
        )

    def mark_processed(self, trades_executed: int) -> None:
        """Mark signal as successfully processed.

        Args:
            trades_executed: Number of trades executed from this signal.

        Raises:
            ValueError: If signal is not PROCESSING.
        """
        if self.status != SignalStatus.PROCESSING:
            raise ValueError(
                f"Cannot mark signal as processed in status {self.status.value}"
            )

        self.status = SignalStatus.PROCESSED
        self.processed_at = datetime.now(timezone.utc)
        self.trades_executed = trades_executed

        # Emit SignalProcessedEvent
        from ..events import SignalProcessedEvent

        self.add_domain_event(
            SignalProcessedEvent(
                signal_id=self.id or 0,
                symbol=self.symbol,
                trades_executed=trades_executed,
            )
        )

    def mark_failed(self, error_message: str) -> None:
        """Mark signal as failed.

        Args:
            error_message: Error message describing failure.

        Note:
            Can be called from any status (retry failed, validation failed, etc.).
        """
        self.status = SignalStatus.FAILED
        self.error_message = error_message
        self.processed_at = datetime.now(timezone.utc)

        # Emit SignalFailedEvent
        from ..events import SignalFailedEvent

        self.add_domain_event(
            SignalFailedEvent(
                signal_id=self.id or 0,
                symbol=self.symbol,
                error_message=error_message,
            )
        )

    def is_expired(self, expiry_seconds: int = 60) -> bool:
        """Check if signal has expired.

        Args:
            expiry_seconds: Expiry time in seconds (default 60).

        Returns:
            True if signal is older than expiry_seconds.

        Note:
            Expired signals should not be processed (price may be stale).
        """
        now = datetime.now(timezone.utc)
        age = (now - self.detected_at).total_seconds()
        return age > expiry_seconds

    def mark_expired(self) -> None:
        """Mark signal as expired.

        Note:
            Called by cleanup job for old PENDING signals.
        """
        if self.status == SignalStatus.PENDING:
            self.status = SignalStatus.EXPIRED
            self.processed_at = datetime.now(timezone.utc)

    def __eq__(self, other: object) -> bool:
        """Check equality based on ID.

        Args:
            other: Other object to compare.

        Returns:
            True if same signal (same ID).
        """
        if not isinstance(other, Signal):
            return False
        return self.id is not None and self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID.

        Returns:
            Hash of signal ID.
        """
        return hash(self.id) if self.id else hash(id(self))

    def __repr__(self) -> str:
        """String representation.

        Returns:
            String representation of signal.
        """
        return (
            f"Signal(id={self.id}, source={self.source.value}, "
            f"symbol={self.symbol}, side={self.side}, "
            f"status={self.status.value}, priority={self.priority.value})"
        )
