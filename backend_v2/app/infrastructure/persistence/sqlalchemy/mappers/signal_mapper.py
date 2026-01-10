"""SignalMapper - converts between Signal entity and SignalModel ORM.

Mapper pattern: Domain entity ↔ ORM model conversion.
Це дозволяє зберігати domain layer чистим від SQLAlchemy.
"""

import json
from datetime import datetime, timezone

from app.domain.signals.entities import Signal
from app.domain.signals.value_objects import SignalPriority, SignalSource, SignalStatus
from app.infrastructure.persistence.sqlalchemy.models.signal_model import SignalModel


class SignalMapper:
    """Mapper для Signal entity ↔ SignalModel ORM.

    Example:
        >>> mapper = SignalMapper()
        >>>
        >>> # Domain → ORM
        >>> signal = Signal.create_whale_signal(...)
        >>> model = mapper.to_model(signal)
        >>> session.add(model)
        >>>
        >>> # ORM → Domain
        >>> model = await session.get(SignalModel, 123)
        >>> signal = mapper.to_entity(model)
        >>> signal.start_processing()
    """

    def to_entity(self, model: SignalModel) -> Signal:
        """Convert SignalModel (ORM) → Signal (domain entity).

        Args:
            model: SignalModel ORM instance.

        Returns:
            Signal domain entity.
        """
        # Parse metadata JSON
        metadata = {}
        if model.metadata_json:
            try:
                metadata = json.loads(model.metadata_json)
            except json.JSONDecodeError:
                metadata = {}

        # Create Signal entity
        signal = Signal(
            id=model.id,
            whale_id=model.whale_id,
            source=SignalSource(model.source),
            status=SignalStatus(model.status),
            priority=SignalPriority(model.priority),
            symbol=model.symbol,
            side=model.side,
            trade_type=model.trade_type,
            entry_price=model.entry_price,
            quantity=model.quantity,
            leverage=model.leverage,
            metadata=metadata,
            trades_executed=model.trades_executed,
            error_message=model.error_message,
            detected_at=model.detected_at,
            processed_at=model.processed_at,
        )

        return signal

    def to_model(self, entity: Signal) -> SignalModel:
        """Convert Signal (domain entity) → SignalModel (ORM).

        Args:
            entity: Signal domain entity.

        Returns:
            SignalModel ORM instance.
        """
        # Serialize metadata to JSON
        metadata_json = None
        if entity.metadata:
            metadata_json = json.dumps(entity.metadata)

        # Create or update ORM model
        model = SignalModel(
            id=entity.id,
            whale_id=entity.whale_id,
            source=entity.source.value,
            status=entity.status.value,
            priority=entity.priority.value,
            symbol=entity.symbol,
            side=entity.side,
            trade_type=entity.trade_type,
            entry_price=entity.entry_price,
            quantity=entity.quantity,
            leverage=entity.leverage,
            metadata_json=metadata_json,
            trades_executed=entity.trades_executed,
            error_message=entity.error_message,
            detected_at=entity.detected_at,
            processed_at=entity.processed_at,
        )

        return model

    def update_model(self, entity: Signal, model: SignalModel) -> None:
        """Update existing SignalModel з Signal entity.

        Це для UPDATE операцій - оновлюємо існуючий model in-place.

        Args:
            entity: Signal domain entity (джерело даних).
            model: SignalModel ORM instance (target to update).
        """
        # Update fields
        model.whale_id = entity.whale_id
        model.source = entity.source.value
        model.status = entity.status.value
        model.priority = entity.priority.value
        model.symbol = entity.symbol
        model.side = entity.side
        model.trade_type = entity.trade_type
        model.entry_price = entity.entry_price
        model.quantity = entity.quantity
        model.leverage = entity.leverage
        model.trades_executed = entity.trades_executed
        model.error_message = entity.error_message
        model.processed_at = entity.processed_at

        # Update metadata JSON
        if entity.metadata:
            model.metadata_json = json.dumps(entity.metadata)
        else:
            model.metadata_json = None
