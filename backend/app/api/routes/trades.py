"""
Trade API Routes
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models.trade import (
    CloseReason,
    Position,
    PositionStatus,
    Trade,
    TradeSide,
    TradeStatus,
    TradeType,
)

router = APIRouter()


# Pydantic schemas
class TradeResponse(BaseModel):
    id: int
    signal_id: int | None
    whale_id: int | None
    is_copy_trade: bool
    exchange: str
    symbol: str
    trade_type: str
    side: str
    quantity: Decimal
    filled_quantity: Decimal
    executed_price: Decimal | None
    trade_value_usdt: Decimal
    leverage: int | None
    fee_amount: Decimal
    commission_amount: Decimal
    status: str
    error_message: str | None
    created_at: datetime
    executed_at: datetime | None

    class Config:
        from_attributes = True


class PositionResponse(BaseModel):
    id: int
    whale_id: int | None
    exchange: str
    symbol: str
    position_type: str
    side: str
    quantity: Decimal
    remaining_quantity: Decimal
    entry_price: Decimal
    current_price: Decimal | None
    exit_price: Decimal | None
    entry_value_usdt: Decimal
    current_value_usdt: Decimal | None
    leverage: int | None
    liquidation_price: Decimal | None
    stop_loss_price: Decimal | None
    take_profit_price: Decimal | None
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    realized_pnl: Decimal
    realized_pnl_percent: Decimal
    total_fees: Decimal
    status: str
    close_reason: str | None
    opened_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True


class UpdatePositionRequest(BaseModel):
    stop_loss_price: Decimal | None = Field(None, gt=0)
    take_profit_price: Decimal | None = Field(None, gt=0)
    trailing_stop_percent: Decimal | None = Field(None, ge=0.5, le=20)


class ClosePositionRequest(BaseModel):
    reason: CloseReason = CloseReason.MANUAL


class PortfolioSummary(BaseModel):
    total_value: Decimal
    available_balance: Decimal
    positions_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    realized_pnl_today: Decimal
    realized_pnl_week: Decimal
    realized_pnl_month: Decimal
    open_positions_count: int


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: TradeStatus | None = None,
    symbol: str | None = None,
    side: TradeSide | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Trade]:
    """List user's trade history."""
    query = select(Trade).where(Trade.user_id == current_user.id)

    if status_filter:
        query = query.where(Trade.status == status_filter)
    if symbol:
        query = query.where(Trade.symbol == symbol.upper())
    if side:
        query = query.where(Trade.side == side)

    query = query.order_by(Trade.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/trades/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> Trade:
    """Get a specific trade."""
    result = await db.execute(
        select(Trade).where(
            Trade.id == trade_id,
            Trade.user_id == current_user.id,
        )
    )
    trade = result.scalar_one_or_none()

    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found",
        )

    return trade


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: PositionStatus | None = None,
    symbol: str | None = None,
) -> list[Position]:
    """List user's positions."""
    query = select(Position).where(Position.user_id == current_user.id)

    if status_filter:
        query = query.where(Position.status == status_filter)
    else:
        # Default to open positions
        query = query.where(Position.status == PositionStatus.OPEN)

    if symbol:
        query = query.where(Position.symbol == symbol.upper())

    query = query.order_by(Position.opened_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/positions/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> Position:
    """Get a specific position."""
    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.user_id == current_user.id,
        )
    )
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    return position


@router.patch("/positions/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: int,
    request: UpdatePositionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Position:
    """Update position settings (stop-loss, take-profit)."""
    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.user_id == current_user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Open position not found",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(position, field, value)

    await db.commit()
    await db.refresh(position)

    # TODO: Update stop-loss/take-profit orders on exchange

    return position


@router.post("/positions/{position_id}/close", response_model=PositionResponse)
async def close_position(
    position_id: int,
    request: ClosePositionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Position:
    """Manually close a position."""
    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.user_id == current_user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Open position not found",
        )

    # TODO: Execute close order on exchange
    # For now, just update status
    position.status = PositionStatus.CLOSED
    position.close_reason = request.reason
    position.closed_at = datetime.utcnow()
    position.exit_price = position.current_price  # Use current price as exit
    position.realized_pnl = position.unrealized_pnl
    position.realized_pnl_percent = position.unrealized_pnl_percent

    await db.commit()
    await db.refresh(position)

    return position


@router.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> PortfolioSummary:
    """Get portfolio summary."""
    from datetime import timedelta

    # Get open positions stats
    positions_result = await db.execute(
        select(
            func.count(Position.id).label("count"),
            func.sum(Position.current_value_usdt).label("total_value"),
            func.sum(Position.unrealized_pnl).label("unrealized_pnl"),
        ).where(
            Position.user_id == current_user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    positions_stats = positions_result.first()

    positions_count = positions_stats.count or 0
    positions_value = positions_stats.total_value or Decimal("0")
    unrealized_pnl = positions_stats.unrealized_pnl or Decimal("0")

    # Calculate unrealized PnL percent
    total_entry_value = await db.execute(
        select(func.sum(Position.entry_value_usdt)).where(
            Position.user_id == current_user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    entry_value = total_entry_value.scalar() or Decimal("0")
    unrealized_pnl_percent = (
        (unrealized_pnl / entry_value * 100) if entry_value > 0 else Decimal("0")
    )

    # Get realized PnL for different periods
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    async def get_realized_pnl_since(since: datetime) -> Decimal:
        result = await db.execute(
            select(func.sum(Position.realized_pnl)).where(
                Position.user_id == current_user.id,
                Position.status == PositionStatus.CLOSED,
                Position.closed_at >= since,
            )
        )
        return result.scalar() or Decimal("0")

    realized_pnl_today = await get_realized_pnl_since(today_start)
    realized_pnl_week = await get_realized_pnl_since(week_start)
    realized_pnl_month = await get_realized_pnl_since(month_start)

    total_value = current_user.available_balance + positions_value

    return PortfolioSummary(
        total_value=total_value,
        available_balance=current_user.available_balance,
        positions_value=positions_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_pnl_percent.quantize(Decimal("0.01")),
        realized_pnl_today=realized_pnl_today,
        realized_pnl_week=realized_pnl_week,
        realized_pnl_month=realized_pnl_month,
        open_positions_count=positions_count,
    )


@router.get("/symbols", response_model=list[str])
async def list_traded_symbols(
    current_user: CurrentUser,
    db: DbSession,
) -> list[str]:
    """Get list of symbols the user has traded."""
    result = await db.execute(
        select(Trade.symbol)
        .where(Trade.user_id == current_user.id)
        .distinct()
        .order_by(Trade.symbol)
    )
    return [row[0] for row in result.all()]
