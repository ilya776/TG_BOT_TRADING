"""
Notification-related Celery tasks
"""
import json
import logging
import os
from datetime import datetime

import httpx
from sqlalchemy import select

from app.database import get_sync_db
from app.models.user import User
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Telegram Bot API
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_telegram_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    """
    Send a message via Telegram Bot API (synchronous for Celery).

    Args:
        chat_id: Telegram chat ID (same as user's telegram_id)
        text: Message text (HTML formatted)
        parse_mode: Parse mode (HTML or Markdown)
        reply_markup: Optional inline keyboard

    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
        return False

    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{TELEGRAM_API_URL}/sendMessage", data=payload)

            if response.status_code == 200:
                return True

            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def format_whale_alert(signal_data: dict) -> tuple[str, dict]:
    """Format whale alert message with inline keyboard."""
    action = signal_data.get("action", "BUY")
    symbol = signal_data.get("symbol", "UNKNOWN")
    whale_name = signal_data.get("whale_name", "Unknown Whale")
    amount_usd = signal_data.get("amount_usd", 0)
    confidence = signal_data.get("confidence", "MEDIUM")
    signal_id = signal_data.get("signal_id", 0)

    action_emoji = "🟢" if action == "BUY" else "🔴"
    confidence_emoji = {"VERY_HIGH": "🔥", "HIGH": "⚡", "MEDIUM": "📊", "LOW": "📉"}.get(
        confidence, "📊"
    )

    message = f"""
{action_emoji} <b>Whale Alert!</b>

🐋 <b>{whale_name}</b>
📈 Action: <b>{action}</b> {symbol}
💰 Size: <b>${amount_usd:,.0f}</b>
{confidence_emoji} Confidence: <b>{confidence}</b>

⏰ {datetime.utcnow().strftime("%H:%M:%S UTC")}
"""

    # Inline keyboard with Copy and Skip buttons
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Copy Trade", "callback_data": f"copy_{signal_id}"},
                {"text": "❌ Skip", "callback_data": f"skip_{signal_id}"},
            ],
            [
                {"text": "📊 View Details", "callback_data": f"details_{signal_id}"},
            ],
        ]
    }

    return message.strip(), keyboard


def format_trade_notification(trade_data: dict) -> str:
    """Format trade execution notification."""
    symbol = trade_data.get("symbol", "UNKNOWN")
    side = trade_data.get("side", "BUY")
    quantity = trade_data.get("quantity", 0)
    price = trade_data.get("price", 0)
    value_usdt = trade_data.get("value_usdt", 0)
    status = trade_data.get("status", "FILLED")
    whale_name = trade_data.get("whale_name", "")

    side_emoji = "🟢" if side == "BUY" else "🔴"
    status_emoji = "✅" if status == "FILLED" else "⚠️"

    message = f"""
{status_emoji} <b>Trade Executed!</b>

{side_emoji} {side} <b>{symbol}</b>
📊 Quantity: {quantity:.6f}
💵 Price: ${price:,.4f}
💰 Value: ${value_usdt:,.2f}

{f"🐋 Copied from: {whale_name}" if whale_name else ""}
⏰ {datetime.utcnow().strftime("%H:%M:%S UTC")}
"""

    return message.strip()


@celery_app.task(bind=True, max_retries=3)
def send_whale_alert(self, user_ids: list[int], signal_data: dict):
    """
    Send whale alert notifications to users.

    Args:
        user_ids: List of database user IDs to notify
        signal_data: Whale signal information
    """
    logger.info(f"Sending whale alert to {len(user_ids)} users")

    if not user_ids:
        return {"status": "skipped", "reason": "no users"}

    # Format the message
    message, keyboard = format_whale_alert(signal_data)

    sent_count = 0
    failed_count = 0

    with get_sync_db() as db:
        # Get telegram_ids for all users
        result = db.execute(
            select(User.id, User.telegram_id).where(
                User.id.in_(user_ids),
                User.is_active == True,
                User.telegram_id.isnot(None),
            )
        )
        users = result.all()

        for user_id, telegram_id in users:
            try:
                success = send_telegram_message(
                    chat_id=telegram_id,
                    text=message,
                    reply_markup=keyboard,
                )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Failed to send alert to user {user_id}: {e}")
                failed_count += 1

        db.commit()

    logger.info(f"Whale alert sent: {sent_count} success, {failed_count} failed")
    return {"status": "completed", "sent": sent_count, "failed": failed_count}


@celery_app.task(bind=True, max_retries=3)
def send_trade_notification(self, user_id: int, trade_data: dict):
    """Send trade execution notification to user."""
    logger.info(f"Sending trade notification to user {user_id}")

    with get_sync_db() as db:
        # Get user's telegram_id
        result = db.execute(
            select(User.telegram_id).where(
                User.id == user_id,
                User.is_active == True,
                User.telegram_id.isnot(None),
            )
        )
        row = result.first()

        if not row:
            logger.warning(f"User {user_id} not found or no telegram_id")
            return {"status": "skipped", "reason": "user not found"}

        telegram_id = row[0]

        # Format and send message
        message = format_trade_notification(trade_data)
        success = send_telegram_message(chat_id=telegram_id, text=message)

        if success:
            return {"status": "sent"}
        else:
            return {"status": "failed"}


@celery_app.task
def send_position_alert(user_id: int, alert_type: str, position_data: dict):
    """
    Send position alert (stop-loss hit, take-profit hit, liquidation warning).

    Args:
        user_id: User database ID
        alert_type: Type of alert (stop_loss, take_profit, liquidation_warning)
        position_data: Position information
    """
    logger.info(f"Sending {alert_type} alert to user {user_id}")

    alert_configs = {
        "stop_loss": ("🛑", "Stop-Loss Triggered"),
        "take_profit": ("🎯", "Take-Profit Reached"),
        "liquidation_warning": ("⚠️", "Liquidation Warning"),
        "whale_exit": ("🐋", "Whale Exited Position"),
        "manual_close": ("✋", "Position Closed"),
    }

    emoji, title = alert_configs.get(alert_type, ("ℹ️", "Position Alert"))

    symbol = position_data.get("symbol", "UNKNOWN")
    pnl = position_data.get("pnl", 0)
    pnl_percent = position_data.get("pnl_percent", 0)
    exit_price = position_data.get("exit_price", 0)

    pnl_emoji = "🟢" if pnl >= 0 else "🔴"

    message = f"""
{emoji} <b>{title}</b>

📊 Symbol: <b>{symbol}</b>
💵 Exit Price: ${exit_price:,.4f}
{pnl_emoji} P&L: ${pnl:,.2f} ({pnl_percent:+.2f}%)

⏰ {datetime.utcnow().strftime("%H:%M:%S UTC")}
"""

    with get_sync_db() as db:
        result = db.execute(
            select(User.telegram_id).where(
                User.id == user_id,
                User.is_active == True,
                User.telegram_id.isnot(None),
            )
        )
        row = result.first()

        if row:
            send_telegram_message(chat_id=row[0], text=message.strip())

    return {"status": "sent"}


@celery_app.task
def cleanup_old_notifications():
    """
    Clean up old notifications.
    Note: Currently a no-op since we don't persist notifications to DB.
    This can be implemented when a Notification model is added.
    """
    logger.info("Cleanup task executed (no-op - notifications not persisted)")
    return {"status": "completed", "deleted": 0}
