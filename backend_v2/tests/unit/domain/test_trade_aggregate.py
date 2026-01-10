"""Unit tests для Trade Aggregate.

Це PURE unit tests - тестують тільки business logic, без DB, без exchange APIs.
Не потрібні mock objects бо domain logic не має dependencies!
"""

import pytest
from decimal import Decimal

from app.domain.trading.entities import Trade
from app.domain.trading.exceptions import InvalidTradeStateError, InvalidTradeSizeError
from app.domain.trading.value_objects import TradeSide, TradeStatus, TradeType


class TestTradeCreation:
    """Tests для створення Trade."""

    def test_create_copy_trade_success(self, sample_trade_data):
        """Test: Можна створити trade з valid parameters."""
        # Arrange & Act
        trade = Trade.create_copy_trade(**sample_trade_data)

        # Assert
        assert trade.user_id == sample_trade_data["user_id"]
        assert trade.signal_id == sample_trade_data["signal_id"]
        assert trade.symbol == sample_trade_data["symbol"]
        assert trade.status == TradeStatus.PENDING
        assert trade.is_pending is True
        assert trade.id is None  # Not saved yet

    def test_create_trade_with_negative_size_fails(self, sample_trade_data):
        """Test: Не можна створити trade з negative size."""
        # Arrange
        sample_trade_data["size_usdt"] = Decimal("-100")

        # Act & Assert
        with pytest.raises(InvalidTradeSizeError) as exc_info:
            Trade.create_copy_trade(**sample_trade_data)

        assert "must be positive" in str(exc_info.value)

    def test_create_trade_with_zero_size_fails(self, sample_trade_data):
        """Test: Не можна створити trade з zero size."""
        # Arrange
        sample_trade_data["size_usdt"] = Decimal("0")

        # Act & Assert
        with pytest.raises(InvalidTradeSizeError):
            Trade.create_copy_trade(**sample_trade_data)


class TestTradeExecution:
    """Tests для execution flow (2-phase commit)."""

    def test_execute_pending_trade_success(self, sample_trade_data, sample_order_result):
        """Test: Pending trade можна успішно execute."""
        # Arrange
        trade = Trade.create_copy_trade(**sample_trade_data)
        assert trade.status == TradeStatus.PENDING

        # Act
        trade.execute(
            exchange_order_id=sample_order_result.order_id,
            executed_price=sample_order_result.avg_fill_price,
            executed_quantity=sample_order_result.filled_quantity,
            fee_amount=sample_order_result.fee_amount,
        )

        # Assert
        assert trade.status == TradeStatus.FILLED
        assert trade.is_filled is True
        assert trade.is_final_state is True
        assert trade.exchange_order_id == sample_order_result.order_id
        assert trade.executed_price == sample_order_result.avg_fill_price
        assert trade.executed_at is not None

    def test_execute_already_filled_trade_fails(self, sample_trade_data, sample_order_result):
        """Test: Не можна execute trade який вже FILLED."""
        # Arrange
        trade = Trade.create_copy_trade(**sample_trade_data)
        trade.execute(
            exchange_order_id="ORDER1",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.002"),
            fee_amount=Decimal("0.1"),
        )
        assert trade.status == TradeStatus.FILLED

        # Act & Assert
        with pytest.raises(InvalidTradeStateError) as exc_info:
            trade.execute(
                exchange_order_id="ORDER2",
                executed_price=Decimal("51000"),
                executed_quantity=Decimal("0.002"),
                fee_amount=Decimal("0.1"),
            )

        assert "invalid status" in str(exc_info.value).lower()
        assert exc_info.value.context["current_status"] == TradeStatus.FILLED.value


class TestTradeFailure:
    """Tests для failure handling."""

    def test_fail_pending_trade_success(self, sample_trade_data):
        """Test: Pending trade можна mark як failed."""
        # Arrange
        trade = Trade.create_copy_trade(**sample_trade_data)
        error_message = "Insufficient balance on exchange"

        # Act
        trade.fail(error_message)

        # Assert
        assert trade.status == TradeStatus.FAILED
        assert trade.is_failed is True
        assert trade.is_final_state is True
        assert trade.error_message == error_message
        assert trade.executed_at is not None

    def test_fail_already_filled_trade_fails(self, sample_trade_data):
        """Test: Не можна fail trade який вже FILLED."""
        # Arrange
        trade = Trade.create_copy_trade(**sample_trade_data)
        trade.execute(
            exchange_order_id="ORDER1",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.002"),
            fee_amount=Decimal("0.1"),
        )

        # Act & Assert
        with pytest.raises(InvalidTradeStateError):
            trade.fail("Some error")


class TestTradeReconciliation:
    """Tests для reconciliation logic."""

    def test_mark_needs_reconciliation(self, sample_trade_data):
        """Test: Trade можна mark для reconciliation."""
        # Arrange
        trade = Trade.create_copy_trade(**sample_trade_data)
        reason = "Exchange call succeeded but DB update failed"

        # Act
        trade.mark_needs_reconciliation(reason)

        # Assert
        assert trade.status == TradeStatus.NEEDS_RECONCILIATION
        assert trade.needs_reconciliation is True
        assert reason in trade.error_message


class TestTradeEquality:
    """Tests для entity equality (порівнюється за ID)."""

    def test_trades_with_same_id_are_equal(self, sample_trade_data):
        """Test: Trades з однаковим ID рівні (навіть якщо різні атрибути)."""
        # Arrange
        trade1 = Trade.create_copy_trade(**sample_trade_data)
        trade1._id = 1

        sample_trade_data["size_usdt"] = Decimal("200")  # Різний size
        trade2 = Trade.create_copy_trade(**sample_trade_data)
        trade2._id = 1  # Але той самий ID

        # Assert
        assert trade1 == trade2

    def test_trades_with_different_ids_are_not_equal(self, sample_trade_data):
        """Test: Trades з різними ID не рівні (навіть якщо однакові атрибути)."""
        # Arrange
        trade1 = Trade.create_copy_trade(**sample_trade_data)
        trade1._id = 1

        trade2 = Trade.create_copy_trade(**sample_trade_data)
        trade2._id = 2  # Різний ID

        # Assert
        assert trade1 != trade2
