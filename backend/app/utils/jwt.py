"""
JWT Token Management
"""

from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


class JWTManager:
    """Handles JWT token creation and verification."""

    def __init__(self, secret_key: str | None = None):
        """
        Initialize JWT manager.

        Args:
            secret_key: Secret key for signing tokens. If not provided,
                       uses the key from settings.
        """
        self.secret_key = secret_key or settings.secret_key

    def create_access_token(
        self,
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta
            if expires_delta
            else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)

    def create_refresh_token(
        self,
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        Create a JWT refresh token.

        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta
            if expires_delta
            else timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token to verify

        Returns:
            Decoded token data or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        """
        Verify an access token specifically.

        Args:
            token: JWT access token

        Returns:
            Decoded token data or None if invalid/wrong type
        """
        payload = self.verify_token(token)
        if payload and payload.get("type") == "access":
            return payload
        return None

    def verify_refresh_token(self, token: str) -> dict[str, Any] | None:
        """
        Verify a refresh token specifically.

        Args:
            token: JWT refresh token

        Returns:
            Decoded token data or None if invalid/wrong type
        """
        payload = self.verify_token(token)
        if payload and payload.get("type") == "refresh":
            return payload
        return None

    def create_telegram_auth_token(self, telegram_id: int, user_id: int) -> str:
        """
        Create a token for Telegram Mini App authentication.

        Args:
            telegram_id: Telegram user ID
            user_id: Internal user ID

        Returns:
            JWT token for Telegram auth
        """
        return self.create_access_token(
            {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "auth_type": "telegram",
            }
        )


# Singleton instance
_jwt_manager: JWTManager | None = None


def get_jwt_manager() -> JWTManager:
    """Get or create the JWT manager singleton."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager
