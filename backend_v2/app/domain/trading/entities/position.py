"""Position Aggregate Root - управління відкритими позиціями.

Position відповідає за:
- Tracking відкритих позицій
- Stop-loss та take-profit logic
- PnL calculation (unrealized, realized)
- Position lifecycle (OPEN → CLOSED/LIQUIDATED)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.domain.shared import AggregateRoot

from ..exceptions.trading_exceptions import PositionAlreadyClosedError, PositionNotFoundError
from ..value_objects import PositionSide, PositionStatus


class Position(AggregateRoot):
    """Position Aggregate Root.

    Правила:
    - Position створюється при успішному trade
    - Position має entry trade (відкриття) та optional exit trade (закриття)
    - Position може мати SL/TP prices
    - Unrealized PnL розраховується на основі current price
    - Realized PnL встановлюється при закритті

    Example:
        >>> # Entry trade executed
        >>> position = Position.create_from_trade(
        ...     user_id=1,
        ...     symbol="BTCUSDT",
        ...     side=PositionSide.LONG,
        ...     entry_price=Decimal("50000"),
        ...     quantity=Decimal("0.1"),
        ...     entry_trade_id=123,
        ... )
        >>> # position.status == PositionStatus.OPEN

        >>> # Check if SL triggered
        >>> current_price = Decimal("49000")
        >>> if position.should_trigger_stop_loss(current_price):
        ...     # Close position
        ...     position.close(exit_price=current_price, exit_trade_id=456)
    """

    def __init__(
        self,
        user_id: int,
        symbol: str,
        side: PositionSide,
        entry_price: Decimal,
        quantity: Decimal,
        entry_trade_id: int,
        leverage: int = 1,
        stop_loss_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
        id: Optional[int] = None,
    ) -> None:
        """Initialize position.

        Args:
            user_id: ID користувача.
            symbol: Trading pair.
            side: LONG або SHORT.
            entry_price: Ціна входу.
            quantity: Кількість (в базовій валюті).
            entry_trade_id: ID trade який відкрив позицію.
            leverage: Плече (1 для spot).
            stop_loss_price: Stop-loss ціна (optional).
            take_profit_price: Take-profit ціна (optional).
            id: Position ID.
        """
        super().__init__(id)

        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_trade_id = entry_trade_id
        self.leverage = leverage

        # Risk management
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price

        # State
        self.status = PositionStatus.OPEN

        # Exit details (заповнюються при закритті)
        self.exit_price: Optional[Decimal] = None
        self.exit_trade_id: Optional[int] = None

        # PnL
        self.unrealized_pnl: Decimal = Decimal("0")
        self.realized_pnl: Optional[Decimal] = None

        # Timestamps
        self.opened_at = datetime.now(timezone.utc)
        self.closed_at: Optional[datetime] = None

    @classmethod
    def create_from_trade(
        cls,
        user_id: int,
        symbol: str,
        side: PositionSide,
        entry_price: Decimal,
        quantity: Decimal,
        entry_trade_id: int,
        leverage: int = 1,
        stop_loss_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
    ) -> "Position":
        """Factory method для створення position з trade.

        Args:
            user_id: ID користувача.
            symbol: Trading pair.
            side: LONG або SHORT.
            entry_price: Ціна входу.
            quantity: Кількість.
            entry_trade_id: ID entry trade.
            leverage: Плече.
            stop_loss_price: SL ціна.
            take_profit_price: TP ціна.

        Returns:
            Position в OPEN status.
        """
        position = cls(
            user_id=user_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_trade_id=entry_trade_id,
            leverage=leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
        )

        # Emit PositionOpenedEvent (only for new positions created via factory)
        from ..events.position_events import PositionOpenedEvent

        position.add_domain_event(
            PositionOpenedEvent(
                position_id=position.id or 0,
                user_id=user_id,
                symbol=symbol,
                side=side.value,
                entry_price=entry_price,
                quantity=quantity,
                leverage=leverage,
                entry_trade_id=entry_trade_id,
            )
        )

        return position

    def update_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Оновити unrealized PnL на основі current price.

        Args:
            current_price: Поточна ринкова ціна.

        Returns:
            Новий unrealized PnL.

        Raises:
            PositionAlreadyClosedError: Якщо position вже закрита.
        """
        if self.status != PositionStatus.OPEN:
            raise PositionAlreadyClosedError(
                "Cannot update PnL for closed position",
                position_id=self.id,
                status=self.status.value,
            )

        self.unrealized_pnl = self._calculate_pnl(
            entry_price=self.entry_price, exit_price=current_price, quantity=self.quantity
        )

        return self.unrealized_pnl

    def should_trigger_stop_loss(self, current_price: Decimal) -> bool:
        """Перевірити чи треба trigger stop-loss.

        Args:
            current_price: Поточна ціна.

        Returns:
            True якщо SL треба trigger.
        """
        if not self.stop_loss_price or self.status != PositionStatus.OPEN:
            return False

        if self.side == PositionSide.LONG:
            # Long: SL triggers коли ціна падає нижче SL
            return current_price <= self.stop_loss_price
        else:
            # Short: SL triggers коли ціна зростає вище SL
            return current_price >= self.stop_loss_price

    def should_trigger_take_profit(self, current_price: Decimal) -> bool:
        """Перевірити чи треба trigger take-profit.

        Args:
            current_price: Поточна ціна.

        Returns:
            True якщо TP треба trigger.
        """
        if not self.take_profit_price or self.status != PositionStatus.OPEN:
            return False

        if self.side == PositionSide.LONG:
            # Long: TP triggers коли ціна зростає вище TP
            return current_price >= self.take_profit_price
        else:
            # Short: TP triggers коли ціна падає нижче TP
            return current_price <= self.take_profit_price

    def close(self, exit_price: Decimal, exit_trade_id: int) -> Decimal:
        """Закрити position.

        Args:
            exit_price: Ціна виходу.
            exit_trade_id: ID exit trade.

        Returns:
            Realized PnL.

        Raises:
            PositionAlreadyClosedError: Якщо position вже закрита.
        """
        if self.status != PositionStatus.OPEN:
            raise PositionAlreadyClosedError(
                "Position already closed",
                position_id=self.id,
                status=self.status.value,
            )

        self.status = PositionStatus.CLOSED
        self.exit_price = exit_price
        self.exit_trade_id = exit_trade_id
        self.closed_at = datetime.now(timezone.utc)

        # Calculate realized PnL
        self.realized_pnl = self._calculate_pnl(
            entry_price=self.entry_price, exit_price=exit_price, quantity=self.quantity
        )

        # Clear unrealized PnL
        self.unrealized_pnl = Decimal("0")

        # Emit PositionClosedEvent
        from ..events.position_events import PositionClosedEvent

        self.add_domain_event(
            PositionClosedEvent(
                position_id=self.id or 0,
                user_id=self.user_id,
                symbol=self.symbol,
                side=self.side.value,
                entry_price=self.entry_price,
                exit_price=exit_price,
                quantity=self.quantity,
                realized_pnl=self.realized_pnl,
                exit_trade_id=exit_trade_id,
            )
        )

        return self.realized_pnl

    def liquidate(self, liquidation_price: Decimal) -> None:
        """Mark position як liquidated (ліквідована біржею).

        Args:
            liquidation_price: Ціна ліквідації.
        """
        self.status = PositionStatus.LIQUIDATED
        self.exit_price = liquidation_price
        self.closed_at = datetime.now(timezone.utc)

        # Calculate realized PnL (зазвичай negative при liquidation)
        self.realized_pnl = self._calculate_pnl(
            entry_price=self.entry_price, exit_price=liquidation_price, quantity=self.quantity
        )

        self.unrealized_pnl = Decimal("0")

        # Emit PositionLiquidatedEvent
        from ..events.position_events import PositionLiquidatedEvent

        self.add_domain_event(
            PositionLiquidatedEvent(
                position_id=self.id or 0,
                user_id=self.user_id,
                symbol=self.symbol,
                liquidation_price=liquidation_price,
                realized_pnl=self.realized_pnl,
            )
        )

    def update_stop_loss(self, new_stop_loss: Decimal) -> None:
        """Оновити stop-loss ціну.

        Args:
            new_stop_loss: Нова SL ціна.

        Raises:
            PositionAlreadyClosedError: Якщо position закрита.
        """
        if self.status != PositionStatus.OPEN:
            raise PositionAlreadyClosedError(
                "Cannot update SL for closed position", position_id=self.id
            )

        self.stop_loss_price = new_stop_loss

    def update_take_profit(self, new_take_profit: Decimal) -> None:
        """Оновити take-profit ціну.

        Args:
            new_take_profit: Нова TP ціна.

        Raises:
            PositionAlreadyClosedError: Якщо position закрита.
        """
        if self.status != PositionStatus.OPEN:
            raise PositionAlreadyClosedError(
                "Cannot update TP for closed position", position_id=self.id
            )

        self.take_profit_price = new_take_profit

    @property
    def is_open(self) -> bool:
        """Check if position відкрита."""
        return self.status == PositionStatus.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if position закрита."""
        return self.status == PositionStatus.CLOSED

    @property
    def is_liquidated(self) -> bool:
        """Check if position ліквідована."""
        return self.status == PositionStatus.LIQUIDATED

    @property
    def is_profitable(self) -> bool:
        """Check if position прибуткова (based on unrealized або realized PnL)."""
        if self.status == PositionStatus.OPEN:
            return self.unrealized_pnl > Decimal("0")
        else:
            return self.realized_pnl is not None and self.realized_pnl > Decimal("0")

    @property
    def position_value_usdt(self) -> Decimal:
        """Розрахувати поточну вартість позиції в USDT."""
        current_price = self.exit_price if self.exit_price else self.entry_price
        return self.quantity * current_price

    def _calculate_pnl(
        self, entry_price: Decimal, exit_price: Decimal, quantity: Decimal
    ) -> Decimal:
        """Розрахувати PnL.

        Args:
            entry_price: Ціна входу.
            exit_price: Ціна виходу.
            quantity: Кількість.

        Returns:
            PnL в USDT.
        """
        if self.side == PositionSide.LONG:
            # Long: profit = (exit - entry) * quantity
            pnl = (exit_price - entry_price) * quantity
        else:
            # Short: profit = (entry - exit) * quantity
            pnl = (entry_price - exit_price) * quantity

        # Apply leverage
        pnl = pnl * self.leverage

        return pnl

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Position(id={self.id}, user_id={self.user_id}, symbol={self.symbol}, "
            f"side={self.side.value}, status={self.status.value}, "
            f"unrealized_pnl={self.unrealized_pnl})"
        )
