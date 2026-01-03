"""
Trade and Portfolio Handlers
"""

from decimal import Decimal

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.trade import Position, PositionStatus, Trade, TradeStatus
from app.telegram.keyboards import get_position_keyboard

router = Router()


@router.message(F.text == "💰 Portfolio")
@router.message(Command("portfolio"))
async def show_portfolio(message: Message, user: User, db: AsyncSession):
    """Show user's portfolio."""
    # Get open positions
    positions_result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.status == PositionStatus.OPEN,
        ).order_by(Position.opened_at.desc())
    )
    positions = positions_result.scalars().all()

    # Calculate totals
    total_value = sum(p.current_value_usdt or p.entry_value_usdt for p in positions)
    total_pnl = sum(p.unrealized_pnl for p in positions)
    total_pnl_percent = (total_pnl / total_value * 100) if total_value > 0 else Decimal("0")

    pnl_icon = "🟢" if total_pnl >= 0 else "🔴"

    text = f"""
<b>💰 Portfolio</b>

<b>Balance</b>
├ Total: ${user.total_balance:,.2f}
├ Available: ${user.available_balance:,.2f}
└ In Positions: ${total_value:,.2f}

<b>P&L</b>
└ {pnl_icon} ${total_pnl:+,.2f} ({total_pnl_percent:+.2f}%)

<b>Open Positions ({len(positions)})</b>
"""

    if positions:
        for pos in positions[:5]:  # Show first 5
            pos_pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            text += f"\n{pos_pnl_icon} <b>{pos.symbol}</b>\n"
            text += f"├ Entry: ${pos.entry_price:,.4f}\n"
            text += f"├ Current: ${pos.current_price:,.4f}\n"
            text += f"└ P&L: ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_percent:+.2f}%)\n"

        if len(positions) > 5:
            text += f"\n... and {len(positions) - 5} more positions"
    else:
        text += "\nNo open positions."

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 All Positions", callback_data="positions_list")],
        [InlineKeyboardButton(text="📈 Trade History", callback_data="trades_history")],
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_portfolio")],
    ])

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "refresh_portfolio")
async def refresh_portfolio(callback: CallbackQuery, user: User, db: AsyncSession):
    """Refresh portfolio."""
    await callback.answer("Refreshing...")
    # Re-run the portfolio function
    await show_portfolio(callback.message, user, db)


