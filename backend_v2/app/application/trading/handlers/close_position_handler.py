"""ClosePosition Handler - закрити відкриту position."""

import logging

from app.application.shared import CommandHandler, UnitOfWork
from app.application.trading.commands import ClosePositionCommand
from app.application.trading.dtos import PositionDTO
from app.domain.exchanges.ports import ExchangePort
from app.domain.trading.entities import Trade
from app.domain.trading.repositories import PositionRepository
from app.domain.trading.value_objects import TradeSide, TradeType
from app.infrastructure.exchanges.factories import ExchangeFactory
from app.infrastructure.messaging import EventBus

logger = logging.getLogger(__name__)


class ClosePositionHandler(CommandHandler[ClosePositionCommand, PositionDTO]):
    """Handler для ClosePosition command.

    Flow:
    1. Get position з DB
    2. Create close trade (PENDING)
    3. Execute close на exchange
    4. Update trade to FILLED
    5. Close position (calculate realized PnL)
    6. Publish events (PositionClosed)

    Example:
        >>> command = ClosePositionCommand(position_id=123, user_id=1, exchange_name="binance")
        >>> position_dto = await handler.handle(command)
    """

    def __init__(
        self,
        uow: UnitOfWork,
        exchange_factory: ExchangeFactory,
        event_bus: EventBus,
    ) -> None:
        """Initialize handler."""
        self.uow = uow
        self.exchange_factory = exchange_factory
        self.event_bus = event_bus

    async def handle(self, command: ClosePositionCommand) -> PositionDTO:
        """Close position.

        Args:
            command: ClosePosition command.

        Returns:
            PositionDTO з результатом.
        """
        logger.info(
            "close_position.started",
            extra={
                "position_id": command.position_id,
                "user_id": command.user_id,
            },
        )

        # Get position
        async with self.uow:
            position = await self.uow.positions.get_by_id(command.position_id)
            if position is None:
                raise ValueError(f"Position {command.position_id} not found")

            # Security check
            if position.user_id != command.user_id:
                raise ValueError("Position doesn't belong to user")

            # Check if already closed
            if not position.is_open:
                raise ValueError(f"Position already {position.status.value}")

        # Create close trade
        close_side = (
            TradeSide.SELL if position.side.value == "long" else TradeSide.BUY
        )

        async with self.uow:
            close_trade = Trade.create_copy_trade(
                user_id=command.user_id,
                signal_id=None,  # Manual close, no signal
                symbol=position.symbol,
                side=close_side,
                trade_type=TradeType.SPOT,
                size_usdt=position.quantity * position.entry_price,
                quantity=position.quantity,
                leverage=1,
            )

            await self.uow.trades.save(close_trade)
            await self.uow.commit()

        # Execute close на exchange
        try:
            adapter: ExchangePort = self.exchange_factory.create_exchange(
                exchange_name=command.exchange_name,
                api_key="mock_key",
                api_secret="mock_secret",
            )

            await adapter.initialize()

            if close_side == TradeSide.SELL:
                order_result = await adapter.execute_spot_sell(
                    symbol=position.symbol, quantity=position.quantity
                )
            else:
                order_result = await adapter.execute_spot_buy(
                    symbol=position.symbol, quantity=position.quantity
                )

            await adapter.close()

        except Exception as e:
            logger.error(
                "close_position.exchange_failed",
                extra={"position_id": command.position_id, "error": str(e)},
            )

            async with self.uow:
                close_trade = await self.uow.trades.get_by_id(close_trade.id)
                if close_trade:
                    close_trade.fail(str(e))
                    await self.uow.commit()

            raise

        # Success - update trade and close position
        async with self.uow:
            # Update close trade
            close_trade = await self.uow.trades.get_by_id(close_trade.id)
            if close_trade:
                close_trade.execute(
                    exchange_order_id=order_result.order_id,
                    executed_price=order_result.avg_fill_price,
                    executed_quantity=order_result.filled_quantity,
                    fee_amount=order_result.fee_amount,
                )

            # Close position
            position = await self.uow.positions.get_by_id(command.position_id)
            if position is None:
                raise ValueError("Position not found")

            realized_pnl = position.close(
                exit_price=order_result.avg_fill_price,
                exit_trade_id=close_trade.id,
            )

            await self.uow.commit()

            logger.info(
                "close_position.completed",
                extra={
                    "position_id": position.id,
                    "realized_pnl": str(realized_pnl),
                },
            )

            # Publish events
            if close_trade:
                trade_events = close_trade.get_domain_events()
                await self.event_bus.publish_all(trade_events)
                close_trade.clear_domain_events()

            position_events = position.get_domain_events()
            await self.event_bus.publish_all(position_events)
            position.clear_domain_events()

        return self._to_dto(position)

    def _to_dto(self, position) -> PositionDTO:
        """Convert Position to DTO."""
        return PositionDTO(
            id=position.id or 0,
            user_id=position.user_id,
            symbol=position.symbol,
            side=position.side.value,
            status=position.status.value,
            entry_price=position.entry_price,
            quantity=position.quantity,
            leverage=position.leverage,
            stop_loss_price=position.stop_loss_price,
            take_profit_price=position.take_profit_price,
            entry_trade_id=position.entry_trade_id,
            exit_price=position.exit_price,
            exit_trade_id=position.exit_trade_id,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            opened_at=position.opened_at,
            closed_at=position.closed_at,
        )
