"""Tests for SignalQueue domain service."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.signals.entities import Signal
from app.domain.signals.repositories import SignalRepository
from app.domain.signals.services import SignalQueue
from app.domain.signals.value_objects import SignalPriority, SignalStatus


@pytest.fixture
def mock_signal_repository():
    """Create mock SignalRepository."""
    return AsyncMock(spec=SignalRepository)


@pytest.fixture
def signal_queue(mock_signal_repository):
    """Create SignalQueue with mock repository."""
    return SignalQueue(mock_signal_repository)


class TestSignalQueuePickNext:
    """Tests для SignalQueue.pick_next()."""

    @pytest.mark.asyncio
    async def test_pick_next_success(self, signal_queue, mock_signal_repository):
        """Test picking next signal from queue."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
            whale_tier="vip",
        )
        signal._id = 1  # Simulate persisted signal

        mock_signal_repository.get_pending_signals.return_value = [signal]
        mock_signal_repository.save = AsyncMock()

        # Act
        result = await signal_queue.pick_next()

        # Assert
        assert result is not None
        assert result.id == 1
        assert result.status == SignalStatus.PROCESSING
        mock_signal_repository.get_pending_signals.assert_called_once()
        mock_signal_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_next_empty_queue_returns_none(
        self, signal_queue, mock_signal_repository
    ):
        """Test pick_next returns None when queue empty."""
        # Arrange
        mock_signal_repository.get_pending_signals.return_value = []

        # Act
        result = await signal_queue.pick_next()

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_pick_next_filters_expired_signals(
        self, signal_queue, mock_signal_repository
    ):
        """Test pick_next filters out expired signals."""
        # Arrange
        expired_signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        expired_signal._id = 1
        # Make it 2 minutes old (expired)
        expired_signal.detected_at = datetime.now(timezone.utc) - timedelta(minutes=2)

        valid_signal = Signal.create_whale_signal(
            whale_id=456,
            symbol="ETHUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("3000"),
            size=Decimal("500"),
        )
        valid_signal._id = 2

        mock_signal_repository.get_pending_signals.return_value = [
            expired_signal,
            valid_signal,
        ]
        mock_signal_repository.save = AsyncMock()

        # Act
        result = await signal_queue.pick_next()

        # Assert - should pick valid signal, skip expired
        assert result is not None
        assert result.id == 2
        assert result.status == SignalStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_pick_next_respects_priority_filter(
        self, signal_queue, mock_signal_repository
    ):
        """Test pick_next respects min_priority filter."""
        # Arrange
        mock_signal_repository.get_pending_signals.return_value = []

        # Act
        await signal_queue.pick_next(min_priority=SignalPriority.HIGH)

        # Assert - check repository called with correct filter
        mock_signal_repository.get_pending_signals.assert_called_once_with(
            limit=10, min_priority=SignalPriority.HIGH
        )

    @pytest.mark.asyncio
    async def test_pick_next_handles_save_error(
        self, signal_queue, mock_signal_repository
    ):
        """Test pick_next handles save error gracefully."""
        # Arrange
        signal = Signal.create_whale_signal(
            whale_id=123,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        signal._id = 1

        mock_signal_repository.get_pending_signals.return_value = [signal]
        mock_signal_repository.save = AsyncMock(side_effect=Exception("DB error"))

        # Act
        result = await signal_queue.pick_next()

        # Assert - should return None on error
        assert result is None


class TestSignalQueueMarkProcessed:
    """Tests для SignalQueue.mark_processed()."""

    @pytest.mark.asyncio
    async def test_mark_processed_success(self, signal_queue, mock_signal_repository):
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
        signal._id = 1
        signal.start_processing()

        mock_signal_repository.get_by_id.return_value = signal
        mock_signal_repository.save = AsyncMock()

        # Act
        await signal_queue.mark_processed(signal_id=1, trades_executed=5)

        # Assert
        assert signal.status == SignalStatus.PROCESSED
        assert signal.trades_executed == 5
        mock_signal_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_processed_signal_not_found_raises_error(
        self, signal_queue, mock_signal_repository
    ):
        """Test mark_processed raises error if signal not found."""
        # Arrange
        mock_signal_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Signal 999 not found"):
            await signal_queue.mark_processed(signal_id=999, trades_executed=5)


class TestSignalQueueMarkFailed:
    """Tests для SignalQueue.mark_failed()."""

    @pytest.mark.asyncio
    async def test_mark_failed_success(self, signal_queue, mock_signal_repository):
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
        signal._id = 1
        signal.start_processing()

        mock_signal_repository.get_by_id.return_value = signal
        mock_signal_repository.save = AsyncMock()

        # Act
        error_msg = "Exchange API failed"
        await signal_queue.mark_failed(signal_id=1, error_message=error_msg)

        # Assert
        assert signal.status == SignalStatus.FAILED
        assert signal.error_message == error_msg
        mock_signal_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed_signal_not_found_raises_error(
        self, signal_queue, mock_signal_repository
    ):
        """Test mark_failed raises error if signal not found."""
        # Arrange
        mock_signal_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Signal 999 not found"):
            await signal_queue.mark_failed(signal_id=999, error_message="Error")


class TestSignalQueueGetQueueSize:
    """Tests для SignalQueue.get_queue_size()."""

    @pytest.mark.asyncio
    async def test_get_queue_size_all_priorities(
        self, signal_queue, mock_signal_repository
    ):
        """Test getting total queue size."""
        # Arrange
        signals = [
            Signal.create_whale_signal(
                whale_id=i,
                symbol="BTCUSDT",
                side="buy",
                trade_type="futures",
                price=Decimal("50000"),
                size=Decimal("1000"),
            )
            for i in range(5)
        ]
        mock_signal_repository.get_pending_signals.return_value = signals

        # Act
        size = await signal_queue.get_queue_size()

        # Assert
        assert size == 5

    @pytest.mark.asyncio
    async def test_get_queue_size_filtered_by_priority(
        self, signal_queue, mock_signal_repository
    ):
        """Test getting queue size for specific priority."""
        # Arrange
        high_signal = Signal.create_whale_signal(
            whale_id=1,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
            whale_tier="vip",
        )
        medium_signal = Signal.create_whale_signal(
            whale_id=2,
            symbol="ETHUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("3000"),
            size=Decimal("500"),
            whale_tier="premium",
        )

        mock_signal_repository.get_pending_signals.return_value = [
            high_signal,
            medium_signal,
        ]

        # Act
        size = await signal_queue.get_queue_size(priority=SignalPriority.HIGH)

        # Assert
        assert size == 1  # Only high priority signal


class TestSignalQueueCleanupExpired:
    """Tests для SignalQueue.cleanup_expired()."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_success(self, signal_queue, mock_signal_repository):
        """Test cleaning up expired signals."""
        # Arrange
        expired_signal_1 = Signal.create_whale_signal(
            whale_id=1,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        expired_signal_1._id = 1
        expired_signal_1.detected_at = datetime.now(timezone.utc) - timedelta(minutes=2)

        expired_signal_2 = Signal.create_whale_signal(
            whale_id=2,
            symbol="ETHUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("3000"),
            size=Decimal("500"),
        )
        expired_signal_2._id = 2
        expired_signal_2.detected_at = datetime.now(timezone.utc) - timedelta(minutes=3)

        mock_signal_repository.get_expired_pending_signals.return_value = [
            expired_signal_1,
            expired_signal_2,
        ]
        mock_signal_repository.save = AsyncMock()

        # Act
        count = await signal_queue.cleanup_expired(expiry_seconds=60)

        # Assert
        assert count == 2
        assert expired_signal_1.status == SignalStatus.EXPIRED
        assert expired_signal_2.status == SignalStatus.EXPIRED
        assert mock_signal_repository.save.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired_no_expired_signals(
        self, signal_queue, mock_signal_repository
    ):
        """Test cleanup when no expired signals."""
        # Arrange
        mock_signal_repository.get_expired_pending_signals.return_value = []

        # Act
        count = await signal_queue.cleanup_expired(expiry_seconds=60)

        # Assert
        assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_handles_save_error(
        self, signal_queue, mock_signal_repository
    ):
        """Test cleanup handles save error gracefully."""
        # Arrange
        expired_signal = Signal.create_whale_signal(
            whale_id=1,
            symbol="BTCUSDT",
            side="buy",
            trade_type="futures",
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        expired_signal._id = 1

        mock_signal_repository.get_expired_pending_signals.return_value = [
            expired_signal
        ]
        mock_signal_repository.save = AsyncMock(side_effect=Exception("DB error"))

        # Act
        count = await signal_queue.cleanup_expired(expiry_seconds=60)

        # Assert - should return 0 due to error
        assert count == 0
