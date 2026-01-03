"""
Start and Onboarding Handlers
"""

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.telegram.keyboards import (
    get_main_menu_keyboard,
    get_start_keyboard,
    get_trading_mode_keyboard,
)

router = Router()


class OnboardingState(StatesGroup):
    """States for onboarding flow."""

    selecting_mode = State()
    connecting_exchange = State()
    setting_trade_size = State()
    selecting_whales = State()


WELCOME_MESSAGE = """
<b>Welcome to Whale Copy Trading Bot!</b> 🐋

Copy trades from successful crypto whales automatically.

<b>What we offer:</b>
• Real-time whale transaction monitoring
• Auto-copy trades to your exchange account
• Support for Binance, OKX, and Bybit
• Both SPOT and FUTURES trading
• Risk management & stop-loss

<b>How it works:</b>
1. Connect your exchange API
2. Follow profitable whales
3. Enable auto-copy
4. Profit! 🚀

Get started below or open our Mini App for the full experience.
"""

HOW_IT_WORKS = """
<b>How Whale Copy Trading Works</b> 🐋

<b>1. Whale Monitoring</b>
We track on-chain transactions from successful traders on DEXes like Uniswap and PancakeSwap.

<b>2. Signal Detection</b>
When a whale makes a significant trade, we instantly detect it and analyze the opportunity.

<b>3. Copy Execution</b>
If you're following that whale with auto-copy enabled, we execute the same trade on your exchange account.

<b>4. Risk Management</b>
Our system respects your risk settings - trade size limits, stop-loss, daily loss limits.

<b>Subscription Tiers:</b>

🆓 <b>FREE</b>
• 1 whale to follow
• Manual copy only
• 2% commission

⭐ <b>PRO</b> - $99/mo
• 5 whales
• Auto-copy enabled
• FUTURES trading
• 1% commission

💎 <b>ELITE</b> - $299/mo
• Unlimited whales
• Flash copy
• AI whale scoring
• 0.5% commission

Ready to start? Click "Get Started" below!
"""


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Handle /start command."""
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_start_keyboard(),
    )

    # Also send main menu keyboard
    await message.answer(
        "Use the menu below to navigate:",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = """
<b>Available Commands:</b>

/start - Start the bot
/help - Show this help
/dashboard - View your dashboard
/whales - Browse and follow whales
/portfolio - View your portfolio
/trades - View trade history
/settings - Configure your settings
/subscription - Manage subscription

<b>Quick Actions:</b>
• Reply to a whale alert with "copy" to copy the trade
• Reply with "skip" to skip
• Use the buttons in alerts for quick actions

Need help? Contact @support
"""
    await message.answer(help_text)


@router.callback_query(F.data == "onboarding_start")
async def start_onboarding(callback: CallbackQuery, state: FSMContext, user: User):
    """Start the onboarding flow."""
    await callback.answer()

    text = """
<b>Step 1: Choose Your Trading Mode</b>

Select how you want to trade:

<b>📈 SPOT</b>
• Safest option
• No leverage
• No liquidation risk
• Best for beginners

<b>🚀 FUTURES</b>
• Higher risk/reward
• Use leverage (5-10x)
• Risk of liquidation
• For experienced traders

<b>⚖️ MIXED</b>
• 50% SPOT, 50% FUTURES
• Balanced approach
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_trading_mode_keyboard(),
    )
    await state.set_state(OnboardingState.selecting_mode)


@router.callback_query(F.data == "how_it_works")
async def show_how_it_works(callback: CallbackQuery):
    """Show how it works explanation."""
    await callback.answer()
    await callback.message.edit_text(
        HOW_IT_WORKS,
        reply_markup=get_start_keyboard(),
    )


