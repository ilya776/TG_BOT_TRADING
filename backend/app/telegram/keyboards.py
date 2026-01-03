"""
Telegram Keyboard Builders
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)

from app.config import get_settings

settings = get_settings()


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="🐋 Whales")],
            [KeyboardButton(text="💰 Portfolio"), KeyboardButton(text="📈 Trades")],
            [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="💳 Subscription")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for start command."""
    buttons = [
        [InlineKeyboardButton(text="🚀 Get Started", callback_data="onboarding_start")],
        [InlineKeyboardButton(text="📖 How It Works", callback_data="how_it_works")],
    ]

    if settings.telegram_webapp_url:
        buttons.append([
            InlineKeyboardButton(
                text="📱 Open Mini App",
                web_app=WebAppInfo(url=settings.telegram_webapp_url),
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_trading_mode_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting trading mode."""
    buttons = [
        [
            InlineKeyboardButton(text="📈 SPOT", callback_data="mode_spot"),
            InlineKeyboardButton(text="🚀 FUTURES", callback_data="mode_futures"),
        ],
        [InlineKeyboardButton(text="⚖️ MIXED (50/50)", callback_data="mode_mixed")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_exchange_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting exchange."""
    buttons = [
        [InlineKeyboardButton(text="🟡 Binance", callback_data="exchange_binance")],
        [InlineKeyboardButton(text="🟢 OKX", callback_data="exchange_okx")],
        [InlineKeyboardButton(text="🟠 Bybit", callback_data="exchange_bybit")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_whale_action_keyboard(whale_id: int, is_following: bool) -> InlineKeyboardMarkup:
    """Get keyboard for whale actions."""
    buttons = []

    if is_following:
        buttons.append([
            InlineKeyboardButton(
                text="⚙️ Edit Settings",
                callback_data=f"whale_edit_{whale_id}",
            ),
            InlineKeyboardButton(
                text="❌ Unfollow",
                callback_data=f"whale_unfollow_{whale_id}",
            ),
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🤖 Toggle Auto-Copy",
                callback_data=f"whale_toggle_auto_{whale_id}",
            ),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="✅ Follow",
                callback_data=f"whale_follow_{whale_id}",
            ),
        ])

    buttons.append([
        InlineKeyboardButton(text="📊 View Stats", callback_data=f"whale_stats_{whale_id}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Back to Whales", callback_data="whales_list"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_signal_keyboard(signal_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for whale signal notification."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Copy Now", callback_data=f"copy_{signal_id}"),
            InlineKeyboardButton(text="❌ Skip", callback_data=f"skip_{signal_id}"),
        ],
        [InlineKeyboardButton(text="⏸️ Pause Auto-Copy", callback_data="pause_auto")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_position_keyboard(position_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for position actions."""
    buttons = [
        [
            InlineKeyboardButton(text="🔒 Close Position", callback_data=f"close_pos_{position_id}"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Set Stop-Loss", callback_data=f"sl_{position_id}"),
            InlineKeyboardButton(text="🎯 Set Take-Profit", callback_data=f"tp_{position_id}"),
        ],
        [InlineKeyboardButton(text="◀️ Back", callback_data="positions_list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for settings menu."""
    buttons = [
        [InlineKeyboardButton(text="📈 Trading Mode", callback_data="settings_mode")],
        [InlineKeyboardButton(text="💱 Exchange", callback_data="settings_exchange")],
        [InlineKeyboardButton(text="🔗 API Keys", callback_data="settings_api_keys")],
        [InlineKeyboardButton(text="💰 Trade Size", callback_data="settings_trade_size")],
        [InlineKeyboardButton(text="🛡️ Risk Settings", callback_data="settings_risk")],
        [InlineKeyboardButton(text="🔔 Notifications", callback_data="settings_notifications")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for subscription options."""
    buttons = [
        [InlineKeyboardButton(text="🆓 Free", callback_data="sub_free")],
        [InlineKeyboardButton(text="⭐ PRO - $99/mo", callback_data="sub_pro")],
        [InlineKeyboardButton(text="💎 ELITE - $299/mo", callback_data="sub_elite")],
        [InlineKeyboardButton(text="📋 Compare Plans", callback_data="sub_compare")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_{action}_{target_id}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    """Get pagination keyboard."""
    buttons = []

    nav_row = []
    if current_page > 1:
        nav_row.append(
            InlineKeyboardButton(text="◀️", callback_data=f"{callback_prefix}_{current_page - 1}")
        )

    nav_row.append(
        InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop")
    )

    if current_page < total_pages:
        nav_row.append(
            InlineKeyboardButton(text="▶️", callback_data=f"{callback_prefix}_{current_page + 1}")
        )

    if nav_row:
        buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
