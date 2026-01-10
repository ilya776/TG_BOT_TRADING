"""ProcessSignal Handler - orchestrates signal processing with copy trades.

Handler для processing signals з priority queue та виконання copy trades.
"""

import logging
from decimal import Decimal

from app.application.shared import CommandHandler, UnitOfWork
from app.application.signals.commands import ProcessSignalCommand
from app.application.signals.dtos import SignalDTO, SignalProcessingResultDTO
from app.application.trading.commands import ExecuteCopyTradeCommand
from app.application.trading.handlers import ExecuteCopyTradeHandler
from app.domain.signals.entities import Signal
from app.domain.signals.services import SignalQueue
from app.domain.whales.repositories import WhaleFollowRepository
from app.infrastructure.messaging import EventBus

logger = logging.getLogger(__name__)


class ProcessSignalHandler(
    CommandHandler[ProcessSignalCommand, SignalProcessingResultDTO | None]
):
    """Handler для ProcessSignal command.

    Orchestrates signal processing flow:
    1. **Pick Signal**: Use SignalQueue to get next signal (priority-based)
    2. **Get Followers**: If whale signal, get all active followers
    3. **Execute Trades**: For each follower, execute ExecuteCopyTradeCommand
    4. **Track Results**: Count successes/failures, total volume
    5. **Mark Signal**: Update signal status (PROCESSED або FAILED)
    6. **Publish Events**: SignalProcessed або SignalFailed

    Returns None if no signals in queue (idle).

    Example:
        >>> handler = ProcessSignalHandler(
        ...     uow=unit_of_work,
        ...     signal_queue=signal_queue,
        ...     whale_follow_repo=whale_follow_repo,
        ...     trade_handler=execute_copy_trade_handler,
        ...     event_bus=event_bus,
        ... )
        >>>
        >>> command = ProcessSignalCommand(min_priority=SignalPriority.HIGH)
        >>> result = await handler.handle(command)
        >>>
        >>> if result:
        ...     print(f"Processed signal {result.signal_id}")
        ...     print(f"Trades: {result.successful_trades}/{result.trades_executed}")
        ... else:
        ...     print("No signals in queue")
    """

    def __init__(
        self,
        uow: UnitOfWork,
        signal_queue: SignalQueue,
        whale_follow_repo: WhaleFollowRepository,
        trade_handler: ExecuteCopyTradeHandler,
        event_bus: EventBus,
    ) -> None:
        """Initialize handler.

        Args:
            uow: Unit of Work для transaction management.
            signal_queue: SignalQueue domain service.
            whale_follow_repo: Repository для getting whale followers.
            trade_handler: ExecuteCopyTradeHandler для executing trades.
            event_bus: Event bus для publishing domain events.
        """
        self._uow = uow
        self._signal_queue = signal_queue
        self._whale_follow_repo = whale_follow_repo
        self._trade_handler = trade_handler
        self._event_bus = event_bus

    async def handle(
        self, command: ProcessSignalCommand
    ) -> SignalProcessingResultDTO | None:
        """Process next signal from queue.

        Args:
            command: ProcessSignalCommand with min_priority filter.

        Returns:
            SignalProcessingResultDTO with results, або None if queue empty.

        Raises:
            ValueError: If signal processing fails critically.
        """
        # Step 1: Pick next signal from queue
        signal = await self._signal_queue.pick_next(min_priority=command.min_priority)

        if signal is None:
            logger.debug("process_signal.no_signals_in_queue")
            return None

        logger.info(
            "process_signal.started",
            extra={
                "signal_id": signal.id,
                "whale_id": signal.whale_id,
                "symbol": signal.symbol,
                "priority": signal.priority.value,
            },
        )

        try:
            # Step 2: Get followers (if whale signal)
            followers = []
            if signal.whale_id:
                followers = await self._whale_follow_repo.get_active_followers(
                    signal.whale_id
                )
                logger.info(
                    "process_signal.followers_found",
                    extra={"signal_id": signal.id, "followers_count": len(followers)},
                )

            if not followers and signal.whale_id:
                # Whale має 0 followers -> skip signal
                await self._signal_queue.mark_processed(signal.id, trades_executed=0)
                logger.warning(
                    "process_signal.no_followers",
                    extra={"signal_id": signal.id, "whale_id": signal.whale_id},
                )
                return self._build_result(signal, [], [])

            # Step 3: Execute copy trades for each follower
            successful_trades = []
            failed_trades = []

            for follower in followers:
                try:
                    # Create ExecuteCopyTradeCommand з follower settings
                    trade_command = ExecuteCopyTradeCommand(
                        signal_id=signal.id,
                        user_id=follower.user_id,
                        exchange_name=follower.exchange_name,
                        symbol=signal.symbol,
                        side=signal.side,
                        trade_type=signal.trade_type,
                        size_usdt=follower.copy_trade_size_usdt,
                        leverage=min(
                            signal.leverage or 1, follower.max_leverage
                        ),  # Use min of signal/follower leverage
                        entry_price=signal.entry_price,
                        # TODO: Extract SL/TP from signal metadata
                        stop_loss_price=None,
                        take_profit_price=None,
                    )

                    # Execute trade
                    trade_dto = await self._trade_handler.handle(trade_command)
                    successful_trades.append(trade_dto)

                    logger.info(
                        "process_signal.trade_executed",
                        extra={
                            "signal_id": signal.id,
                            "user_id": follower.user_id,
                            "trade_id": trade_dto.id,
                        },
                    )

                except Exception as e:
                    error_msg = f"User {follower.user_id}: {str(e)}"
                    failed_trades.append(error_msg)

                    logger.error(
                        "process_signal.trade_failed",
                        extra={
                            "signal_id": signal.id,
                            "user_id": follower.user_id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )

            # Step 4: Mark signal as processed/failed
            if successful_trades:
                await self._signal_queue.mark_processed(
                    signal.id, trades_executed=len(successful_trades)
                )
                logger.info(
                    "process_signal.completed",
                    extra={
                        "signal_id": signal.id,
                        "successful": len(successful_trades),
                        "failed": len(failed_trades),
                    },
                )
            else:
                # Всі trades failed
                error_message = (
                    f"All trades failed: {'; '.join(failed_trades[:3])}"  # First 3
                )
                await self._signal_queue.mark_failed(signal.id, error_message)
                logger.error(
                    "process_signal.all_trades_failed",
                    extra={
                        "signal_id": signal.id,
                        "failed_count": len(failed_trades),
                    },
                )

            # Step 5: Build result DTO
            result = self._build_result(signal, successful_trades, failed_trades)

            # Step 6: Publish domain events (вони вже додані в signal entity)
            async with self._uow:
                await self._uow.commit()  # Flush events to event bus

            return result

        except Exception as e:
            # Critical error -> mark signal as failed
            await self._signal_queue.mark_failed(signal.id, str(e))
            logger.error(
                "process_signal.critical_error",
                extra={"signal_id": signal.id, "error": str(e)},
                exc_info=True,
            )
            raise

    def _build_result(
        self,
        signal: Signal,
        successful_trades: list,
        failed_trades: list[str],
    ) -> SignalProcessingResultDTO:
        """Build SignalProcessingResultDTO from signal and trade results.

        Args:
            signal: Signal entity.
            successful_trades: List of successful TradeDTO.
            failed_trades: List of error messages.

        Returns:
            SignalProcessingResultDTO.
        """
        total_volume = sum(
            trade.size for trade in successful_trades if trade.size
        ) or Decimal("0")

        signal_dto = SignalDTO(
            id=signal.id,
            whale_id=signal.whale_id,
            source=signal.source.value,
            status=signal.status.value,
            priority=signal.priority.value,
            symbol=signal.symbol,
            side=signal.side,
            trade_type=signal.trade_type,
            entry_price=signal.entry_price,
            quantity=signal.quantity,
            leverage=signal.leverage,
            detected_at=signal.detected_at,
            processed_at=signal.processed_at,
            trades_executed=signal.trades_executed,
            error_message=signal.error_message,
        )

        return SignalProcessingResultDTO(
            signal_id=signal.id,
            signal=signal_dto,
            trades_executed=len(successful_trades) + len(failed_trades),
            successful_trades=len(successful_trades),
            failed_trades=len(failed_trades),
            total_volume_usdt=total_volume,
            errors=failed_trades,
        )
