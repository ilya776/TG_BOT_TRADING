"""Telegram Mini App Authentication.

Verifies Telegram WebApp init data for secure authentication.
"""

import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime

import structlog

logger = structlog.get_logger()


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Verify Telegram Mini App init data.

    The init data is signed by Telegram and contains user information.
    This function verifies the signature and returns the user data if valid.

    Args:
        init_data: The init data string from Telegram WebApp.
        bot_token: The bot token to verify against.

    Returns:
        Parsed user data if valid, None otherwise.
    """
    try:
        # Parse the init data
        parsed = dict(urllib.parse.parse_qsl(init_data))

        if "hash" not in parsed:
            logger.warning("telegram_auth.no_hash")
            return None

        received_hash = parsed.pop("hash")

        # Create data check string (sorted alphabetically)
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        # Create secret key using HMAC-SHA256
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Calculate expected hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if calculated_hash != received_hash:
            logger.warning("telegram_auth.invalid_hash")
            return None

        # Check auth_date (not older than 24 hours)
        auth_date = int(parsed.get("auth_date", 0))
        if datetime.utcnow().timestamp() - auth_date > 86400:
            logger.warning("telegram_auth.expired")
            return None

        # Parse and return user data
        user_data = json.loads(parsed.get("user", "{}"))
        return user_data

    except Exception as e:
        logger.error("telegram_auth.failed", error=str(e))
        return None
