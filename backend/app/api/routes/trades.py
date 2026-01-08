"""
Trade API Routes
"""

import logging
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
from app.models.user import ExchangeName, UserAPIKey
from app.services.exchanges import PositionSide, get_exchange_executor
from app.utils.encryption import get_encryption_manager

logger = logging.getLogger(__name__)

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
    # F3: Win rate and trade statistics
    total_closed_positions: int = 0
    winning_positions: int = 0
    losing_positions: int = 0
    win_rate: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")  # gross_profit / gross_loss
    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")


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
    """Manually close a position on the exchange."""
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

    # Get user's API key for this exchange
    try:
        exchange_enum = ExchangeName(position.exchange.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid exchange: {position.exchange}",
        )

    keys_result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.exchange == exchange_enum,
            UserAPIKey.is_active == True,
        )
    )
    api_key = keys_result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No active API key found for {position.exchange}. Please add API key in Settings.",
        )

    # Decrypt credentials
    encryption = get_encryption_manager()
    decrypted_key = encryption.decrypt(api_key.api_key_encrypted)
    decrypted_secret = encryption.decrypt(api_key.api_secret_encrypted)
    decrypted_passphrase = None
    if api_key.passphrase_encrypted:
        decrypted_passphrase = encryption.decrypt(api_key.passphrase_encrypted)

    # Initialize exchange executor
    executor = None
    try:
        executor = get_exchange_executor(
            exchange_name=exchange_enum.value.lower(),
            api_key=decrypted_key,
            api_secret=decrypted_secret,
            passphrase=decrypted_passphrase,
            testnet=api_key.is_testnet,
        )
        await executor.initialize()

        # Execute close order based on position type
        # Use position_type as primary indicator - leverage doesn't determine spot/futures
        # (futures can have 1x leverage in cross margin mode)
        is_spot = position.position_type == TradeType.SPOT
        quantity = Decimal(str(position.quantity)) if position.quantity else None

        logger.info(f"Close position {position_id}: type={position.position_type}, leverage={position.leverage}, is_spot={is_spot}")

        if is_spot:
            # For spot: get actual balance from exchange and sell that
            asset = position.symbol.replace("USDT", "")
            balances = await executor.get_account_balance()
            asset_balance = next((b for b in balances if b.asset == asset), None)

            if not asset_balance or asset_balance.free <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No {asset} balance available to sell",
                )

            # Use actual balance from exchange (may differ slightly from DB)
            actual_quantity = asset_balance.free
            logger.info(f"Closing SPOT position: selling {actual_quantity} {asset} (DB had {quantity})")

            order_result = await executor.spot_market_sell(
                symbol=position.symbol,
                quantity=actual_quantity,
            )

            # Check for remaining dust after LOT_SIZE rounding
            filled_qty = order_result.filled_quantity or Decimal("0")
            dust_remaining = actual_quantity - filled_qty
            if dust_remaining > 0:
                dust_value = dust_remaining * (order_result.avg_fill_price or Decimal("0"))
                logger.warning(
                    f"Dust remaining after close: {dust_remaining} {asset} (~${dust_value:.2f}). "
                    f"This is due to exchange LOT_SIZE filter. Use Binance 'Convert Small Balance to BNB' to clean up."
                )
        else:
            # For futures: close the position
            position_side = PositionSide.LONG if position.side == "BUY" else PositionSide.SHORT
            logger.info(f"Closing FUTURES position: {position_side.value} {position.symbol}")
            order_result = await executor.futures_close_position(
                symbol=position.symbol,
                position_side=position_side,
                quantity=quantity,
            )

        # Update position with actual execution results - do this FIRST before any calculations
        now = datetime.utcnow()
        position.status = PositionStatus.CLOSED
        position.close_reason = request.reason
        position.closed_at = now
        position.exit_price = order_result.avg_fill_price if order_result.avg_fill_price else position.current_price

        # Update filled quantity from actual order
        if order_result.filled_quantity:
            position.remaining_quantity = Decimal("0")

        logger.info(f"Position {position_id} closed at {now}, exit_price={position.exit_price}")

        # Calculate realized PnL based on actual exit price (wrapped in try to not lose close status)
        # F1: Include fees in PnL calculation
        # F2: Include leverage in PnL percent (for futures, ROI on margin = price_change_% * leverage)
        try:
            if position.exit_price and position.entry_price:
                entry = Decimal(str(position.entry_price))
                exit_price = Decimal(str(position.exit_price))
                size = Decimal(str(position.entry_value_usdt or 0))
                leverage = position.leverage or 1
                fees = Decimal(str(position.total_fees or 0))

                if entry > 0 and size > 0:
                    # Calculate price change percentage
                    if position.side == "BUY":
                        price_change_pct = ((exit_price - entry) / entry) * 100
                    else:
                        price_change_pct = ((entry - exit_price) / entry) * 100

                    # For futures with leverage, actual ROI on margin = price_change * leverage
                    # For spot (leverage=1), this is unchanged
                    pnl_percent = price_change_pct * Decimal(leverage)

                    # Calculate gross PnL
                    gross_pnl = (price_change_pct / 100) * size * Decimal(leverage)

                    # Subtract fees for net PnL
                    position.realized_pnl = gross_pnl - fees
                    position.realized_pnl_percent = pnl_percent

                    # Adjust percent for fees if significant
                    if size > 0 and fees > 0:
                        fee_impact_pct = (fees / size) * 100 * Decimal(leverage)
                        position.realized_pnl_percent = pnl_percent - fee_impact_pct

                    logger.info(
                        f"PnL calculation: entry={entry}, exit={exit_price}, leverage={leverage}x, "
                        f"price_change={price_change_pct:.2f}%, gross_pnl={gross_pnl:.2f}, "
                        f"fees={fees:.2f}, net_pnl={position.realized_pnl:.2f} ({position.realized_pnl_percent:.2f}%)"
                    )
                else:
                    position.realized_pnl = position.unrealized_pnl or Decimal("0")
                    position.realized_pnl_percent = position.unrealized_pnl_percent or Decimal("0")
            else:
                position.realized_pnl = position.unrealized_pnl or Decimal("0")
                position.realized_pnl_percent = position.unrealized_pnl_percent or Decimal("0")
        except Exception as pnl_error:
            logger.error(f"Failed to calculate PnL for position {position_id}: {pnl_error}")
            position.realized_pnl = Decimal("0")
            position.realized_pnl_percent = Decimal("0")

        logger.info(f"Position {position_id} closed successfully. PnL: {position.realized_pnl} ({position.realized_pnl_percent}%)")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close position {position_id} on exchange: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close position on exchange: {str(e)}",
        )
    finally:
        if executor:
            await executor.close()

    await db.commit()
    await db.refresh(position)

    return position


