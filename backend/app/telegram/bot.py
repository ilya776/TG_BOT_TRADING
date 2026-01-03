"""
Telegram Bot Initialization
"""

import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.config import get_settings
from app.telegram.handlers import start, settings, whales, trades, callbacks
from app.telegram.middleware import DatabaseMiddleware, UserMiddleware

logger = logging.getLogger(__name__)
settings_config = get_settings()

# Initialize bot
bot = Bot(
    token=settings_config.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# Initialize Redis storage for FSM
redis_storage = RedisStorage(Redis.from_url(settings_config.redis_url))

# Initialize dispatcher
dp = Dispatcher(storage=redis_storage)


def setup_handlers() -> None:
    """Register all handlers with the dispatcher."""
    # Register middleware
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(settings.router)
    dp.include_router(whales.router)
    dp.include_router(trades.router)
    dp.include_router(callbacks.router)

    logger.info("Telegram handlers registered")


async def start_bot() -> None:
    """Start the bot (webhook mode)."""
    setup_handlers()

    if settings_config.telegram_webhook_url:
        # Webhook mode
        await bot.set_webhook(
            url=f"{settings_config.telegram_webhook_url}/webhook/telegram",
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set to {settings_config.telegram_webhook_url}")
    else:
        # Polling mode (for development)
        logger.info("Starting bot in polling mode")
        await dp.start_polling(bot)


async def stop_bot() -> None:
    """Stop the bot and cleanup."""
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Bot stopped")
