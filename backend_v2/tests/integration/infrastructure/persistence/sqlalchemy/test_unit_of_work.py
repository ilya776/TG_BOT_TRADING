"""Integration tests for Unit of Work."""

from decimal import Decimal

import pytest

from app.domain.trading.entities import Position, Trade
from app.domain.trading.value_objects import (
    PositionSide,
    PositionStatus,
    TradeSide,
    TradeStatus,
    TradeType,
)
from app.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)


class TestUnitOfWork:
    """Integration tests для Unit of Work pattern."""

    @pytest.mark.asyncio
    async def test_commit_transaction(self, session_factory):
        """Test successful transaction commit."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act
        async with uow:
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
            await uow.trades.save(trade)
            await uow.commit()

        # Assert: Verify trade збережено
        async with uow:
            saved_trade = await uow.trades.get_by_id(trade.id)
            assert saved_trade is not None
            assert saved_trade.symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self, session_factory):
        """Test automatic rollback при exception."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act & Assert
        with pytest.raises(ValueError):
            async with uow:
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
                await uow.trades.save(trade)
                await uow.commit()

                # Raise exception (має викликати rollback)
                raise ValueError("Test exception")

        # Verify: Trade НЕ збережено (rollback worked)
        async with uow:
            count = await uow.trades.count_user_trades_today(user_id=1)
            assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_repositories_single_transaction(self, session_factory):
        """Test що Trade + Position використовують одну транзакцію."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act: Save trade + position в одній транзакції
        async with uow:
            # Create trade
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
            await uow.trades.save(trade)

            # Create position
            position = Position.create_from_trade(
                user_id=1,
                symbol="BTCUSDT",
                side=PositionSide.LONG,
                entry_price=Decimal("50000"),
                quantity=Decimal("0.02"),
                entry_trade_id=trade.id or 0,
                leverage=1,
            )
            await uow.positions.save(position)

            # Single commit
            await uow.commit()

        # Assert: Обидва збережені
        async with uow:
            saved_trade = await uow.trades.get_by_id(trade.id)
            saved_position = await uow.positions.get_by_id(position.id)

            assert saved_trade is not None
            assert saved_position is not None
            assert saved_trade.status == TradeStatus.FILLED
            assert saved_position.status == PositionStatus.OPEN

    @pytest.mark.asyncio
    async def test_rollback_both_repositories_on_exception(self, session_factory):
        """Test що rollback відміняє зміни в обох repositories."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act & Assert
        with pytest.raises(ValueError):
            async with uow:
                # Save trade
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
                await uow.trades.save(trade)

                # Save position
                position = Position.create_from_trade(
                    user_id=1,
                    symbol="BTCUSDT",
                    side=PositionSide.LONG,
                    entry_price=Decimal("50000"),
                    quantity=Decimal("0.02"),
                    entry_trade_id=1,
                    leverage=1,
                )
                await uow.positions.save(position)

                await uow.commit()

                # Exception (rollback)
                raise ValueError("Test exception")

        # Verify: Нічого НЕ збережено
        async with uow:
            trade_count = await uow.trades.count_user_trades_today(user_id=1)
            position_count = await uow.positions.count_open_positions_for_user(
                user_id=1
            )

            assert trade_count == 0
            assert position_count == 0

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self, session_factory):
        """Test що session закривається після __aexit__."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act
        async with uow:
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
            await uow.trades.save(trade)
            await uow.commit()

        # Assert: Session closed (accessing repositories має raise error)
        with pytest.raises(RuntimeError, match="Unit of Work not started"):
            _ = uow.trades

    @pytest.mark.asyncio
    async def test_lazy_repository_initialization(self, session_factory):
        """Test що repositories створюються тільки коли потрібно."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act
        async with uow:
            # До першого доступу repositories None
            assert uow._trades is None
            assert uow._positions is None

            # Перший доступ - створює repository
            _ = uow.trades
            assert uow._trades is not None
            assert uow._positions is None  # Positions ще не accessed

            # Другий доступ - повертає той самий instance
            trades_repo = uow.trades
            assert uow._trades is trades_repo

    @pytest.mark.asyncio
    async def test_multiple_commits_in_transaction(self, session_factory):
        """Test що можна commit кілька разів."""
        # Arrange
        uow = SQLAlchemyUnitOfWork(session_factory)

        # Act: Phase 1 - save trade PENDING
        async with uow:
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
            await uow.trades.save(trade)
            await uow.commit()  # Commit 1

            # Phase 2 - execute trade
            trade.execute(
                exchange_order_id="ORDER123",
                executed_price=Decimal("50000"),
                executed_quantity=Decimal("0.02"),
                fee_amount=Decimal("0.5"),
            )
            await uow.trades.save(trade)
            await uow.commit()  # Commit 2

        # Assert: Trade FILLED
        async with uow:
            saved_trade = await uow.trades.get_by_id(trade.id)
            assert saved_trade is not None
            assert saved_trade.status == TradeStatus.FILLED
