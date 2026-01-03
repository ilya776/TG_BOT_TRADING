"""
Settings Handlers
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserSettings, TradingMode, ExchangeName
from app.telegram.keyboards import get_settings_keyboard

router = Router()


class SettingsState(StatesGroup):
    """States for settings flow."""

    entering_trade_size = State()
    entering_stop_loss = State()
    entering_daily_limit = State()
    entering_api_key = State()
    entering_api_secret = State()
    entering_passphrase = State()


@router.message(F.text == "⚙️ Settings")
@router.message(Command("settings"))
async def show_settings(message: Message, user: User, db: AsyncSession):
    """Show settings menu."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    text = f"""
<b>⚙️ Settings</b>

<b>Trading</b>
├ Mode: {settings.trading_mode.value if settings else 'SPOT'}
├ Exchange: {settings.preferred_exchange.value if settings else 'BINANCE'}
└ Auto-Copy Delay: {settings.auto_copy_delay_seconds if settings else 10}s

<b>Position Sizing</b>
├ Default Size: ${settings.default_trade_size_usdt if settings else 100}
└ Max Size: ${settings.max_trade_size_usdt if settings else 1000}

<b>Risk Management</b>
├ Stop Loss: {settings.stop_loss_percent if settings else 10}%
├ Take Profit: {settings.take_profit_percent if settings else 'Not set'}%
└ Daily Loss Limit: ${settings.daily_loss_limit_usdt if settings else 500}

<b>Futures</b>
├ Default Leverage: {settings.default_leverage if settings else 5}x
└ Max Leverage: {settings.max_leverage if settings else 10}x

Select an option below to change:
"""

    await message.answer(text, reply_markup=get_settings_keyboard())


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, user: User, db: AsyncSession):
    """Return to settings menu."""
    await callback.answer()

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    text = f"""
<b>⚙️ Settings</b>

<b>Trading</b>
├ Mode: {settings.trading_mode.value if settings else 'SPOT'}
├ Exchange: {settings.preferred_exchange.value if settings else 'BINANCE'}
└ Auto-Copy Delay: {settings.auto_copy_delay_seconds if settings else 10}s

<b>Position Sizing</b>
├ Default Size: ${settings.default_trade_size_usdt if settings else 100}
└ Max Size: ${settings.max_trade_size_usdt if settings else 1000}

<b>Risk Management</b>
├ Stop Loss: {settings.stop_loss_percent if settings else 10}%
└ Daily Loss Limit: ${settings.daily_loss_limit_usdt if settings else 500}

Select an option below to change:
"""

    await callback.message.edit_text(text, reply_markup=get_settings_keyboard())


@router.callback_query(F.data == "settings_mode")
async def settings_mode(callback: CallbackQuery):
    """Show trading mode options."""
    await callback.answer()

    text = """
<b>📈 Trading Mode</b>

Select your trading mode:

<b>SPOT</b> - Buy/sell actual tokens
• No leverage
• No liquidation risk
• Recommended for beginners

<b>FUTURES</b> - Perpetual contracts
• Use leverage (5-10x)
• Higher profits potential
• Risk of liquidation

<b>MIXED</b> - 50% SPOT, 50% FUTURES
• Balanced approach
• Diversified risk
"""

    from app.telegram.keyboards import get_trading_mode_keyboard
    await callback.message.edit_text(text, reply_markup=get_trading_mode_keyboard())


@router.callback_query(F.data == "settings_exchange")
async def settings_exchange(callback: CallbackQuery):
    """Show exchange options."""
    await callback.answer()

    text = """
<b>💱 Preferred Exchange</b>

Select your exchange:

<b>🟡 Binance</b>
• Largest by volume
• Most liquid markets
• Low fees

<b>🟢 OKX</b>
• Advanced features
• Good for futures
• Competitive fees

<b>🟠 Bybit</b>
• Futures-focused
• High leverage options
• Fast execution
"""

    from app.telegram.keyboards import get_exchange_keyboard
    await callback.message.edit_text(text, reply_markup=get_exchange_keyboard())


@router.callback_query(F.data == "settings_trade_size")
async def settings_trade_size(callback: CallbackQuery, state: FSMContext):
    """Prompt for trade size setting."""
    await callback.answer()

    text = """
<b>💰 Default Trade Size</b>

Enter your default trade size in USDT.

This is the amount that will be used for each copy trade unless overridden for specific whales.

Example: <code>100</code>
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Cancel", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SettingsState.entering_trade_size)


