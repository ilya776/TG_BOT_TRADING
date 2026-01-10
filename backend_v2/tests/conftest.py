"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_trade_data():
    """Sample data для створення trades в tests."""
    from decimal import Decimal

    from app.domain.trading.value_objects import TradeSide, TradeType

    return {
        "user_id": 1,
        "signal_id": 100,
        "symbol": "BTCUSDT",
        "side": TradeSide.BUY,
        "trade_type": TradeType.SPOT,
        "size_usdt": Decimal("100"),
        "quantity": Decimal("0.002"),
        "leverage": 1,
    }


@pytest.fixture
def sample_order_result():
    """Sample OrderResult для tests."""
    from decimal import Decimal

    from app.domain.exchanges.value_objects import OrderResult, OrderStatus

    return OrderResult(
        order_id="BINANCE-123456",
        status=OrderStatus.FILLED,
        symbol="BTCUSDT",
        filled_quantity=Decimal("0.002"),
        avg_fill_price=Decimal("50000"),
        total_cost=Decimal("100"),
        fee_amount=Decimal("0.1"),
    )
