"""Tests для Domain Events.

Перевіряємо що aggregates правильно emit events.
"""

import pytest
from decimal import Decimal

from app.domain.trading.entities import Position, Trade
from app.domain.trading.events.position_events import (
    PositionClosedEvent,
    PositionLiquidatedEvent,
    PositionOpenedEvent,
)
from app.domain.trading.events.trade_events import (
    TradeExecutedEvent,
    TradeFailedEvent,
    TradeNeedsReconciliationEvent,
)
from app.domain.trading.value_objects import PositionSide, TradeSide, TradeType


class TestTradeEvents:
    """Tests для Trade domain events."""

    def test_trade_emits_executed_event(self):
        """Test: Trade emits TradeExecutedEvent коли execute()."""
        # Arrange
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("100"),
            quantity=Decimal("0.002"),
        )

        # Act
        trade.execute(
            exchange_order_id="12345",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.002"),
            fee_amount=Decimal("0.1"),
        )

        # Assert
        events = trade.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], TradeExecutedEvent)

        event = events[0]
        assert event.trade_id == (trade.id or 0)
        assert event.user_id == 1
        assert event.signal_id == 100
        assert event.symbol == "BTCUSDT"
        assert event.side == "buy"
        assert event.executed_price == Decimal("50000")
        assert event.executed_quantity == Decimal("0.002")
        assert event.fee_amount == Decimal("0.1")
        assert event.exchange_order_id == "12345"

    def test_trade_emits_failed_event(self):
        """Test: Trade emits TradeFailedEvent коли fail()."""
        # Arrange
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("100"),
            quantity=Decimal("0.002"),
        )

        # Act
        trade.fail("Insufficient balance")

        # Assert
        events = trade.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], TradeFailedEvent)

        event = events[0]
        assert event.trade_id == (trade.id or 0)
        assert event.user_id == 1
        assert event.symbol == "BTCUSDT"
        assert event.error_message == "Insufficient balance"

    def test_trade_emits_reconciliation_event(self):
        """Test: Trade emits TradeNeedsReconciliationEvent."""
        # Arrange
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("100"),
            quantity=Decimal("0.002"),
        )

        # Act
        trade.mark_needs_reconciliation("DB commit failed after exchange success")

        # Assert
        events = trade.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], TradeNeedsReconciliationEvent)

        event = events[0]
        assert event.reason == "DB commit failed after exchange success"


class TestPositionEvents:
    """Tests для Position domain events."""

    def test_position_emits_opened_event(self):
        """Test: Position emits PositionOpenedEvent при створенні."""
        # Act
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            leverage=10,
            stop_loss_price=Decimal("49000"),
            take_profit_price=Decimal("52000"),
        )

        # Assert
        events = position.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], PositionOpenedEvent)

        event = events[0]
        assert event.position_id == (position.id or 0)
        assert event.user_id == 1
        assert event.symbol == "BTCUSDT"
        assert event.side == "long"
        assert event.entry_price == Decimal("50000")
        assert event.quantity == Decimal("0.1")
        assert event.leverage == 10
        assert event.entry_trade_id == 123

    def test_position_emits_closed_event(self):
        """Test: Position emits PositionClosedEvent коли close()."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Clear initial event
        position.clear_domain_events()

        # Act
        position.close(exit_price=Decimal("52000"), exit_trade_id=456)

        # Assert
        events = position.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], PositionClosedEvent)

        event = events[0]
        assert event.position_id == (position.id or 0)
        assert event.user_id == 1
        assert event.symbol == "BTCUSDT"
        assert event.side == "long"
        assert event.entry_price == Decimal("50000")
        assert event.exit_price == Decimal("52000")
        assert event.quantity == Decimal("0.1")
        assert event.realized_pnl == Decimal("200")  # (52000 - 50000) * 0.1
        assert event.exit_trade_id == 456

    def test_position_emits_liquidated_event(self):
        """Test: Position emits PositionLiquidatedEvent коли liquidate()."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            leverage=10,
        )

        # Clear initial event
        position.clear_domain_events()

        # Act
        position.liquidate(liquidation_price=Decimal("45000"))

        # Assert
        events = position.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], PositionLiquidatedEvent)

        event = events[0]
        assert event.position_id == (position.id or 0)
        assert event.user_id == 1
        assert event.symbol == "BTCUSDT"
        assert event.liquidation_price == Decimal("45000")
        # PnL = (45000 - 50000) * 0.1 * 10 = -5000 (total loss with 10x leverage)
        assert event.realized_pnl == Decimal("-5000")

    def test_position_no_event_on_direct_init(self):
        """Test: Position НЕ emit event при direct __init__ (restore з DB)."""
        # Act - direct init (як при restore з DB)
        position = Position(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            id=999,  # Existing position
        )

        # Assert - NO events
        events = position.get_domain_events()
        assert len(events) == 0


class TestEventBusIntegration:
    """Integration tests для Event Bus."""

    @pytest.mark.asyncio
    async def test_event_bus_publishes_to_subscribers(self):
        """Test: Event bus викликає subscribers."""
        from app.infrastructure.messaging import get_event_bus, reset_event_bus

        # Reset event bus
        reset_event_bus()
        event_bus = get_event_bus()

        # Track calls
        calls = []

        async def handler(event: TradeExecutedEvent):
            calls.append(("handler", event))

        async def handler2(event: TradeExecutedEvent):
            calls.append(("handler2", event))

        # Subscribe handlers
        event_bus.subscribe(TradeExecutedEvent, handler)
        event_bus.subscribe(TradeExecutedEvent, handler2)

        # Create trade and execute
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("100"),
            quantity=Decimal("0.002"),
        )

        trade.execute(
            exchange_order_id="12345",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.002"),
            fee_amount=Decimal("0.1"),
        )

        # Publish events
        events = trade.get_domain_events()
        await event_bus.publish_all(events)

        # Assert both handlers called
        assert len(calls) == 2
        assert calls[0][0] == "handler"
        assert calls[1][0] == "handler2"
        assert isinstance(calls[0][1], TradeExecutedEvent)

    @pytest.mark.asyncio
    async def test_event_bus_handles_handler_failures(self):
        """Test: Event bus продовжує роботу навіть якщо handler failed."""
        from app.infrastructure.messaging import get_event_bus, reset_event_bus

        reset_event_bus()
        event_bus = get_event_bus()

        calls = []

        async def failing_handler(event: TradeExecutedEvent):
            raise Exception("Handler error")

        async def working_handler(event: TradeExecutedEvent):
            calls.append("working")

        # Subscribe both
        event_bus.subscribe(TradeExecutedEvent, failing_handler)
        event_bus.subscribe(TradeExecutedEvent, working_handler)

        # Publish event
        event = TradeExecutedEvent(
            trade_id=1,
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side="buy",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.002"),
            fee_amount=Decimal("0.1"),
            exchange_order_id="12345",
        )

        await event_bus.publish(event)

        # Assert working handler still called despite failing handler
        assert "working" in calls
