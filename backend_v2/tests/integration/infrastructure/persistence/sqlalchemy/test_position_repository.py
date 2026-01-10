"""Integration tests for PositionRepository."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.trading.entities import Position
from app.domain.trading.value_objects import PositionSide, PositionStatus
from app.infrastructure.persistence.sqlalchemy.repositories import (
    SQLAlchemyPositionRepository,
)


class TestPositionRepository:
    """Integration tests для PositionRepository."""

    @pytest.mark.asyncio
    async def test_save_new_position(self, session):
        """Test saving new position (INSERT)."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
            stop_loss_price=Decimal("45000"),
            take_profit_price=Decimal("60000"),
        )

        # Act
        await repo.save(position)
        await session.commit()

        # Assert
        assert position.id is not None  # ID generated
        saved_position = await repo.get_by_id(position.id)
        assert saved_position is not None
        assert saved_position.user_id == 1
        assert saved_position.symbol == "BTCUSDT"
        assert saved_position.side == PositionSide.LONG
        assert saved_position.status == PositionStatus.OPEN
        assert saved_position.stop_loss_price == Decimal("45000")

    @pytest.mark.asyncio
    async def test_save_existing_position(self, session):
        """Test updating existing position (UPDATE)."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
        )
        await repo.save(position)
        await session.commit()

        # Act: Close position
        realized_pnl = position.close(
            exit_price=Decimal("55000"), exit_trade_id=101
        )
        await repo.save(position)
        await session.commit()

        # Assert
        updated_position = await repo.get_by_id(position.id)
        assert updated_position is not None
        assert updated_position.status == PositionStatus.CLOSED
        assert updated_position.exit_price == Decimal("55000")
        assert updated_position.exit_trade_id == 101
        assert updated_position.realized_pnl == realized_pnl
        assert updated_position.closed_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, session):
        """Test get_by_id returns None якщо position не знайдено."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)

        # Act
        position = await repo.get_by_id(9999)

        # Assert
        assert position is None

    @pytest.mark.asyncio
    async def test_get_open_positions_for_user(self, session):
        """Test getting open positions for user."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)

        # Create 3 positions: 2 OPEN, 1 CLOSED
        pos1 = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
        )
        pos2 = Position.create_from_trade(
            user_id=1,
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("3000"),
            quantity=Decimal("0.5"),
            entry_trade_id=101,
            leverage=1,
        )
        pos3 = Position.create_from_trade(
            user_id=1,
            symbol="BNBUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("400"),
            quantity=Decimal("2.5"),
            entry_trade_id=102,
            leverage=1,
        )
        pos3.close(exit_price=Decimal("450"), exit_trade_id=103)

        await repo.save(pos1)
        await repo.save(pos2)
        await repo.save(pos3)
        await session.commit()

        # Act
        open_positions = await repo.get_open_positions_for_user(user_id=1)

        # Assert
        assert len(open_positions) == 2
        assert all(p.status == PositionStatus.OPEN for p in open_positions)
        symbols = {p.symbol for p in open_positions}
        assert symbols == {"BTCUSDT", "ETHUSDT"}

    @pytest.mark.asyncio
    async def test_get_positions_with_stop_loss(self, session):
        """Test getting positions з stop-loss."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)

        # Position з SL
        pos1 = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
            stop_loss_price=Decimal("45000"),
        )

        # Position БЕЗ SL
        pos2 = Position.create_from_trade(
            user_id=2,
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("3000"),
            quantity=Decimal("0.5"),
            entry_trade_id=101,
            leverage=1,
        )

        await repo.save(pos1)
        await repo.save(pos2)
        await session.commit()

        # Act
        sl_positions = await repo.get_positions_with_stop_loss()

        # Assert
        assert len(sl_positions) == 1
        assert sl_positions[0].symbol == "BTCUSDT"
        assert sl_positions[0].stop_loss_price == Decimal("45000")

    @pytest.mark.asyncio
    async def test_get_positions_with_take_profit(self, session):
        """Test getting positions з take-profit."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)

        # Position з TP
        pos1 = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
            take_profit_price=Decimal("60000"),
        )

        # Position БЕЗ TP
        pos2 = Position.create_from_trade(
            user_id=2,
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("3000"),
            quantity=Decimal("0.5"),
            entry_trade_id=101,
            leverage=1,
        )

        await repo.save(pos1)
        await repo.save(pos2)
        await session.commit()

        # Act
        tp_positions = await repo.get_positions_with_take_profit()

        # Assert
        assert len(tp_positions) == 1
        assert tp_positions[0].symbol == "BTCUSDT"
        assert tp_positions[0].take_profit_price == Decimal("60000")

    @pytest.mark.asyncio
    async def test_get_position_by_symbol_and_user(self, session):
        """Test getting position by symbol and user."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)

        pos1 = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
        )
        pos2 = Position.create_from_trade(
            user_id=2,
            symbol="BTCUSDT",  # Same symbol, different user
            side=PositionSide.LONG,
            entry_price=Decimal("51000"),
            quantity=Decimal("0.01"),
            entry_trade_id=101,
            leverage=1,
        )

        await repo.save(pos1)
        await repo.save(pos2)
        await session.commit()

        # Act
        position = await repo.get_position_by_symbol_and_user(
            user_id=1, symbol="BTCUSDT", status=PositionStatus.OPEN
        )

        # Assert
        assert position is not None
        assert position.user_id == 1
        assert position.symbol == "BTCUSDT"
        assert position.entry_price == Decimal("50000")

        # Other user
        position2 = await repo.get_position_by_symbol_and_user(
            user_id=2, symbol="BTCUSDT", status=PositionStatus.OPEN
        )
        assert position2 is not None
        assert position2.user_id == 2
        assert position2.entry_price == Decimal("51000")

    @pytest.mark.asyncio
    async def test_count_open_positions_for_user(self, session):
        """Test counting open positions for user."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)

        # User 1: 2 OPEN positions
        pos1 = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
        )
        pos2 = Position.create_from_trade(
            user_id=1,
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("3000"),
            quantity=Decimal("0.5"),
            entry_trade_id=101,
            leverage=1,
        )
        pos3 = Position.create_from_trade(
            user_id=1,
            symbol="BNBUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("400"),
            quantity=Decimal("2.5"),
            entry_trade_id=102,
            leverage=1,
        )
        pos3.close(exit_price=Decimal("450"), exit_trade_id=103)  # CLOSED

        # User 2: 1 OPEN position
        pos4 = Position.create_from_trade(
            user_id=2,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("51000"),
            quantity=Decimal("0.01"),
            entry_trade_id=104,
            leverage=1,
        )

        await repo.save(pos1)
        await repo.save(pos2)
        await repo.save(pos3)
        await repo.save(pos4)
        await session.commit()

        # Act
        count_user1 = await repo.count_open_positions_for_user(user_id=1)
        count_user2 = await repo.count_open_positions_for_user(user_id=2)

        # Assert
        assert count_user1 == 2  # pos1, pos2 (pos3 CLOSED)
        assert count_user2 == 1  # pos4

    @pytest.mark.asyncio
    async def test_domain_events_cleared_after_load(self, session):
        """Test що domain events НЕ replay з DB."""
        # Arrange
        repo = SQLAlchemyPositionRepository(session)
        position = Position.create_from_trade(
            user_id=1,
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.02"),
            entry_trade_id=100,
            leverage=1,
        )

        # Position has events (PositionOpenedEvent)
        assert len(position.get_domain_events()) > 0

        # Save
        await repo.save(position)
        await session.commit()

        # Act: Load from DB
        loaded_position = await repo.get_by_id(position.id)

        # Assert: Events cleared
        assert loaded_position is not None
        assert len(loaded_position.get_domain_events()) == 0
