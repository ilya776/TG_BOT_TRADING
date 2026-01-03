"""
Whale Management Handlers
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.whale import Whale, WhaleStats, UserWhaleFollow
from app.telegram.keyboards import get_whale_action_keyboard, get_pagination_keyboard

router = Router()

WHALES_PER_PAGE = 5


@router.message(F.text == "🐋 Whales")
@router.message(Command("whales"))
async def show_whales(message: Message, user: User, db: AsyncSession):
    """Show whale list."""
    await send_whale_list(message, user, db, page=1)


@router.callback_query(F.data == "whales_list")
async def callback_whales_list(callback: CallbackQuery, user: User, db: AsyncSession):
    """Return to whale list."""
    await callback.answer()
    await send_whale_list(callback.message, user, db, page=1, edit=True)


@router.callback_query(F.data.startswith("whales_page_"))
async def callback_whales_page(callback: CallbackQuery, user: User, db: AsyncSession):
    """Handle whale list pagination."""
    await callback.answer()
    page = int(callback.data.replace("whales_page_", ""))
    await send_whale_list(callback.message, user, db, page=page, edit=True)


async def send_whale_list(
    message: Message,
    user: User,
    db: AsyncSession,
    page: int = 1,
    edit: bool = False,
):
    """Send paginated whale list."""
    # Get total count
    count_result = await db.execute(
        select(func.count(Whale.id)).where(Whale.is_active == True, Whale.is_public == True)
    )
    total_count = count_result.scalar() or 0
    total_pages = (total_count + WHALES_PER_PAGE - 1) // WHALES_PER_PAGE

    # Get whales for this page
    offset = (page - 1) * WHALES_PER_PAGE
    result = await db.execute(
        select(Whale, WhaleStats)
        .outerjoin(WhaleStats, Whale.id == WhaleStats.whale_id)
        .where(Whale.is_active == True, Whale.is_public == True)
        .order_by(Whale.score.desc())
        .offset(offset)
        .limit(WHALES_PER_PAGE)
    )
    whales = result.all()

    # Get user's followed whale IDs
    follows_result = await db.execute(
        select(UserWhaleFollow.whale_id).where(UserWhaleFollow.user_id == user.id)
    )
    followed_ids = {row[0] for row in follows_result.all()}

    if not whales:
        text = "No whales available yet. Check back later!"
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    text = "<b>🐋 Top Whales</b>\n\n"

    for whale, stats in whales:
        is_following = whale.id in followed_ids
        follow_icon = "✅" if is_following else ""

        win_rate = stats.win_rate if stats else 0
        profit_7d = stats.profit_7d if stats else 0

        text += f"{follow_icon} <b>{whale.name}</b>\n"
        text += f"├ Rank: {whale.rank.value} | Score: {whale.score:.1f}\n"
        text += f"├ Win Rate: {win_rate:.1f}% | 7d P&L: ${profit_7d:,.0f}\n"
        text += f"└ /whale_{whale.id}\n\n"

    text += f"\n<i>Page {page}/{total_pages}</i>"

    # Build keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = []

    # Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"whales_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"whales_page_{page + 1}"))
    buttons.append(nav_row)

    # Filter buttons
    buttons.append([
        InlineKeyboardButton(text="🔝 Top Win Rate", callback_data="whales_sort_winrate"),
        InlineKeyboardButton(text="💰 Top Profit", callback_data="whales_sort_profit"),
    ])

    buttons.append([
        InlineKeyboardButton(text="📊 My Following", callback_data="whales_my_following"),
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.message(F.text.regexp(r"^/whale_(\d+)$"))
async def show_whale_detail(message: Message, user: User, db: AsyncSession):
    """Show whale details."""
    import re
    match = re.match(r"^/whale_(\d+)$", message.text)
    if not match:
        return

    whale_id = int(match.group(1))
    await send_whale_detail(message, user, db, whale_id)


@router.callback_query(F.data.startswith("whale_view_"))
async def callback_whale_detail(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show whale detail from callback."""
    await callback.answer()
    whale_id = int(callback.data.replace("whale_view_", ""))
    await send_whale_detail(callback.message, user, db, whale_id, edit=True)


