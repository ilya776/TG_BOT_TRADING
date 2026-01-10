"""Trade Aggregate Root - серце copy trading logic.

Trade відповідає за виконання торгових операцій з 2-phase commit pattern:
1. Phase 1 (RESERVE): Створ trade в PENDING, reserve funds
2. Exchange Call: Виконай на біржі
3. Phase 2 (CONFIRM): Оновлення trade на FILLED або FAILED
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.domain.shared import AggregateRoot, BusinessRuleViolation

from ..exceptions.trading_exceptions import (
    InsufficientBalanceError,
    InvalidTradeStateError,
    InvalidTradeSizeError,
)
from ..value_objects import TradeSide, TradeStatus, TradeType


class Trade(AggregateRoot):
    """Trade Aggregate Root.

    Правила:
    - Trade створюється в PENDING status
    - Funds резервуються при створенні (Phase 1)
    - Trade виконується на біржі
    - Trade переходить в FILLED або FAILED (Phase 2)
    - Trade immutable після FILLED/FAILED

    Example (2-Phase Commit):
        >>> # Phase 1: Reserve
        >>> trade = Trade.create_copy_trade(
        ...     user_id=1,
        ...     signal_id=100,
        ...     symbol="BTCUSDT",
        ...     side=TradeSide.BUY,
        ...     size_usdt=Decimal("100"),
        ... )
        >>> # trade.status == TradeStatus.PENDING
        >>> await trade_repo.save(trade)
        >>> await uow.commit()  # Commit Phase 1 (funds reserved)

        >>> # Exchange Call (може failнути)
        >>> order_result = await exchange.execute_spot_buy(...)

        >>> # Phase 2: Confirm
        >>> trade.execute(order_result)
        >>> # trade.status == TradeStatus.FILLED
        >>> await uow.commit()  # Commit Phase 2
    """

    def __init__(
        self,
        user_id: int,
        signal_id: Optional[int],
        symbol: str,
        side: TradeSide,
        trade_type: TradeType,
        size_usdt: Decimal,
        quantity: Decimal,
        leverage: int = 1,
        id: Optional[int] = None,
    ) -> None:
        """Initialize trade.

        Args:
            user_id: ID користувача.
            signal_id: ID whale signal (якщо це copy trade).
            symbol: Trading pair (e.g., "BTCUSDT").
            side: BUY або SELL.
            trade_type: SPOT, FUTURES_LONG, FUTURES_SHORT.
            size_usdt: Розмір trade в USDT.
            quantity: Кількість базового активу.
            leverage: Плече (1 для spot).
            id: Trade ID (None для нових).
        """
        super().__init__(id)

        # Validate inputs
        self._validate_trade_size(size_usdt)
        self._validate_quantity(quantity)

        # Core attributes
        self.user_id = user_id
        self.signal_id = signal_id
        self.symbol = symbol
        self.side = side
        self.trade_type = trade_type
        self.size_usdt = size_usdt
        self.quantity = quantity
        self.leverage = leverage

        # State
        self.status = TradeStatus.PENDING

        # Execution details (заповнюються після execution)
        self.executed_price: Optional[Decimal] = None
        self.executed_quantity: Optional[Decimal] = None
        self.exchange_order_id: Optional[str] = None
        self.fee_amount: Optional[Decimal] = None

        # Timestamps
        self.created_at = datetime.now(timezone.utc)
        self.executed_at: Optional[datetime] = None

        # Error tracking
        self.error_message: Optional[str] = None

    @classmethod
    def create_copy_trade(
        cls,
        user_id: int,
        signal_id: int,
        symbol: str,
        side: TradeSide,
        trade_type: TradeType,
        size_usdt: Decimal,
        quantity: Decimal,
        leverage: int = 1,
    ) -> "Trade":
        """Factory method для створення copy trade.

        Args:
            user_id: ID користувача.
            signal_id: ID whale signal.
            symbol: Trading pair.
            side: BUY або SELL.
            trade_type: SPOT, FUTURES_LONG, FUTURES_SHORT.
            size_usdt: Розмір trade в USDT.
            quantity: Кількість.
            leverage: Плече.

        Returns:
            Trade в PENDING status.

        Raises:
            InvalidTradeSizeError: Якщо розмір trade invalid.
        """
        return cls(
            user_id=user_id,
            signal_id=signal_id,
            symbol=symbol,
            side=side,
            trade_type=trade_type,
            size_usdt=size_usdt,
            quantity=quantity,
            leverage=leverage,
        )

    # Alias for semantic clarity
    create_pending = create_copy_trade

    def execute(
        self,
        executed_price: Decimal,
        executed_quantity: Decimal,
        exchange_order_id: str | None = None,
        order_id: str | None = None,
        fee_amount: Decimal | None = None,
        fee: Decimal | None = None,
    ) -> None:
        """Mark trade as successfully executed (Phase 2: CONFIRM).

        Args:
            executed_price: Ціна виконання.
            executed_quantity: Виконана кількість.
            exchange_order_id: Order ID з біржі (or use order_id alias).
            order_id: Alias for exchange_order_id.
            fee_amount: Комісія (or use fee alias).
            fee: Alias for fee_amount.

        Raises:
            InvalidTradeStateError: Якщо trade не в PENDING status.
        """
        # Handle aliases
        actual_order_id = exchange_order_id or order_id or ""
        actual_fee = fee_amount or fee or Decimal("0")

        if self.status != TradeStatus.PENDING:
            raise InvalidTradeStateError(
                "Cannot execute trade: invalid status",
                trade_id=self.id,
                current_status=self.status.value,
                expected_status=TradeStatus.PENDING.value,
            )

        self.status = TradeStatus.FILLED
        self.exchange_order_id = actual_order_id
        self.executed_price = executed_price
        self.executed_quantity = executed_quantity
        self.fee_amount = actual_fee
        self.executed_at = datetime.now(timezone.utc)

        # Emit TradeExecutedEvent
        from ..events.trade_events import TradeExecutedEvent

        self.add_domain_event(
            TradeExecutedEvent(
                trade_id=self.id or 0,
                user_id=self.user_id,
                signal_id=self.signal_id,
                symbol=self.symbol,
                side=self.side.value,
                executed_price=executed_price,
                executed_quantity=executed_quantity,
                fee_amount=actual_fee,
                exchange_order_id=actual_order_id,
            )
        )

    def fail(self, error_message: str) -> None:
        """Mark trade as failed (Phase 2: ROLLBACK).

        Викликається коли exchange call failed або інша помилка.

        Args:
            error_message: Опис помилки.

        Raises:
            InvalidTradeStateError: Якщо trade не в PENDING status.
        """
        if self.status != TradeStatus.PENDING:
            raise InvalidTradeStateError(
                "Cannot fail trade: invalid status",
                trade_id=self.id,
                current_status=self.status.value,
            )

        self.status = TradeStatus.FAILED
        self.error_message = error_message
        self.executed_at = datetime.now(timezone.utc)

        # Emit TradeFailedEvent
        from ..events.trade_events import TradeFailedEvent

        self.add_domain_event(
            TradeFailedEvent(
                trade_id=self.id or 0,
                user_id=self.user_id,
                signal_id=self.signal_id,
                symbol=self.symbol,
                error_message=error_message,
            )
        )

    def mark_needs_reconciliation(self, reason: str) -> None:
        """Mark trade для reconciliation.

        Викликається коли exchange call успішний але DB update failed.

        Args:
            reason: Причина reconciliation.
        """
        self.status = TradeStatus.NEEDS_RECONCILIATION
        self.error_message = f"Needs reconciliation: {reason}"

        # Emit TradeNeedsReconciliationEvent
        from ..events.trade_events import TradeNeedsReconciliationEvent

        self.add_domain_event(
            TradeNeedsReconciliationEvent(
                trade_id=self.id or 0,
                user_id=self.user_id,
                exchange_order_id=self.exchange_order_id,
                reason=reason,
            )
        )

    @property
    def is_pending(self) -> bool:
        """Check if trade очікує execution."""
        return self.status == TradeStatus.PENDING

    @property
    def is_filled(self) -> bool:
        """Check if trade успішно виконаний."""
        return self.status == TradeStatus.FILLED

    @property
    def is_failed(self) -> bool:
        """Check if trade failed."""
        return self.status == TradeStatus.FAILED

    @property
    def needs_reconciliation(self) -> bool:
        """Check if trade потребує reconciliation."""
        return self.status == TradeStatus.NEEDS_RECONCILIATION

    @property
    def is_final_state(self) -> bool:
        """Check if trade в final state (не може змінитись)."""
        return self.status in (TradeStatus.FILLED, TradeStatus.FAILED)

    def _validate_trade_size(self, size_usdt: Decimal) -> None:
        """Validate trade size.

        Args:
            size_usdt: Trade size in USDT.

        Raises:
            InvalidTradeSizeError: If size invalid.
        """
        if size_usdt <= Decimal("0"):
            raise InvalidTradeSizeError(
                "Trade size must be positive",
                size_usdt=str(size_usdt),
            )

        # TODO: Add minimum/maximum size validation based on exchange rules

    def _validate_quantity(self, quantity: Decimal) -> None:
        """Validate quantity.

        Args:
            quantity: Quantity to validate.

        Raises:
            InvalidTradeSizeError: If quantity invalid.
        """
        if quantity <= Decimal("0"):
            raise InvalidTradeSizeError(
                "Quantity must be positive",
                quantity=str(quantity),
            )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Trade(id={self.id}, user_id={self.user_id}, symbol={self.symbol}, "
            f"side={self.side.value}, status={self.status.value}, size_usdt={self.size_usdt})"
        )
