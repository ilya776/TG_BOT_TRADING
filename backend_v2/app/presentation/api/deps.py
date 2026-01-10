"""API Dependencies.

FastAPI dependency injection for authentication, database sessions, etc.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth import get_jwt_manager
from app.infrastructure.persistence.sqlalchemy.models import User
from app.presentation.api.dependencies import get_db_session


async def get_db() -> AsyncSession:
    """Get database session.

    Yields an async session from the session factory.
    """
    async for session in get_db_session():
        yield session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from the JWT token.

    Args:
        authorization: Authorization header with Bearer token.
        db: Database session.

    Returns:
        Authenticated user.

    Raises:
        HTTPException: If authentication fails.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from Bearer scheme
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    jwt_manager = get_jwt_manager()
    payload = jwt_manager.verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user from database
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

    return user


async def get_current_user_optional(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optionally get the current authenticated user.

    Returns None if no valid authentication is provided.
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None


def require_subscription_tier(required_tier: str):
    """Dependency factory to require a minimum subscription tier.

    Args:
        required_tier: Minimum tier required ("FREE", "PRO", "ELITE").
    """
    tier_levels = {"FREE": 0, "PRO": 1, "ELITE": 2}

    async def check_tier(current_user: User = Depends(get_current_user)) -> User:
        user_tier_level = tier_levels.get(current_user.subscription_tier.value, 0)
        required_level = tier_levels.get(required_tier, 0)

        if user_tier_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {required_tier} subscription or higher",
            )

        return current_user

    return check_tier


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
ProUser = Annotated[User, Depends(require_subscription_tier("PRO"))]
EliteUser = Annotated[User, Depends(require_subscription_tier("ELITE"))]