@router.callback_query(F.data == "positions_list")
async def positions_list(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show all open positions."""
    await callback.answer()

    positions_result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.status == PositionStatus.OPEN,
        ).order_by(Position.opened_at.desc())
    )
    positions = positions_result.scalars().all()

    if not positions:
        text = "No open positions."
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_portfolio")],
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        return

    text = "<b>📊 Open Positions</b>\n"

    for i, pos in enumerate(positions, 1):
        pos_pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
        side = "LONG" if pos.is_long else "SHORT"
        leverage = f" {pos.leverage}x" if pos.leverage else ""

        text += f"""
<b>{i}. {pos.symbol}</b> ({side}{leverage})
├ Entry: ${pos.entry_price:,.4f}
├ Current: ${pos.current_price:,.4f}
├ Qty: {pos.quantity:.4f}
├ Value: ${pos.current_value_usdt:,.2f}
└ {pos_pnl_icon} P&L: ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_percent:+.2f}%)
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    # Create buttons for each position
    buttons = []
    for pos in positions:
        buttons.append([
            InlineKeyboardButton(
                text=f"⚙️ {pos.symbol}",
                callback_data=f"pos_detail_{pos.id}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="◀️ Back", callback_data="back_to_portfolio")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("pos_detail_"))
async def position_detail(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show position details."""
    await callback.answer()

    position_id = int(callback.data.replace("pos_detail_", ""))

    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.user_id == user.id,
        )
    )
    pos = result.scalar_one_or_none()

    if not pos:
        await callback.message.edit_text("Position not found.")
        return

    pos_pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
    side = "LONG" if pos.is_long else "SHORT"
    leverage = f" {pos.leverage}x" if pos.leverage else ""
    pos_type = pos.position_type.value

    text = f"""
<b>📊 Position Details</b>

<b>{pos.symbol}</b> ({side}{leverage})
Exchange: {pos.exchange}
Type: {pos_type}

<b>Position</b>
├ Entry Price: ${pos.entry_price:,.6f}
├ Current Price: ${pos.current_price:,.6f}
├ Quantity: {pos.quantity:.6f}
└ Value: ${pos.current_value_usdt:,.2f}

<b>P&L</b>
└ {pos_pnl_icon} ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_percent:+.2f}%)

<b>Risk Management</b>
├ Stop Loss: {f'${pos.stop_loss_price:,.4f}' if pos.stop_loss_price else 'Not set'}
├ Take Profit: {f'${pos.take_profit_price:,.4f}' if pos.take_profit_price else 'Not set'}
└ Liquidation: {f'${pos.liquidation_price:,.4f}' if pos.liquidation_price else 'N/A'}

<b>Opened:</b> {pos.opened_at.strftime('%Y-%m-%d %H:%M')} UTC
"""

    keyboard = get_position_keyboard(position_id)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("close_pos_"))
async def close_position(callback: CallbackQuery, user: User, db: AsyncSession):
    """Confirm position close."""
    position_id = int(callback.data.replace("close_pos_", ""))

    from app.telegram.keyboards import get_confirmation_keyboard
    keyboard = get_confirmation_keyboard("close_position", position_id)

    await callback.message.edit_text(
        "⚠️ <b>Close Position?</b>\n\nThis will close your position at market price.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("confirm_close_position_"))
async def confirm_close_position(callback: CallbackQuery, user: User, db: AsyncSession):
    """Execute position close."""
    position_id = int(callback.data.replace("confirm_close_position_", ""))

    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.user_id == user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    pos = result.scalar_one_or_none()

    if not pos:
        await callback.answer("Position not found or already closed", show_alert=True)
        return

    # TODO: Execute actual close on exchange
    # For now, just update the status
    from datetime import datetime
    from app.models.trade import CloseReason

    pos.status = PositionStatus.CLOSED
    pos.close_reason = CloseReason.MANUAL
    pos.closed_at = datetime.utcnow()
    pos.exit_price = pos.current_price
    pos.realized_pnl = pos.unrealized_pnl
    pos.realized_pnl_percent = pos.unrealized_pnl_percent

    # Return funds to user
    user.available_balance += pos.current_value_usdt + pos.realized_pnl

    await db.commit()

    await callback.answer("Position closed!", show_alert=True)
    await callback.message.edit_text(
        f"✅ Position {pos.symbol} closed.\n\nRealized P&L: ${pos.realized_pnl:+,.2f}"
    )


@router.message(F.text == "📈 Trades")
@router.message(Command("trades"))
async def show_trades(message: Message, user: User, db: AsyncSession):
    """Show trade history."""
    await send_trade_history(message, user, db)


@router.callback_query(F.data == "trades_history")
async def callback_trades_history(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show trade history from callback."""
    await callback.answer()
    await send_trade_history(callback.message, user, db, edit=True)


async def send_trade_history(
    message: Message,
    user: User,
    db: AsyncSession,
    edit: bool = False,
):
    """Send trade history."""
    result = await db.execute(
        select(Trade)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.desc())
        .limit(10)
    )
    trades = result.scalars().all()

    if not trades:
        text = "No trade history yet."
    else:
        text = "<b>📈 Recent Trades</b>\n"

        for trade in trades:
            status_icon = "✅" if trade.status == TradeStatus.FILLED else "⏳"
            side_icon = "🟢" if trade.side.value == "BUY" else "🔴"

            text += f"""
{status_icon} {side_icon} <b>{trade.symbol}</b>
├ {trade.side.value} {trade.quantity:.4f}
├ Price: ${trade.executed_price:,.4f}
├ Value: ${trade.trade_value_usdt:,.2f}
└ {trade.created_at.strftime('%m/%d %H:%M')}
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_portfolio")],
    ])

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "back_to_portfolio")
async def back_to_portfolio(callback: CallbackQuery, user: User, db: AsyncSession):
    """Return to portfolio view."""
    await callback.answer()
    # Delete current message and send portfolio as new message
    await callback.message.delete()
    await show_portfolio(callback.message, user, db)
