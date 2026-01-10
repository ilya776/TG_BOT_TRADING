"""Tests for Signal aggregate root."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.signals.entities import Signal
from app.domain.signals.events import (
    SignalDetectedEvent,
    SignalFailedEvent,
    SignalProcessedEvent,
    SignalProcessingStartedEvent,
)
from app.domain.signals.value_objects import SignalPriority, SignalSource, SignalStatus


class TestSignalCreation:
    """Tests для Signal creation factory methods."""

    def test_create_whale_signal_success(self):
        """Test creating whale signal."""
        # Act
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
            whale_tier="vip",
        )

        # Assert
        assert signal.id is None  # Not persisted yet
        assert signal.whale_id == 123
        assert signal.source == SignalSource.WHALE
        assert signal.status == SignalStatus.PENDING
        assert signal.priority == SignalPriority.HIGH  # VIP = HIGH
        assert signal.symbol == "BTCUSDT"
        assert signal.side == "buy"
        assert signal.trade_type == "futures"
        assert signal.price == Decimal("50000")
        assert signal.size == Decimal("1000")
        assert signal.trades_executed == 0
        assert signal.error_message is None
        assert signal.detected_at is not None
        assert signal.processed_at is None

        # Check domain event
        events = signal.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], SignalDetectedEvent)
        assert events[0].whale_id == 123
        assert events[0].symbol == "BTCUSDT"
        assert events[0].priority == "high"

    def test_create_manual_signal_success(self):
        """Test creating manual signal."""
        # Act
        signal = Signal.create_manual_signal(
            user_id=456,
            symbol="ETHUSDT",
            side="sell",
            trade_type="spot",
            price=Decimal("3000"),
            size=Decimal("500"),
            priority=SignalPriority.MEDIUM,
        )

        # Assert
        assert signal.whale_id is None
        assert signal.user_id == 456
        assert signal.source == SignalSource.MANUAL
        assert signal.status == SignalStatus.PENDING
        assert signal.priority == SignalPriority.MEDIUM
        assert signal.symbol == "ETHUSDT"
        assert signal.side == "sell"
        assert signal.trade_type == "spot"

        # Check domain event
        events = signal.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], SignalDetectedEvent)
        assert events[0].whale_id is None
        assert events[0].source == "manual"


class TestSignalProcessing:
    """Tests для Signal processing lifecycle."""

    def test_start_processing_success(self):
        """Test starting signal processing."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        signal.clear_domain_events()

        # Act
        signal.start_processing()

        # Assert
        assert signal.status == SignalStatus.PROCESSING

        # Check domain event
        events = signal.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], SignalProcessingStartedEvent)
        assert events[0].signal_id == (signal.id or 0)  # 0 for unpersisted signals
        assert events[0].symbol == "BTCUSDT"

    def test_start_processing_already_processing_raises_error(self):
        """Test starting processing on already processing signal raises error."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        signal.start_processing()

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot start processing"):
            signal.start_processing()

    def test_mark_processed_success(self):
        """Test marking signal as processed."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        signal.start_processing()
        signal.clear_domain_events()

        # Act
        signal.mark_processed(trades_executed=5)

        # Assert
        assert signal.status == SignalStatus.PROCESSED
        assert signal.trades_executed == 5
        assert signal.processed_at is not None

        # Check domain event
        events = signal.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], SignalProcessedEvent)
        assert events[0].signal_id == (signal.id or 0)  # 0 for unpersisted signals
        assert events[0].trades_executed == 5

    def test_mark_failed_success(self):
        """Test marking signal as failed."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        signal.start_processing()
        signal.clear_domain_events()

        # Act
        error_msg = "Exchange API failed"
        signal.mark_failed(error_msg)

        # Assert
        assert signal.status == SignalStatus.FAILED
        assert signal.error_message == error_msg
        assert signal.processed_at is not None

        # Check domain event
        events = signal.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], SignalFailedEvent)
        assert events[0].signal_id == (signal.id or 0)  # 0 for unpersisted signals
        assert events[0].error_message == error_msg

    def test_mark_expired_success(self):
        """Test marking signal as expired."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        # Act
        signal.mark_expired()

        # Assert
        assert signal.status == SignalStatus.EXPIRED
        assert signal.processed_at is not None


class TestSignalExpiry:
    """Tests для signal expiry logic."""

    def test_is_expired_false_for_new_signal(self):
        """Test is_expired returns False для нового signal."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        # Act & Assert
        assert signal.is_expired(expiry_seconds=60) is False

    def test_is_expired_true_for_old_signal(self):
        """Test is_expired returns True для старого signal."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        # Manually set detected_at to 2 minutes ago
        signal.detected_at = datetime.now(timezone.utc) - timedelta(minutes=2)

        # Act & Assert
        assert signal.is_expired(expiry_seconds=60) is True

    def test_is_expired_edge_case_exactly_at_threshold(self):
        """Test is_expired at exactly threshold."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        # Set detected_at to exactly 60 seconds ago
        signal.detected_at = datetime.now(timezone.utc) - timedelta(seconds=60)

        # Act & Assert - exactly at threshold should be expired
        assert signal.is_expired(expiry_seconds=60) is True


class TestSignalMetadata:
    """Tests для signal metadata handling."""

    def test_metadata_with_stop_loss_and_take_profit(self):
        """Test signal with SL/TP metadata."""
        # Arrange
        metadata = {
            "stop_loss_price": "49000",
            "take_profit_price": "52000",
            "strategy": "breakout",
        }

        # Act
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
            metadata=metadata,
        )

        # Assert
        assert signal.metadata == metadata
        assert signal.metadata["stop_loss_price"] == "49000"
        assert signal.metadata["take_profit_price"] == "52000"
        assert signal.metadata["strategy"] == "breakout"

    def test_metadata_none_by_default(self):
        """Test signal has empty metadata by default."""
        # Act
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        # Assert
        assert signal.metadata == {}


class TestSignalPriority:
    """Tests для SignalPriority value object."""

    def test_priority_ordering(self):
        """Test priority comparison (HIGH > MEDIUM > LOW)."""
        high = SignalPriority.HIGH
        medium = SignalPriority.MEDIUM
        low = SignalPriority.LOW

        # For priority queue, lower is better (higher priority)
        assert high < medium  # HIGH has higher priority
        assert medium < low  # MEDIUM has higher priority than LOW
        assert high < low


class TestSignalStatus:
    """Tests для SignalStatus value object."""

    def test_all_statuses_defined(self):
        """Test all signal statuses are defined."""
        assert SignalStatus.PENDING.value == "pending"
        assert SignalStatus.PROCESSING.value == "processing"
        assert SignalStatus.PROCESSED.value == "processed"
        assert SignalStatus.FAILED.value == "failed"
        assert SignalStatus.EXPIRED.value == "expired"


class TestSignalSource:
    """Tests для SignalSource value object."""

    def test_all_sources_defined(self):
        """Test all signal sources are defined."""
        assert SignalSource.WHALE.value == "whale"
        assert SignalSource.INDICATOR.value == "indicator"
        assert SignalSource.MANUAL.value == "manual"
        assert SignalSource.BOT.value == "bot"
        assert SignalSource.WEBHOOK.value == "webhook"
