"""Base Handler classes для Commands та Queries.

Handler - orchestrates domain logic для виконання use case.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .command import Command
from .query import Query

TCommand = TypeVar("TCommand", bound=Command)
TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """Base class для command handlers.

    Command Handler відповідає за:
    - Load aggregates з repository
    - Execute domain logic (aggregate methods)
    - Save changes через Unit of Work
    - Publish domain events

    Example:
        >>> class ExecuteCopyTradeHandler(CommandHandler[ExecuteCopyTradeCommand, Trade]):
        ...     def __init__(
        ...         self,
        ...         trade_repo: TradeRepository,
        ...         signal_repo: SignalRepository,
        ...         uow: UnitOfWork,
        ...         exchange_factory: ExchangeFactory,
        ...     ):
        ...         self.trade_repo = trade_repo
        ...         self.signal_repo = signal_repo
        ...         self.uow = uow
        ...         self.exchange_factory = exchange_factory
        ...
        ...     async def handle(self, command: ExecuteCopyTradeCommand) -> Trade:
        ...         async with self.uow:
        ...             # Load aggregates
        ...             signal = await self.signal_repo.get_by_id(command.signal_id)
        ...
        ...             # Execute domain logic
        ...             trade = Trade.create_copy_trade(...)
        ...             trade.reserve_balance(...)
        ...
        ...             # Save
        ...             await self.trade_repo.save(trade)
        ...             await self.uow.commit()  # Phase 1
        ...
        ...             # Exchange call
        ...             exchange = self.exchange_factory.create(...)
        ...             order_result = await exchange.execute_spot_buy(...)
        ...
        ...             # Confirm
        ...             trade.execute(order_result)
        ...             await self.uow.commit()  # Phase 2
        ...
        ...             return trade

    Why Handlers?
        - **Single Responsibility**: One handler = one use case
        - **Testable**: Easy to test (inject mock repositories)
        - **Reusable**: Can be called from API, workers, tests
    """

    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """Handle command and return result.

        Args:
            command: Command to handle.

        Returns:
            Result of command execution.

        Raises:
            DomainException: If business rule violated.
            ValidationError: If command invalid.
        """
        pass


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Base class для query handlers.

    Query Handler відповідає за:
    - Fetch data з repository або read model
    - Transform to DTOs
    - Apply filters, sorting, pagination
    - NO side effects (read-only)

    Example:
        >>> class GetUserTradesHandler(QueryHandler[GetUserTradesQuery, list[TradeDTO]]):
        ...     def __init__(self, trade_repo: TradeRepository):
        ...         self.trade_repo = trade_repo
        ...
        ...     async def handle(self, query: GetUserTradesQuery) -> list[TradeDTO]:
        ...         trades = await self.trade_repo.get_trades_for_user(
        ...             user_id=query.user_id,
        ...             status=query.status,
        ...             limit=query.limit,
        ...         )
        ...         return [TradeDTO.from_entity(t) for t in trades]

    Query Optimization:
        - Use projections (select only needed fields)
        - Use indexes
        - Use caching for expensive queries
        - Consider materialized views for analytics
    """

    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """Handle query and return result.

        Args:
            query: Query to handle.

        Returns:
            Query result (DTOs, aggregates, primitives).

        Note:
            Queries MUST NOT have side effects.
        """
        pass
