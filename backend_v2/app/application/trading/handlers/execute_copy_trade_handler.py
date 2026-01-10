"""ExecuteCopyTrade Handler - orchestrates copy trade execution.

Це CORE use case handler всієї системи.
Демонструє як всі building blocks з Phase 1 & 2 працюють разом.
"""

import logging
from decimal import Decimal

from app.application.shared import CommandHandler, UnitOfWork
from app.application.trading.commands import ExecuteCopyTradeCommand
from app.application.trading.dtos import TradeDTO
from app.domain.exchanges.ports import ExchangePort
from app.domain.trading.entities import Position, Trade
from app.domain.trading.repositories import PositionRepository, TradeRepository
from app.domain.trading.value_objects import PositionSide, TradeSide, TradeType
from app.infrastructure.exchanges.factories import ExchangeFactory
from app.infrastructure.messaging import EventBus

logger = logging.getLogger(__name__)


class ExecuteCopyTradeHandler(CommandHandler[ExecuteCopyTradeCommand, TradeDTO]):
    """Handler для ExecuteCopyTrade command.

    Orchestrates entire copy trade flow:
    1. **Phase 1 (RESERVE)**: Create trade в PENDING, commit (reserve funds)
    2. **Exchange Call**: Execute на біржі (з автоматичним retry + circuit breaker)
    3. **Phase 2 (CONFIRM)**: Update trade to FILLED, create position, commit
    4. **Publish Events**: TradeExecuted, PositionOpened

    Example:
        >>> handler = ExecuteCopyTradeHandler(
        ...     uow=unit_of_work,
        ...     exchange_factory=exchange_factory,
        ...     event_bus=event_bus,
        ... )
        >>> 
        >>> command = ExecuteCopyTradeCommand(...)
        >>> trade_dto = await handler.handle(command)
        >>> # Trade executed, position created, events published!
    """

    def __init__(
        self,
        uow: UnitOfWork,
        exchange_factory: ExchangeFactory,
        event_bus: EventBus,
    ) -> None:
        """Initialize handler.

        Args:
            uow: Unit of Work для transaction management.
            exchange_factory: Factory для створення exchange adapters.
            event_bus: Event bus для publishing domain events.
        """
        self.uow = uow
        self.exchange_factory = exchange_factory
        self.event_bus = event_bus

    async def handle(self, command: ExecuteCopyTradeCommand) -> TradeDTO:
        """Execute copy trade.

        Args:
            command: ExecuteCopyTrade command.

        Returns:
            TradeDTO з результатом.

        Raises:
            InsufficientBalanceError: Not enough funds.
            ExchangeAPIError: Exchange API failed.
        """
        logger.info(
            "execute_copy_trade.started",
            extra={
                "user_id": command.user_id,
                "signal_id": command.signal_id,
                "symbol": command.symbol,
                "size_usdt": str(command.size_usdt),
            },
        )

        # Map command to domain value objects
        side = TradeSide(command.side)
        trade_type = TradeType(command.trade_type)

        # Calculate quantity (simplified - в production буде price service)
        # TODO: Get current price from exchange
        current_price = Decimal("50000")  # Mock price
        quantity = command.size_usdt / current_price

        # ===== PHASE 1: RESERVE =====
        # Create trade в PENDING, reserve funds
        async with self.uow:
            trade = Trade.create_copy_trade(
                user_id=command.user_id,
                signal_id=command.signal_id,
                symbol=command.symbol,
                side=side,
                trade_type=trade_type,
                size_usdt=command.size_usdt,
                quantity=quantity,
                leverage=command.leverage,
            )

            # Save trade (PENDING status)
            trade_repo: TradeRepository = self.uow.trades
            await trade_repo.save(trade)

            # Commit Phase 1 - funds reserved!
            await self.uow.commit()

            logger.info(
                "execute_copy_trade.phase1_committed",
                extra={"trade_id": trade.id},
            )

        # ===== EXCHANGE CALL =====
        # Execute на біржі з автоматичним retry + circuit breaker
        try:
            # Create exchange adapter
            adapter: ExchangePort = self.exchange_factory.create_exchange(
                exchange_name=command.exchange_name,
                api_key="mock_key",  # TODO: Get from user credentials
                api_secret="mock_secret",
            )

            await adapter.initialize()

            # Execute trade (АВТОМАТИЧНИЙ retry + circuit breaker!)
            if side == TradeSide.BUY:
                order_result = await adapter.execute_spot_buy(
                    symbol=command.symbol, quantity=quantity
                )
            else:
                order_result = await adapter.execute_spot_sell(
                    symbol=command.symbol, quantity=quantity
                )

            await adapter.close()

            logger.info(
                "execute_copy_trade.exchange_success",
                extra={
                    "trade_id": trade.id,
                    "order_id": order_result.order_id,
                },
            )

        except Exception as e:
            # Exchange call FAILED - rollback trade
            logger.error(
                "execute_copy_trade.exchange_failed",
                extra={"trade_id": trade.id, "error": str(e)},
            )

            async with self.uow:
                # Reload trade
                trade = await self.uow.trades.get_by_id(trade.id)
                if trade is None:
                    raise RuntimeError(f"Trade {trade.id} not found")

                # Mark as FAILED (Phase 2: ROLLBACK)
                trade.fail(str(e))
                await self.uow.commit()

                # Publish TradeFailedEvent
                events = trade.get_domain_events()
                await self.event_bus.publish_all(events)
                trade.clear_domain_events()

            # Re-raise exception
            raise

        # ===== PHASE 2: CONFIRM =====
        # Exchange success - update trade, create position
        async with self.uow:
            # Reload trade
            trade = await self.uow.trades.get_by_id(trade.id)
            if trade is None:
                raise RuntimeError(f"Trade {trade.id} not found")

            # Mark trade as FILLED
            trade.execute(
                exchange_order_id=order_result.order_id,
                executed_price=order_result.avg_fill_price,
                executed_quantity=order_result.filled_quantity,
                fee_amount=order_result.fee_amount,
            )

            # Create position
            position_side = (
                PositionSide.LONG if side == TradeSide.BUY else PositionSide.SHORT
            )

            # Calculate SL/TP prices
            sl_price = None
            tp_price = None
            if command.stop_loss_percentage:
                sl_price = order_result.avg_fill_price * (
                    Decimal("1") - command.stop_loss_percentage / Decimal("100")
                )
            if command.take_profit_percentage:
                tp_price = order_result.avg_fill_price * (
                    Decimal("1") + command.take_profit_percentage / Decimal("100")
                )

            position = Position.create_from_trade(
                user_id=command.user_id,
                symbol=command.symbol,
                side=position_side,
                entry_price=order_result.avg_fill_price,
                quantity=order_result.filled_quantity,
                entry_trade_id=trade.id,
                leverage=command.leverage,
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
            )

            # Save position
            position_repo: PositionRepository = self.uow.positions
            await position_repo.save(position)

            # Commit Phase 2
            await self.uow.commit()

            logger.info(
                "execute_copy_trade.phase2_committed",
                extra={
                    "trade_id": trade.id,
                    "position_id": position.id,
                },
            )

            # Publish domain events (TradeExecuted, PositionOpened)
            trade_events = trade.get_domain_events()
            position_events = position.get_domain_events()
            all_events = trade_events + position_events

            await self.event_bus.publish_all(all_events)
            trade.clear_domain_events()
            position.clear_domain_events()

        # Convert to DTO
        trade_dto = self._to_dto(trade)

        logger.info(
            "execute_copy_trade.completed",
            extra={"trade_id": trade.id},
        )

        return trade_dto

    def _to_dto(self, trade: Trade) -> TradeDTO:
        """Convert Trade entity to DTO.

        Args:
            trade: Trade entity.

        Returns:
            TradeDTO.
        """
        return TradeDTO(
            id=trade.id or 0,
            user_id=trade.user_id,
            signal_id=trade.signal_id,
            symbol=trade.symbol,
            side=trade.side.value,
            trade_type=trade.trade_type.value,
            status=trade.status.value,
            size_usdt=trade.size_usdt,
            quantity=trade.quantity,
            leverage=trade.leverage,
            executed_price=trade.executed_price,
            executed_quantity=trade.executed_quantity,
            exchange_order_id=trade.exchange_order_id,
            fee_amount=trade.fee_amount,
            created_at=trade.created_at,
            executed_at=trade.executed_at,
            error_message=trade.error_message,
        )