@router.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> PortfolioSummary:
    """Get portfolio summary with win rate and trade statistics."""
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

    # F3: Calculate win rate and trade statistics
    # Get all closed positions for statistics
    closed_positions_result = await db.execute(
        select(Position.realized_pnl).where(
            Position.user_id == current_user.id,
            Position.status == PositionStatus.CLOSED,
        )
    )
    closed_positions = [row[0] or Decimal("0") for row in closed_positions_result.all()]

    total_closed = len(closed_positions)
    winning_trades = [p for p in closed_positions if p > 0]
    losing_trades = [p for p in closed_positions if p < 0]

    winning_count = len(winning_trades)
    losing_count = len(losing_trades)

    # Calculate win rate
    win_rate = Decimal("0")
    if total_closed > 0:
        win_rate = (Decimal(winning_count) / Decimal(total_closed)) * 100

    # Calculate average win/loss
    average_win = Decimal("0")
    average_loss = Decimal("0")
    if winning_trades:
        average_win = sum(winning_trades) / len(winning_trades)
    if losing_trades:
        average_loss = abs(sum(losing_trades)) / len(losing_trades)

    # Calculate profit factor (gross profit / gross loss)
    gross_profit = sum(winning_trades) if winning_trades else Decimal("0")
    gross_loss = abs(sum(losing_trades)) if losing_trades else Decimal("0")
    profit_factor = Decimal("0")
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss

    # Largest win/loss
    largest_win = max(winning_trades) if winning_trades else Decimal("0")
    largest_loss = abs(min(losing_trades)) if losing_trades else Decimal("0")

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
        # F3: Trade statistics
        total_closed_positions=total_closed,
        winning_positions=winning_count,
        losing_positions=losing_count,
        win_rate=win_rate.quantize(Decimal("0.01")),
        average_win=average_win.quantize(Decimal("0.01")),
        average_loss=average_loss.quantize(Decimal("0.01")),
        profit_factor=profit_factor.quantize(Decimal("0.01")),
        largest_win=largest_win.quantize(Decimal("0.01")),
        largest_loss=largest_loss.quantize(Decimal("0.01")),
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
