"""Authentication Routes.

Handles Telegram Mini App authentication and JWT token management.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy import select
from typing import Annotated

from app.config import get_settings
from app.infrastructure.auth import get_jwt_manager, verify_telegram_init_data
from app.infrastructure.persistence.sqlalchemy.models import User, UserSettings
from app.presentation.api.deps import DbSession, get_db

logger = structlog.get_logger()
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# SCHEMAS
# ============================================================================


class TelegramAuthRequest(BaseModel):
    """Request body for Telegram authentication."""
    init_data: str


class TelegramDesktopAuthRequest(BaseModel):
    """Request body for Telegram Desktop fallback authentication."""
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str = "en"
    platform: str = "unknown"


class AuthResponse(BaseModel):
    """Response containing authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds
    user: dict


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""
    refresh_token: str


# ============================================================================
# HELPERS
# ============================================================================


async def get_or_create_user(
    db: DbSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str = "en",
) -> User:
    """Get existing user or create new one.

    Args:
        db: Database session.
        telegram_id: Telegram user ID.
        username: Telegram username.
        first_name: User's first name.
        last_name: User's last name.
        language_code: User's language code.

    Returns:
        User instance.
    """
    # Try to find existing user
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        user.last_active_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        return user

    # Create new user
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        last_active_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()

    # Create default settings
    user_settings = UserSettings(user_id=user.id)
    db.add(user_settings)

    await db.commit()
    await db.refresh(user)

    logger.info("user.created", user_id=user.id, telegram_id=telegram_id)
    return user


# ============================================================================
# ROUTES
# ============================================================================


@router.post("/telegram", response_model=AuthResponse)
async def authenticate_telegram(
    request: TelegramAuthRequest,
    db: DbSession,
):
    """Authenticate using Telegram Mini App init data.

    This endpoint verifies the Telegram init data and returns JWT tokens.
    """
    # Verify init data
    user_data = verify_telegram_init_data(
        request.init_data,
        settings.telegram_bot_token
    )

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Telegram authentication data",
        )

    telegram_id = user_data.get("id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram user ID",
        )

    # Get or create user
    user = await get_or_create_user(
        db=db,
        telegram_id=telegram_id,
        username=user_data.get("username"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        language_code=user_data.get("language_code", "en"),
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is banned: {user.ban_reason or 'No reason provided'}",
        )

    # Generate tokens
    jwt_manager = get_jwt_manager()
    access_token = jwt_manager.create_access_token({"user_id": user.id})
    refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    logger.info("auth.telegram.success", user_id=user.id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "subscription_tier": user.subscription_tier.value,
        }
    )


@router.post("/telegram/desktop", response_model=AuthResponse)
async def authenticate_telegram_desktop(
    request: TelegramDesktopAuthRequest,
    db: DbSession,
):
    """Fallback authentication for Telegram Desktop where initData is empty.

    SECURITY: This endpoint only allows authentication for EXISTING users.
    New user creation is disabled to prevent account enumeration attacks.
    """
    # Check if desktop auth is disabled
    if settings.disable_desktop_auth:
        logger.warning(
            "auth.desktop.blocked",
            telegram_id=request.telegram_id,
            platform=request.platform,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Desktop authentication is disabled. Please use Telegram mobile app.",
        )

    logger.warning(
        "auth.desktop.attempt",
        telegram_id=request.telegram_id,
        platform=request.platform,
    )

    if not request.telegram_id or request.telegram_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram user ID",
        )

    # SECURITY: Only allow existing users to authenticate via desktop
    result = await db.execute(
        select(User).where(User.telegram_id == request.telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(
            "auth.desktop.user_not_found",
            telegram_id=request.telegram_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please authenticate via Telegram mobile app first.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is banned: {user.ban_reason or 'No reason provided'}",
        )

    # Update user info if provided
    if request.username:
        user.username = request.username
    if request.first_name:
        user.first_name = request.first_name
    if request.last_name:
        user.last_name = request.last_name
    user.language_code = request.language_code
    user.last_active_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    jwt_manager = get_jwt_manager()
    access_token = jwt_manager.create_access_token({"user_id": user.id})
    refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    logger.info(
        "auth.desktop.success",
        user_id=user.id,
        platform=request.platform,
    )

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "subscription_tier": user.subscription_tier.value,
        }
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(
    request: RefreshTokenRequest,
    db: DbSession,
):
    """Refresh access token using refresh token."""
    jwt_manager = get_jwt_manager()
    payload = jwt_manager.verify_refresh_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is banned: {user.ban_reason or 'No reason provided'}",
        )

    # Generate new tokens
    access_token = jwt_manager.create_access_token({"user_id": user.id})
    refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    # Update last active
    user.last_active_at = datetime.utcnow()
    await db.commit()

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "subscription_tier": user.subscription_tier.value,
        }
    )


@router.get("/me")
async def get_current_user_info(
    authorization: Annotated[str | None, Header()] = None,
    db: DbSession = None,
):
    """Get current user info from token.

    Returns null if not authenticated (does not throw error).
    """
    if not authorization:
        return {"authenticated": False, "user": None}

    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return {"authenticated": False, "user": None}

        token = parts[1]
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.verify_access_token(token)

        if not payload:
            return {"authenticated": False, "user": None}

        user_id = payload.get("user_id")
        if not user_id:
            return {"authenticated": False, "user": None}

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active or user.is_banned:
            return {"authenticated": False, "user": None}

        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "subscription_tier": user.subscription_tier.value,
            }
        }
    except Exception:
        return {"authenticated": False, "user": None}
