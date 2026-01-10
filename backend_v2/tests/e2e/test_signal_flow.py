"""End-to-end tests for complete signal processing flow.

Tests the full signal processing pipeline:
    Signal Detection → Queue → Processing → Trade Execution → Position

These tests require database and can be run with pytest --e2e flag.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.signals import ProcessSignalCommand, ProcessSignalHandler
from app.application.trading.handlers import ExecuteCopyTradeHandler
from app.domain.signals.entities import Signal
from app.domain.signals.services import SignalQueue
from app.domain.signals.value_objects import (
    SignalPriority,
    SignalStatus,
    SignalType,
    TradeSide,
)
from app.domain.trading.entities import Trade, Position
from app.domain.trading.value_objects import TradeStatus


@pytest.fixture
def mock_uow():
    """Create mock Unit of Work."""
    uow = MagicMock()
    uow.signals = MagicMock()
    uow.trades = MagicMock()
    uow.positions = MagicMock()
    uow.whale_follows = MagicMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()

    # Make it work as async context manager
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    return uow


@pytest.fixture
def mock_exchange_factory():
    """Create mock exchange factory."""
    factory = MagicMock()
    exchange = MagicMock()

    # Mock successful order execution
    order_result = MagicMock()
    order_result.order_id = "123456"
    order_result.filled_quantity = Decimal("0.1")
    order_result.avg_price = Decimal("50000")
    order_result.fee = Decimal("0.01")
    order_result.success = True

    exchange.execute_spot_buy = AsyncMock(return_value=order_result)
    exchange.execute_spot_sell = AsyncMock(return_value=order_result)
    factory.create = MagicMock(return_value=exchange)

    return factory


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock()
    return event_bus


@pytest.fixture
def sample_signal():
    """Create sample signal for testing."""
    return Signal.create_whale_signal(
        whale_id=1,
        whale_tier="vip",  # HIGH priority
        symbol="BTCUSDT",
        side=TradeSide.BUY,
        signal_type=SignalType.SPOT,
        price=Decimal("50000"),
        size=Decimal("10000"),
    )


class TestSignalProcessingFlow:
    """Tests for complete signal processing flow."""

    @pytest.mark.asyncio
    async def test_signal_lifecycle(self, sample_signal):
        """Test signal status transitions."""
        # 1. Signal starts as PENDING
        assert sample_signal.status == SignalStatus.PENDING
        assert sample_signal.priority == SignalPriority.HIGH

        # 2. Start processing
        sample_signal.start_processing()
        assert sample_signal.status == SignalStatus.PROCESSING

        # 3. Mark as processed
        sample_signal.mark_processed(trades_executed=5)
        assert sample_signal.status == SignalStatus.PROCESSED
        assert sample_signal.trades_executed == 5
        assert sample_signal.processed_at is not None

    @pytest.mark.asyncio
    async def test_signal_can_fail(self, sample_signal):
        """Test signal failure handling."""
        sample_signal.start_processing()
        sample_signal.mark_failed(error="Exchange API error")

        assert sample_signal.status == SignalStatus.FAILED
        assert sample_signal.error_message == "Exchange API error"

    @pytest.mark.asyncio
    async def test_signal_can_expire(self, sample_signal):
        """Test signal expiration."""
        sample_signal.mark_expired()

        assert sample_signal.status == SignalStatus.EXPIRED


class TestSignalQueueProcessing:
    """Tests for SignalQueue domain service."""

    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self, mock_uow):
        """Test basic queue operations."""
        queue = SignalQueue(mock_uow.signals)

        # Setup mock
        signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="vip",
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        # Mock save and get_pending
        mock_uow.signals.save = AsyncMock()
        mock_uow.signals.get_pending_signals = AsyncMock(return_value=[signal])

        # Enqueue
        await queue.enqueue(signal)
        mock_uow.signals.save.assert_called_once_with(signal)

        # Dequeue
        mock_uow.signals.get_pending_signals = AsyncMock(return_value=[signal])
        dequeued = await queue.dequeue()

        assert dequeued is not None
        assert dequeued.status == SignalStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_queue_respects_priority(self, mock_uow):
        """Test that queue returns high priority signals first."""
        queue = SignalQueue(mock_uow.signals)

        high_priority = Signal.create_whale_signal(
            whale_id=1, whale_tier="vip", symbol="BTCUSDT", side=TradeSide.BUY,
            signal_type=SignalType.SPOT, price=Decimal("50000"), size=Decimal("1000"),
        )
        low_priority = Signal.create_whale_signal(
            whale_id=2, whale_tier="regular", symbol="ETHUSDT", side=TradeSide.BUY,
            signal_type=SignalType.SPOT, price=Decimal("3000"), size=Decimal("500"),
        )

        # Mock returns HIGH priority first
        mock_uow.signals.get_pending_signals = AsyncMock(
            return_value=[high_priority, low_priority]
        )
        mock_uow.signals.save = AsyncMock()

        dequeued = await queue.dequeue()

        assert dequeued.priority == SignalPriority.HIGH


class TestProcessSignalHandler:
    """Tests for ProcessSignalHandler use case."""

    @pytest.mark.asyncio
    async def test_process_signal_with_no_signals(
        self, mock_uow, mock_exchange_factory, mock_event_bus
    ):
        """Test handler when queue is empty."""
        # Empty queue
        mock_uow.signals.get_pending_signals = AsyncMock(return_value=[])

        queue = SignalQueue(mock_uow.signals)
        trade_handler = ExecuteCopyTradeHandler(
            uow=mock_uow,
            exchange_factory=mock_exchange_factory,
            event_bus=mock_event_bus,
        )

        handler = ProcessSignalHandler(
            uow=mock_uow,
            signal_queue=queue,
            whale_follow_repo=mock_uow.whale_follows,
            trade_handler=trade_handler,
            event_bus=mock_event_bus,
        )

        command = ProcessSignalCommand(min_priority=SignalPriority.LOW)
        result = await handler.handle(command)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_signal_success(
        self, mock_uow, mock_exchange_factory, mock_event_bus, sample_signal
    ):
        """Test successful signal processing."""
        # Mock queue with signal
        mock_uow.signals.get_pending_signals = AsyncMock(return_value=[sample_signal])
        mock_uow.signals.save = AsyncMock()

        # Mock followers (users who copy this whale)
        mock_follower = MagicMock()
        mock_follower.user_id = 1
        mock_follower.whale_id = 1
        mock_follower.copy_trade_size_usdt = Decimal("100")
        mock_follower.max_leverage = 10
        mock_follower.exchange_name = "binance"

        mock_uow.whale_follows.get_active_followers = AsyncMock(
            return_value=[mock_follower]
        )

        # Mock trade save
        mock_uow.trades.save = AsyncMock()

        queue = SignalQueue(mock_uow.signals)
        trade_handler = ExecuteCopyTradeHandler(
            uow=mock_uow,
            exchange_factory=mock_exchange_factory,
            event_bus=mock_event_bus,
        )

        handler = ProcessSignalHandler(
            uow=mock_uow,
            signal_queue=queue,
            whale_follow_repo=mock_uow.whale_follows,
            trade_handler=trade_handler,
            event_bus=mock_event_bus,
        )

        command = ProcessSignalCommand(min_priority=SignalPriority.LOW)
        result = await handler.handle(command)

        assert result is not None
        assert result.successful_trades >= 0

        # Verify signal was saved
        mock_uow.signals.save.assert_called()


class TestDomainEvents:
    """Tests for domain event emission during signal processing."""

    @pytest.mark.asyncio
    async def test_signal_creates_domain_events(self, sample_signal):
        """Test that signals emit domain events."""
        # Process signal
        sample_signal.start_processing()
        sample_signal.mark_processed(trades_executed=5)

        # Get domain events
        events = sample_signal.get_domain_events()

        # Should have events for detection and processing
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_trade_creates_domain_events(self):
        """Test that trades emit domain events."""
        trade = Trade.create_pending(
            user_id=1,
            signal_id=1,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=SignalType.SPOT,
            size_usdt=Decimal("100"),
            quantity=Decimal("0.002"),
        )

        # Execute trade
        trade.execute(
            order_id="123",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.002"),
            fee=Decimal("0.01"),
        )

        events = trade.get_domain_events()
        assert len(events) >= 1


class TestCompleteFlow:
    """Complete end-to-end signal flow tests."""

    @pytest.mark.asyncio
    async def test_whale_signal_to_trade_flow(self):
        """Test complete flow: whale signal → queue → trade."""
        # 1. Whale makes a trade → Signal detected
        signal = Signal.create_whale_signal(
            whale_id=42,
            whale_tier="vip",
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("50000"),
            size=Decimal("10000"),  # $10k whale trade
        )

        assert signal.status == SignalStatus.PENDING
        assert signal.priority == SignalPriority.HIGH  # VIP whale
        assert len(signal.get_domain_events()) == 1  # SignalDetected event

        # 2. Signal enters processing
        signal.start_processing()
        assert signal.status == SignalStatus.PROCESSING

        # 3. For each follower, create trade
        follower_trade = Trade.create_pending(
            user_id=1,  # Follower
            signal_id=signal.id or 0,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=SignalType.SPOT,
            size_usdt=Decimal("100"),  # Follower's trade size
            quantity=Decimal("0.002"),
        )

        assert follower_trade.status == TradeStatus.PENDING

        # 4. Execute trade on exchange
        follower_trade.execute(
            order_id="EX-123456",
            executed_price=Decimal("50050"),  # Slight slippage
            executed_quantity=Decimal("0.002"),
            fee=Decimal("0.0001"),
        )

        assert follower_trade.status == TradeStatus.FILLED
        assert follower_trade.exchange_order_id == "EX-123456"

        # 5. Create position from trade
        position = Position.open_from_trade(follower_trade)

        assert position.status.value == "open"
        assert position.symbol == "BTCUSDT"
        assert position.entry_price == Decimal("50050")

        # 6. Mark signal as processed
        signal.mark_processed(trades_executed=1)

        assert signal.status == SignalStatus.PROCESSED
        assert signal.trades_executed == 1

        # 7. Verify domain events were created
        signal_events = signal.get_domain_events()
        trade_events = follower_trade.get_domain_events()
        position_events = position.get_domain_events()

        # All entities should have produced events
        assert len(signal_events) >= 1
        assert len(trade_events) >= 1
        assert len(position_events) >= 1