@router.callback_query(F.data.startswith("mode_"))
async def handle_mode_selection(
    callback: CallbackQuery,
    state: FSMContext,
    db: AsyncSession,
    user: User,
):
    """Handle trading mode selection."""
    await callback.answer()

    mode = callback.data.replace("mode_", "").upper()

    # Update user settings
    from sqlalchemy import select
    from app.models.user import UserSettings, TradingMode

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    if settings:
        settings.trading_mode = TradingMode(mode)
    else:
        settings = UserSettings(
            user_id=user.id,
            trading_mode=TradingMode(mode),
        )
        db.add(settings)

    await db.commit()

    text = f"""
<b>Trading Mode Set: {mode}</b> ✅

<b>Step 2: Connect Your Exchange</b>

To copy trades, you need to connect your exchange API.

<b>Important Security Notes:</b>
• Only enable Spot/Futures trading
• <b>NEVER</b> enable withdrawal permissions
• Use IP restriction (your server IP)
• Enable 2FA on your exchange

Select your exchange to get setup instructions:
"""

    from app.telegram.keyboards import get_exchange_keyboard
    await callback.message.edit_text(
        text,
        reply_markup=get_exchange_keyboard(),
    )
    await state.set_state(OnboardingState.connecting_exchange)


@router.callback_query(F.data.startswith("exchange_"))
async def handle_exchange_selection(callback: CallbackQuery, state: FSMContext):
    """Handle exchange selection and show API setup instructions."""
    await callback.answer()

    exchange = callback.data.replace("exchange_", "").upper()

    instructions = {
        "BINANCE": """
<b>Binance API Setup</b>

1. Go to Binance.com → API Management
2. Create a new API key
3. Enable these permissions:
   ✅ Enable Spot Trading
   ✅ Enable Futures (optional)
   ❌ Enable Withdrawals - NEVER!
4. Add IP restriction: Your server IP
5. Copy API Key and Secret

Send me your API credentials in this format:
<code>api_key: your_api_key</code>
<code>secret: your_secret</code>
""",
        "OKX": """
<b>OKX API Setup</b>

1. Go to OKX.com → API
2. Create a new API key
3. Set permissions:
   ✅ Trade
   ❌ Withdraw - NEVER!
4. Add IP restriction
5. Set a passphrase
6. Copy API Key, Secret, and Passphrase

Send me your API credentials in this format:
<code>api_key: your_api_key</code>
<code>secret: your_secret</code>
<code>passphrase: your_passphrase</code>
""",
        "BYBIT": """
<b>Bybit API Setup</b>

1. Go to Bybit.com → API Management
2. Create a new API key
3. Set permissions:
   ✅ Read-Write (Trade)
   ❌ Withdrawals - NEVER!
4. Add IP restriction
5. Copy API Key and Secret

Send me your API credentials in this format:
<code>api_key: your_api_key</code>
<code>secret: your_secret</code>
""",
    }

    text = instructions.get(exchange, "Unknown exchange")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back", callback_data="onboarding_start")],
        [InlineKeyboardButton(text="⏭️ Skip for Now", callback_data="skip_api_setup")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.update_data(selected_exchange=exchange)


@router.callback_query(F.data == "skip_api_setup")
async def skip_api_setup(callback: CallbackQuery, state: FSMContext):
    """Skip API setup for now."""
    await callback.answer()
    await state.clear()

    text = """
<b>Setup Complete!</b> 🎉

You can connect your exchange API later in Settings.

For now, you can:
• Browse available whales
• View whale statistics
• Learn about copy trading

When you're ready to trade, go to ⚙️ Settings → API Keys.

Use the menu below to explore!
"""
    await callback.message.edit_text(text)
    await callback.message.answer(
        "What would you like to do?",
        reply_markup=get_main_menu_keyboard(),
    )


# Main menu button handlers
@router.message(F.text == "📊 Dashboard")
async def show_dashboard(message: Message, user: User, db: AsyncSession):
    """Show user dashboard."""
    from sqlalchemy import func, select
    from app.models.trade import Position, PositionStatus

    # Get stats
    positions_result = await db.execute(
        select(
            func.count(Position.id).label("count"),
            func.sum(Position.unrealized_pnl).label("pnl"),
        ).where(
            Position.user_id == user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    stats = positions_result.first()

    open_positions = stats.count or 0
    unrealized_pnl = stats.pnl or 0

    text = f"""
<b>📊 Your Dashboard</b>

<b>Balance:</b> ${user.total_balance:,.2f}
<b>Available:</b> ${user.available_balance:,.2f}

<b>Open Positions:</b> {open_positions}
<b>Unrealized P&L:</b> ${unrealized_pnl:,.2f}

<b>Subscription:</b> {user.subscription_tier.value}
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Open Mini App", web_app={"url": "https://your-webapp.com"})],
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_dashboard")],
    ])

    await message.answer(text, reply_markup=keyboard)
