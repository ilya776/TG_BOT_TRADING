"""Position Mapper - converts between Position entity and PositionModel ORM."""

from app.domain.trading.entities import Position
from app.domain.trading.value_objects import PositionSide, PositionStatus
from app.infrastructure.persistence.sqlalchemy.models import PositionModel


class PositionMapper:
    """Mapper для Position entity ↔ PositionModel ORM.

    Responsibilities:
    - Convert domain Position entity → ORM PositionModel
    - Convert ORM PositionModel → domain Position entity
    - Handle enum conversions (PositionSide, PositionStatus)
    - Preserve all data during round-trip conversion

    Example:
        >>> mapper = PositionMapper()
        >>> position = Position.create_from_trade(...)
        >>> model = mapper.to_model(position)  # Domain → ORM
        >>> position_back = mapper.to_entity(model)  # ORM → Domain
    """

    def to_entity(self, model: PositionModel) -> Position:
        """Convert ORM PositionModel → Domain Position entity.

        Args:
            model: SQLAlchemy PositionModel.

        Returns:
            Domain Position entity.
        """
        # Reconstruct Position entity з ORM data
        position = Position(
            id=model.id,
            user_id=model.user_id,
            symbol=model.symbol,
            side=PositionSide(model.side),
            status=PositionStatus(model.status),
            entry_price=model.entry_price,
            quantity=model.quantity,
            leverage=model.leverage,
            stop_loss_price=model.stop_loss_price,
            take_profit_price=model.take_profit_price,
            entry_trade_id=model.entry_trade_id,
            exit_price=model.exit_price,
            exit_trade_id=model.exit_trade_id,
            unrealized_pnl=model.unrealized_pnl,
            realized_pnl=model.realized_pnl,
            opened_at=model.opened_at,
            closed_at=model.closed_at,
        )

        # ВАЖЛИВО: Clear domain events (не хочемо replay events з DB)
        position.clear_domain_events()

        return position

    def to_model(self, entity: Position) -> PositionModel:
        """Convert Domain Position entity → ORM PositionModel.

        Args:
            entity: Domain Position entity.

        Returns:
            SQLAlchemy PositionModel.
        """
        # Create або update PositionModel
        model = PositionModel(
            id=entity.id,
            user_id=entity.user_id,
            symbol=entity.symbol,
            side=entity.side.value,  # Enum → string
            status=entity.status.value,  # Enum → string
            entry_price=entity.entry_price,
            quantity=entity.quantity,
            leverage=entity.leverage,
            stop_loss_price=entity.stop_loss_price,
            take_profit_price=entity.take_profit_price,
            entry_trade_id=entity.entry_trade_id,
            exit_price=entity.exit_price,
            exit_trade_id=entity.exit_trade_id,
            unrealized_pnl=entity.unrealized_pnl,
            realized_pnl=entity.realized_pnl,
            opened_at=entity.opened_at,
            closed_at=entity.closed_at,
        )

        return model

    def update_model_from_entity(
        self, model: PositionModel, entity: Position
    ) -> PositionModel:
        """Update існуючого PositionModel з domain entity.

        Args:
            model: Існуючий PositionModel (з DB).
            entity: Updated domain Position entity.

        Returns:
            Updated PositionModel.

        Note:
            Використовується для UPDATE queries (preserve model.id).
        """
        # Update всі поля (крім id)
        model.user_id = entity.user_id
        model.symbol = entity.symbol
        model.side = entity.side.value
        model.status = entity.status.value
        model.entry_price = entity.entry_price
        model.quantity = entity.quantity
        model.leverage = entity.leverage
        model.stop_loss_price = entity.stop_loss_price
        model.take_profit_price = entity.take_profit_price
        model.entry_trade_id = entity.entry_trade_id
        model.exit_price = entity.exit_price
        model.exit_trade_id = entity.exit_trade_id
        model.unrealized_pnl = entity.unrealized_pnl
        model.realized_pnl = entity.realized_pnl
        model.opened_at = entity.opened_at
        model.closed_at = entity.closed_at

        # Increment version (optimistic locking)
        model.version += 1

        return model
