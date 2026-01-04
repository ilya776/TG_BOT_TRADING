"""
General Callback Handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

router = Router()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Handle no-operation callbacks (like pagination indicators)."""
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery):
    """Cancel current action."""
    await callback.answer("Action cancelled")
    await callback.message.delete()


@router.callback_query(F.data == "refresh_dashboard")
async def refresh_dashboard(callback: CallbackQuery, user: User, db: AsyncSession):
    """Refresh dashboard."""
    await callback.answer("Refreshing...")
    # Re-render dashboard
    from app.telegram.handlers.start import show_dashboard
    await show_dashboard(callback.message, user, db)


@router.callback_query(F.data == "pause_auto")
async def pause_auto_copy(callback: CallbackQuery, user: User, db: AsyncSession):
    """Pause all auto-copy for user."""
    from sqlalchemy import update
    from app.models.whale import UserWhaleFollow

    await db.execute(
        update(UserWhaleFollow)
        .where(UserWhaleFollow.user_id == user.id)
        .values(auto_copy_enabled=False)
    )
    await db.commit()

    await callback.answer("All auto-copy paused!", show_alert=True)


@router.callback_query(F.data.startswith("copy_"))
async def copy_signal(callback: CallbackQuery, user: User, db: AsyncSession):
    """Copy a whale signal manually."""
    signal_id = int(callback.data.replace("copy_", ""))

    from sqlalchemy import select
    from app.models.signal import WhaleSignal, SignalStatus

    result = await db.execute(
        select(WhaleSignal).where(WhaleSignal.id == signal_id)
    )
    signal = result.scalar_one_or_none()

    if not signal:
        await callback.answer("Signal not found", show_alert=True)
        return

    if signal.status != SignalStatus.PENDING:
        await callback.answer("Signal already processed", show_alert=True)
        return

    # Process the signal for this user
    from app.services.copy_trade_engine import CopyTradeEngine
    from app.models.whale import UserWhaleFollow
    from app.models.user import UserSettings

    # Get follow and settings
    follow_result = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == user.id,
            UserWhaleFollow.whale_id == signal.whale_id,
        )
    )
    follow = follow_result.scalar_one_or_none()

    if not follow:
        await callback.answer("You're not following this whale", show_alert=True)
        return

    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = settings_result.scalar_one_or_none()

    engine = CopyTradeEngine(db)
    result = await engine._execute_copy_trade(
        signal=signal,
        follow=follow,
        user=user,
        settings=settings,
    )

    if result.success:
        await callback.answer(
            f"✅ Trade executed!\n{result.details.get('symbol')} {result.details.get('side')}",
            show_alert=True,
        )
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Copied!</b>",
        )
    else:
        await callback.answer(f"❌ Failed: {result.error}", show_alert=True)


@router.callback_query(F.data.startswith("skip_"))
async def skip_signal(callback: CallbackQuery):
    """Skip a whale signal."""
    await callback.answer("Signal skipped")
    await callback.message.edit_text(
        callback.message.text + "\n\n⏭️ <b>Skipped</b>",
    )


# Subscription-related callbacks
@router.callback_query(F.data.startswith("sub_"))
async def subscription_callback(callback: CallbackQuery, user: User, db: AsyncSession):
    """Handle subscription-related callbacks."""
    action = callback.data.replace("sub_", "")

    if action == "compare":
        text = """
<b>📋 Plan Comparison</b>

<b>🆓 FREE</b>
• 1 whale to follow
• Manual copy only
• 2% commission on profits
• Basic analytics

<b>⭐ PRO - $99/mo</b>
• 5 whales to follow
• Auto-copy enabled
• FUTURES trading
• 1% commission
• Advanced analytics
• Priority execution

<b>💎 ELITE - $299/mo</b>
• Unlimited whales
• Auto-copy enabled
• Flash copy (MEV protection)
• 0.5% commission
• AI whale scoring
• Custom strategies
• 24/7 VIP support
"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Get PRO", callback_data="sub_pro")],
            [InlineKeyboardButton(text="💎 Get ELITE", callback_data="sub_elite")],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_subscription")],
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)

    elif action in ["pro", "elite"]:
        tier = action.upper()
        price = 99 if action == "pro" else 299

        text = f"""
<b>Upgrade to {tier}</b>

Price: ${price}/month

<b>Payment Methods:</b>
• Telegram Stars
• USDT (TRC20/ERC20)

Select your payment method:
"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Pay with Telegram Stars", callback_data=f"pay_stars_{action}")],
            [InlineKeyboardButton(text="💵 Pay with USDT", callback_data=f"pay_usdt_{action}")],
            [InlineKeyboardButton(text="◀️ Back", callback_data="back_subscription")],
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)

    elif action == "free":
        await callback.answer("You're already on FREE plan")

    await callback.answer()


@router.callback_query(F.data == "back_subscription")
async def back_subscription(callback: CallbackQuery, user: User):
    """Return to subscription menu."""
    await callback.answer()

    text = f"""
<b>💳 Subscription</b>

Current Plan: <b>{user.subscription_tier.value}</b>

Upgrade your plan for more features:
"""
    from app.telegram.keyboards import get_subscription_keyboard
    await callback.message.edit_text(text, reply_markup=get_subscription_keyboard())


@router.message(F.text == "💳 Subscription")
async def show_subscription(message: Message, user: User):
    """Show subscription menu."""
    text = f"""
<b>💳 Subscription</b>

Current Plan: <b>{user.subscription_tier.value}</b>
{'Expires: ' + user.subscription_expires_at.strftime('%Y-%m-%d') if user.subscription_expires_at else ''}

Select a plan to upgrade:
"""
    from app.telegram.keyboards import get_subscription_keyboard
    await message.answer(text, reply_markup=get_subscription_keyboard())
