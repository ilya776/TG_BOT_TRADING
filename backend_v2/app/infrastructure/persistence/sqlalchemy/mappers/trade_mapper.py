"""Trade Mapper - converts between Trade entity and TradeModel ORM."""

from app.domain.trading.entities import Trade
from app.domain.trading.value_objects import TradeSide, TradeStatus, TradeType
from app.infrastructure.persistence.sqlalchemy.models import TradeModel


class TradeMapper:
    """Mapper для Trade entity ↔ TradeModel ORM.

    Responsibilities:
    - Convert domain Trade entity → ORM TradeModel (to_model)
    - Convert ORM TradeModel → domain Trade entity (to_entity)
    - Handle enum conversions (TradeSide, TradeType, TradeStatus)
    - Preserve all data during round-trip conversion

    Example:
        >>> mapper = TradeMapper()
        >>> trade = Trade.create_copy_trade(...)
        >>> model = mapper.to_model(trade)  # Domain → ORM
        >>> trade_back = mapper.to_entity(model)  # ORM → Domain
    """

    def to_entity(self, model: TradeModel) -> Trade:
        """Convert ORM TradeModel → Domain Trade entity.

        Args:
            model: SQLAlchemy TradeModel.

        Returns:
            Domain Trade entity.
        """
        # Reconstruct Trade entity з ORM data
        trade = Trade(
            id=model.id,
            user_id=model.user_id,
            signal_id=model.signal_id,
            symbol=model.symbol,
            side=TradeSide(model.side),
            trade_type=TradeType(model.trade_type),
            status=TradeStatus(model.status),
            size_usdt=model.size_usdt,
            quantity=model.quantity,
            leverage=model.leverage,
            executed_price=model.executed_price,
            executed_quantity=model.executed_quantity,
            exchange_order_id=model.exchange_order_id,
            fee_amount=model.fee_amount,
            created_at=model.created_at,
            executed_at=model.executed_at,
            error_message=model.error_message,
        )

        # ВАЖЛИВО: Clear domain events (не хочемо replay events з DB)
        trade.clear_domain_events()

        return trade

    def to_model(self, entity: Trade) -> TradeModel:
        """Convert Domain Trade entity → ORM TradeModel.

        Args:
            entity: Domain Trade entity.

        Returns:
            SQLAlchemy TradeModel.
        """
        # Create або update TradeModel
        model = TradeModel(
            id=entity.id,
            user_id=entity.user_id,
            signal_id=entity.signal_id,
            symbol=entity.symbol,
            side=entity.side.value,  # Enum → string
            trade_type=entity.trade_type.value,  # Enum → string
            status=entity.status.value,  # Enum → string
            size_usdt=entity.size_usdt,
            quantity=entity.quantity,
            leverage=entity.leverage,
            executed_price=entity.executed_price,
            executed_quantity=entity.executed_quantity,
            exchange_order_id=entity.exchange_order_id,
            fee_amount=entity.fee_amount,
            created_at=entity.created_at,
            executed_at=entity.executed_at,
            error_message=entity.error_message,
        )

        return model

    def update_model_from_entity(
        self, model: TradeModel, entity: Trade
    ) -> TradeModel:
        """Update існуючого TradeModel з domain entity.

        Args:
            model: Існуючий TradeModel (з DB).
            entity: Updated domain Trade entity.

        Returns:
            Updated TradeModel.

        Note:
            Використовується для UPDATE queries (preserve model.id).
        """
        # Update всі поля (крім id)
        model.user_id = entity.user_id
        model.signal_id = entity.signal_id
        model.symbol = entity.symbol
        model.side = entity.side.value
        model.trade_type = entity.trade_type.value
        model.status = entity.status.value
        model.size_usdt = entity.size_usdt
        model.quantity = entity.quantity
        model.leverage = entity.leverage
        model.executed_price = entity.executed_price
        model.executed_quantity = entity.executed_quantity
        model.exchange_order_id = entity.exchange_order_id
        model.fee_amount = entity.fee_amount
        model.created_at = entity.created_at
        model.executed_at = entity.executed_at
        model.error_message = entity.error_message

        # Increment version (optimistic locking)
        model.version += 1

        return model
