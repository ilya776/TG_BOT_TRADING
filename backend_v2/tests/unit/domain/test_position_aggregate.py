"""Unit tests для Position Aggregate.

Pure unit tests - тільки business logic, zero dependencies.
"""

import pytest
from decimal import Decimal

from app.domain.trading.entities import Position
from app.domain.trading.exceptions import PositionAlreadyClosedError
from app.domain.trading.value_objects import PositionSide, PositionStatus


class TestPositionCreation:
    """Tests для створення Position."""

    def test_create_long_position(self):
        """Test: Можна створити LONG position."""
        # Arrange & Act
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Assert
        assert position.side == PositionSide.LONG
        assert position.status == PositionStatus.OPEN
        assert position.is_open is True
        assert position.entry_price == Decimal("50000")
        assert position.quantity == Decimal("0.1")
        assert position.unrealized_pnl == Decimal("0")

    def test_create_short_position(self):
        """Test: Можна створити SHORT position."""
        # Arrange & Act
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Assert
        assert position.side == PositionSide.SHORT
        assert position.status == PositionStatus.OPEN


class TestPositionPnLCalculation:
    """Tests для PnL розрахунків."""

    def test_long_position_profit(self):
        """Test: LONG position profitable коли ціна зростає."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Act - ціна зросла до 51000
        current_price = Decimal("51000")
        pnl = position.update_unrealized_pnl(current_price)

        # Assert
        # PnL = (51000 - 50000) * 0.1 = 100 USDT
        assert pnl == Decimal("100")
        assert position.unrealized_pnl == Decimal("100")
        assert position.is_profitable is True

    def test_long_position_loss(self):
        """Test: LONG position у збитку коли ціна падає."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Act - ціна впала до 49000
        current_price = Decimal("49000")
        pnl = position.update_unrealized_pnl(current_price)

        # Assert
        # PnL = (49000 - 50000) * 0.1 = -100 USDT
        assert pnl == Decimal("-100")
        assert position.is_profitable is False

    def test_short_position_profit(self):
        """Test: SHORT position profitable коли ціна падає."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Act - ціна впала до 49000 (добре для short)
        current_price = Decimal("49000")
        pnl = position.update_unrealized_pnl(current_price)

        # Assert
        # PnL = (50000 - 49000) * 0.1 = 100 USDT (short profits from price drop)
        assert pnl == Decimal("100")
        assert position.is_profitable is True

    def test_short_position_loss(self):
        """Test: SHORT position у збитку коли ціна зростає."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Act - ціна зросла до 51000 (погано для short)
        current_price = Decimal("51000")
        pnl = position.update_unrealized_pnl(current_price)

        # Assert
        # PnL = (50000 - 51000) * 0.1 = -100 USDT
        assert pnl == Decimal("-100")
        assert position.is_profitable is False

    def test_leverage_multiplies_pnl(self):
        """Test: Leverage збільшує PnL (profit та loss)."""
        # Arrange - 10x leverage
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            leverage=10,
        )

        # Act
        current_price = Decimal("51000")
        pnl = position.update_unrealized_pnl(current_price)

        # Assert
        # PnL = (51000 - 50000) * 0.1 * 10 = 1000 USDT (10x leverage)
        assert pnl == Decimal("1000")


class TestStopLoss:
    """Tests для stop-loss logic."""

    def test_long_stop_loss_triggered(self):
        """Test: LONG stop-loss triggers коли ціна падає нижче SL."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            stop_loss_price=Decimal("49000"),  # SL at 49000
        )

        # Act & Assert
        assert position.should_trigger_stop_loss(Decimal("49000")) is True
        assert position.should_trigger_stop_loss(Decimal("48500")) is True
        assert position.should_trigger_stop_loss(Decimal("49500")) is False

    def test_short_stop_loss_triggered(self):
        """Test: SHORT stop-loss triggers коли ціна зростає вище SL."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            stop_loss_price=Decimal("51000"),  # SL at 51000
        )

        # Act & Assert
        assert position.should_trigger_stop_loss(Decimal("51000")) is True
        assert position.should_trigger_stop_loss(Decimal("51500")) is True
        assert position.should_trigger_stop_loss(Decimal("50500")) is False


class TestTakeProfit:
    """Tests для take-profit logic."""

    def test_long_take_profit_triggered(self):
        """Test: LONG take-profit triggers коли ціна зростає вище TP."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            take_profit_price=Decimal("52000"),  # TP at 52000
        )

        # Act & Assert
        assert position.should_trigger_take_profit(Decimal("52000")) is True
        assert position.should_trigger_take_profit(Decimal("53000")) is True
        assert position.should_trigger_take_profit(Decimal("51500")) is False

    def test_short_take_profit_triggered(self):
        """Test: SHORT take-profit triggers коли ціна падає нижче TP."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
            take_profit_price=Decimal("48000"),  # TP at 48000
        )

        # Act & Assert
        assert position.should_trigger_take_profit(Decimal("48000")) is True
        assert position.should_trigger_take_profit(Decimal("47000")) is True
        assert position.should_trigger_take_profit(Decimal("49000")) is False


class TestPositionClosure:
    """Tests для закриття position."""

    def test_close_position_with_profit(self):
        """Test: Position закривається з profit."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )

        # Act
        exit_price = Decimal("52000")
        realized_pnl = position.close(exit_price=exit_price, exit_trade_id=456)

        # Assert
        assert position.status == PositionStatus.CLOSED
        assert position.is_closed is True
        assert position.exit_price == Decimal("52000")
        assert position.exit_trade_id == 456
        # PnL = (52000 - 50000) * 0.1 = 200 USDT
        assert realized_pnl == Decimal("200")
        assert position.realized_pnl == Decimal("200")
        assert position.unrealized_pnl == Decimal("0")  # Cleared

    def test_cannot_update_pnl_for_closed_position(self):
        """Test: Не можна update PnL для закритої position."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )
        position.close(exit_price=Decimal("52000"), exit_trade_id=456)

        # Act & Assert
        with pytest.raises(PositionAlreadyClosedError):
            position.update_unrealized_pnl(Decimal("53000"))

    def test_cannot_close_already_closed_position(self):
        """Test: Не можна закрити вже закриту position."""
        # Arrange
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_trade_id=123,
        )
        position.close(exit_price=Decimal("52000"), exit_trade_id=456)

        # Act & Assert
        with pytest.raises(PositionAlreadyClosedError):
            position.close(exit_price=Decimal("53000"), exit_trade_id=789)


class TestPositionLiquidation:
    """Tests для liquidation."""

    def test_liquidate_position(self):
        """Test: Position може бути ліквідована."""
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

        # Act - liquidation ціна = entry - margin
        liquidation_price = Decimal("45000")
        position.liquidate(liquidation_price)

        # Assert
        assert position.status == PositionStatus.LIQUIDATED
        assert position.is_liquidated is True
        assert position.exit_price == liquidation_price
        # PnL = (45000 - 50000) * 0.1 * 10 = -5000 USDT (total loss)
        assert position.realized_pnl == Decimal("-5000")