@router.message(SettingsState.entering_trade_size)
async def handle_trade_size(message: Message, state: FSMContext, user: User, db: AsyncSession):
    """Handle trade size input."""
    try:
        from decimal import Decimal
        trade_size = Decimal(message.text.strip())

        if trade_size <= 0:
            await message.answer("Trade size must be positive. Try again:")
            return

        if trade_size > 10000:
            await message.answer("Maximum trade size is $10,000. Try again:")
            return

        # Update settings
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            settings.default_trade_size_usdt = trade_size
        else:
            settings = UserSettings(user_id=user.id, default_trade_size_usdt=trade_size)
            db.add(settings)

        await db.commit()
        await state.clear()

        await message.answer(f"✅ Default trade size set to ${trade_size}")

    except ValueError:
        await message.answer("Invalid number. Please enter a valid amount (e.g., 100):")


@router.callback_query(F.data == "settings_risk")
async def settings_risk(callback: CallbackQuery):
    """Show risk settings."""
    await callback.answer()

    text = """
<b>🛡️ Risk Settings</b>

Configure your risk management:
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Stop Loss %", callback_data="set_stop_loss")],
        [InlineKeyboardButton(text="💰 Daily Loss Limit", callback_data="set_daily_limit")],
        [InlineKeyboardButton(text="📊 Max Positions", callback_data="set_max_positions")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "set_stop_loss")
async def set_stop_loss(callback: CallbackQuery, state: FSMContext):
    """Prompt for stop loss setting."""
    await callback.answer()

    text = """
<b>🛑 Stop Loss Percentage</b>

Enter the percentage loss at which positions should automatically close.

Recommended: 5-10%

Example: <code>10</code> for 10%
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Cancel", callback_data="settings_risk")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SettingsState.entering_stop_loss)


@router.message(SettingsState.entering_stop_loss)
async def handle_stop_loss(message: Message, state: FSMContext, user: User, db: AsyncSession):
    """Handle stop loss input."""
    try:
        from decimal import Decimal
        stop_loss = Decimal(message.text.strip())

        if stop_loss <= 0 or stop_loss > 50:
            await message.answer("Stop loss must be between 1% and 50%. Try again:")
            return

        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            settings.stop_loss_percent = stop_loss
        else:
            settings = UserSettings(user_id=user.id, stop_loss_percent=stop_loss)
            db.add(settings)

        await db.commit()
        await state.clear()

        await message.answer(f"✅ Stop loss set to {stop_loss}%")

    except ValueError:
        await message.answer("Invalid number. Please enter a valid percentage (e.g., 10):")


@router.callback_query(F.data == "settings_api_keys")
async def settings_api_keys(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show API keys management."""
    await callback.answer()

    from app.models.user import UserAPIKey

    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == user.id)
    )
    api_keys = result.scalars().all()

    text = "<b>🔗 API Keys</b>\n\n"

    if api_keys:
        for key in api_keys:
            status = "✅ Active" if key.is_active else "❌ Inactive"
            mode = "🧪 Testnet" if key.is_testnet else "🌐 Live"
            text += f"• <b>{key.exchange.value}</b> {status} {mode}\n"
    else:
        text += "No API keys configured.\n"

    text += "\nAdd or manage your exchange API keys:"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Binance", callback_data="add_api_binance")],
        [InlineKeyboardButton(text="➕ Add OKX", callback_data="add_api_okx")],
        [InlineKeyboardButton(text="➕ Add Bybit", callback_data="add_api_bybit")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "settings_notifications")
async def settings_notifications(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show notification settings."""
    await callback.answer()

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    def status(enabled: bool) -> str:
        return "✅" if enabled else "❌"

    text = f"""
<b>🔔 Notification Settings</b>

{status(settings.notify_whale_alerts if settings else True)} Whale Alerts
{status(settings.notify_trade_executed if settings else True)} Trade Executed
{status(settings.notify_position_closed if settings else True)} Position Closed
{status(settings.notify_stop_loss_hit if settings else True)} Stop Loss Hit

Tap to toggle:
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐋 Whale Alerts", callback_data="toggle_notif_whale")],
        [InlineKeyboardButton(text="📈 Trade Executed", callback_data="toggle_notif_trade")],
        [InlineKeyboardButton(text="📊 Position Closed", callback_data="toggle_notif_position")],
        [InlineKeyboardButton(text="🛑 Stop Loss Hit", callback_data="toggle_notif_stoploss")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("toggle_notif_"))
async def toggle_notification(callback: CallbackQuery, user: User, db: AsyncSession):
    """Toggle a notification setting."""
    setting_name = callback.data.replace("toggle_notif_", "")

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    # Map callback to setting field
    field_map = {
        "whale": "notify_whale_alerts",
        "trade": "notify_trade_executed",
        "position": "notify_position_closed",
        "stoploss": "notify_stop_loss_hit",
    }

    field = field_map.get(setting_name)
    if field:
        current_value = getattr(settings, field)
        setattr(settings, field, not current_value)
        await db.commit()

    await callback.answer("Setting updated!")

    # Refresh the notification settings view
    await settings_notifications(callback, user, db)