async def send_whale_detail(
    message: Message,
    user: User,
    db: AsyncSession,
    whale_id: int,
    edit: bool = False,
):
    """Send whale details."""
    # Get whale with stats
    result = await db.execute(
        select(Whale, WhaleStats)
        .outerjoin(WhaleStats, Whale.id == WhaleStats.whale_id)
        .where(Whale.id == whale_id)
    )
    row = result.first()

    if not row:
        text = "Whale not found."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    whale, stats = row

    # Check if following
    follow_result = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == user.id,
            UserWhaleFollow.whale_id == whale_id,
        )
    )
    follow = follow_result.scalar_one_or_none()
    is_following = follow is not None

    text = f"""
<b>🐋 {whale.name}</b>
{'✅ Following' if is_following else ''}

<b>Address:</b> <code>{whale.wallet_address[:10]}...{whale.wallet_address[-8:]}</code>
<b>Chain:</b> {whale.chain.value}
<b>Rank:</b> {whale.rank.value}
<b>Score:</b> {whale.score:.2f}
"""

    if stats:
        text += f"""
<b>📊 Performance</b>
├ Total Trades: {stats.total_trades}
├ Win Rate: {stats.win_rate:.1f}%
├ Avg Profit: {stats.avg_profit_percent:.1f}%
├ Max Drawdown: {stats.max_drawdown_percent:.1f}%
└ Trades/Week: {stats.trades_per_week:.1f}

<b>💰 Profit</b>
├ 7 Days: ${stats.profit_7d:,.0f}
├ 30 Days: ${stats.profit_30d:,.0f}
└ 90 Days: ${stats.profit_90d:,.0f}
"""

    if is_following and follow:
        text += f"""
<b>⚙️ Your Settings</b>
├ Auto-Copy: {'✅ ON' if follow.auto_copy_enabled else '❌ OFF'}
├ Trade Size: ${follow.trade_size_usdt or 'Default'}
└ Trades Copied: {follow.trades_copied}
"""

    if whale.description:
        text += f"\n<b>📝 Description:</b>\n{whale.description}"

    keyboard = get_whale_action_keyboard(whale_id, is_following)

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("whale_follow_"))
async def follow_whale(callback: CallbackQuery, user: User, db: AsyncSession):
    """Follow a whale."""
    await callback.answer()

    whale_id = int(callback.data.replace("whale_follow_", ""))

    # Check whale limit
    from app.config import SUBSCRIPTION_TIERS
    tier_config = SUBSCRIPTION_TIERS.get(user.subscription_tier.value, {})
    whale_limit = tier_config.get("whales_limit", 1)

    if whale_limit > 0:
        count_result = await db.execute(
            select(func.count(UserWhaleFollow.id)).where(
                UserWhaleFollow.user_id == user.id
            )
        )
        current_count = count_result.scalar() or 0

        if current_count >= whale_limit:
            await callback.message.edit_text(
                f"❌ You've reached your whale limit ({whale_limit}).\n\n"
                f"Upgrade to PRO or ELITE for more whales!",
            )
            return

    # Create follow
    follow = UserWhaleFollow(
        user_id=user.id,
        whale_id=whale_id,
        auto_copy_enabled=False,
    )
    db.add(follow)
    await db.commit()

    await callback.answer("✅ Whale followed!", show_alert=True)
    await send_whale_detail(callback.message, user, db, whale_id, edit=True)


@router.callback_query(F.data.startswith("whale_unfollow_"))
async def unfollow_whale(callback: CallbackQuery, user: User, db: AsyncSession):
    """Unfollow a whale."""
    whale_id = int(callback.data.replace("whale_unfollow_", ""))

    result = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == user.id,
            UserWhaleFollow.whale_id == whale_id,
        )
    )
    follow = result.scalar_one_or_none()

    if follow:
        await db.delete(follow)
        await db.commit()
        await callback.answer("Unfollowed", show_alert=True)
    else:
        await callback.answer("Not following this whale")

    await send_whale_detail(callback.message, user, db, whale_id, edit=True)


@router.callback_query(F.data.startswith("whale_toggle_auto_"))
async def toggle_auto_copy(callback: CallbackQuery, user: User, db: AsyncSession):
    """Toggle auto-copy for a whale."""
    whale_id = int(callback.data.replace("whale_toggle_auto_", ""))

    result = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == user.id,
            UserWhaleFollow.whale_id == whale_id,
        )
    )
    follow = result.scalar_one_or_none()

    if not follow:
        await callback.answer("You're not following this whale")
        return

    # Check if auto-copy is allowed
    from app.config import SUBSCRIPTION_TIERS
    tier_config = SUBSCRIPTION_TIERS.get(user.subscription_tier.value, {})

    if not tier_config.get("auto_copy", False) and not follow.auto_copy_enabled:
        await callback.answer(
            "Auto-copy requires PRO subscription or higher!",
            show_alert=True,
        )
        return

    # Toggle
    follow.auto_copy_enabled = not follow.auto_copy_enabled
    await db.commit()

    status = "ON" if follow.auto_copy_enabled else "OFF"
    await callback.answer(f"Auto-copy: {status}", show_alert=True)
    await send_whale_detail(callback.message, user, db, whale_id, edit=True)


@router.callback_query(F.data == "whales_my_following")
async def show_my_following(callback: CallbackQuery, user: User, db: AsyncSession):
    """Show whales user is following."""
    await callback.answer()

    result = await db.execute(
        select(UserWhaleFollow, Whale)
        .join(Whale, UserWhaleFollow.whale_id == Whale.id)
        .where(UserWhaleFollow.user_id == user.id)
    )
    follows = result.all()

    if not follows:
        text = "You're not following any whales yet.\n\nBrowse whales and click Follow to start!"
    else:
        text = "<b>🐋 My Following</b>\n\n"
        for follow, whale in follows:
            auto_status = "🤖 Auto" if follow.auto_copy_enabled else "📝 Manual"
            text += f"• <b>{whale.name}</b> ({auto_status})\n"
            text += f"  Trades: {follow.trades_copied} | P&L: ${follow.total_profit:,.2f}\n"
            text += f"  /whale_{whale.id}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Whales", callback_data="whales_list")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
