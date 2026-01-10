"""Integration tests for TradeRepository."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.trading.entities import Trade
from app.domain.trading.value_objects import TradeSide, TradeStatus, TradeType
from app.infrastructure.persistence.sqlalchemy.repositories import (
    SQLAlchemyTradeRepository,
)


class TestTradeRepository:
    """Integration tests для TradeRepository."""

    @pytest.mark.asyncio
    async def test_save_new_trade(self, session):
        """Test saving new trade (INSERT)."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )

        # Act
        await repo.save(trade)
        await session.commit()

        # Assert
        assert trade.id is not None  # ID generated
        saved_trade = await repo.get_by_id(trade.id)
        assert saved_trade is not None
        assert saved_trade.user_id == 1
        assert saved_trade.symbol == "BTCUSDT"
        assert saved_trade.side == TradeSide.BUY
        assert saved_trade.status == TradeStatus.PENDING

    @pytest.mark.asyncio
    async def test_save_existing_trade(self, session):
        """Test updating existing trade (UPDATE)."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )
        await repo.save(trade)
        await session.commit()

        # Act: Execute trade
        trade.execute(
            exchange_order_id="ORDER123",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.02"),
            fee_amount=Decimal("0.5"),
        )
        await repo.save(trade)
        await session.commit()

        # Assert
        updated_trade = await repo.get_by_id(trade.id)
        assert updated_trade is not None
        assert updated_trade.status == TradeStatus.FILLED
        assert updated_trade.exchange_order_id == "ORDER123"
        assert updated_trade.executed_price == Decimal("50000")

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, session):
        """Test get_by_id returns None якщо trade не знайдено."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)

        # Act
        trade = await repo.get_by_id(9999)

        # Assert
        assert trade is None

    @pytest.mark.asyncio
    async def test_get_pending_trades_for_user(self, session):
        """Test getting pending trades for user."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)

        # Create 3 trades: 2 PENDING, 1 FILLED
        trade1 = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )
        trade2 = Trade.create_copy_trade(
            user_id=1,
            signal_id=101,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("500"),
            quantity=Decimal("0.2"),
            leverage=1,
        )
        trade3 = Trade.create_copy_trade(
            user_id=1,
            signal_id=102,
            symbol="BNBUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("300"),
            quantity=Decimal("1.5"),
            leverage=1,
        )
        trade3.execute(
            exchange_order_id="ORDER123",
            executed_price=Decimal("200"),
            executed_quantity=Decimal("1.5"),
            fee_amount=Decimal("0.3"),
        )

        await repo.save(trade1)
        await repo.save(trade2)
        await repo.save(trade3)
        await session.commit()

        # Act
        pending_trades = await repo.get_pending_trades_for_user(user_id=1)

        # Assert
        assert len(pending_trades) == 2
        assert all(t.status == TradeStatus.PENDING for t in pending_trades)
        symbols = {t.symbol for t in pending_trades}
        assert symbols == {"BTCUSDT", "ETHUSDT"}

    @pytest.mark.asyncio
    async def test_get_trades_by_signal(self, session):
        """Test getting trades by signal ID."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)

        # Create 2 trades з одним signal_id
        trade1 = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )
        trade2 = Trade.create_copy_trade(
            user_id=2,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("500"),
            quantity=Decimal("0.01"),
            leverage=1,
        )
        trade3 = Trade.create_copy_trade(
            user_id=3,
            signal_id=200,  # Different signal
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("300"),
            quantity=Decimal("0.15"),
            leverage=1,
        )

        await repo.save(trade1)
        await repo.save(trade2)
        await repo.save(trade3)
        await session.commit()

        # Act
        signal_trades = await repo.get_trades_by_signal(signal_id=100)

        # Assert
        assert len(signal_trades) == 2
        assert all(t.signal_id == 100 for t in signal_trades)
        user_ids = {t.user_id for t in signal_trades}
        assert user_ids == {1, 2}

    @pytest.mark.asyncio
    async def test_get_trades_needing_reconciliation(self, session):
        """Test getting trades що потребують reconciliation."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)

        trade1 = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )
        trade1.mark_needs_reconciliation("Exchange timeout")

        trade2 = Trade.create_copy_trade(
            user_id=2,
            signal_id=101,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("500"),
            quantity=Decimal("0.2"),
            leverage=1,
        )
        # PENDING trade

        await repo.save(trade1)
        await repo.save(trade2)
        await session.commit()

        # Act
        reconciliation_trades = await repo.get_trades_needing_reconciliation()

        # Assert
        assert len(reconciliation_trades) == 1
        assert reconciliation_trades[0].status == TradeStatus.NEEDS_RECONCILIATION
        assert reconciliation_trades[0].symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_count_user_trades_today(self, session):
        """Test counting user trades today."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)

        # Create 2 trades today для user 1
        trade1 = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )
        trade2 = Trade.create_copy_trade(
            user_id=1,
            signal_id=101,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("500"),
            quantity=Decimal("0.2"),
            leverage=1,
        )

        # 1 trade для user 2
        trade3 = Trade.create_copy_trade(
            user_id=2,
            signal_id=102,
            symbol="BNBUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("300"),
            quantity=Decimal("1.5"),
            leverage=1,
        )

        await repo.save(trade1)
        await repo.save(trade2)
        await repo.save(trade3)
        await session.commit()

        # Act
        count_user1 = await repo.count_user_trades_today(user_id=1)
        count_user2 = await repo.count_user_trades_today(user_id=2)

        # Assert
        assert count_user1 == 2
        assert count_user2 == 1

    @pytest.mark.asyncio
    async def test_domain_events_cleared_after_load(self, session):
        """Test що domain events НЕ replay з DB."""
        # Arrange
        repo = SQLAlchemyTradeRepository(session)
        trade = Trade.create_copy_trade(
            user_id=1,
            signal_id=100,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            trade_type=TradeType.SPOT,
            size_usdt=Decimal("1000"),
            quantity=Decimal("0.02"),
            leverage=1,
        )
        trade.execute(
            exchange_order_id="ORDER123",
            executed_price=Decimal("50000"),
            executed_quantity=Decimal("0.02"),
            fee_amount=Decimal("0.5"),
        )

        # Trade has events
        assert len(trade.get_domain_events()) > 0

        # Save
        await repo.save(trade)
        await session.commit()

        # Act: Load from DB
        loaded_trade = await repo.get_by_id(trade.id)

        # Assert: Events cleared
        assert loaded_trade is not None
        assert len(loaded_trade.get_domain_events()) == 0
