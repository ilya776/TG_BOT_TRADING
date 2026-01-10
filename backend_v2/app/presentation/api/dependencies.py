"""Dependency injection for FastAPI.

Provides dependencies для API routes:
- Database session/Unit of Work
- Handlers (ExecuteCopyTradeHandler, ClosePositionHandler)
- Exchange factory
- Event bus
- User authentication
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.trading.handlers import (
    ClosePositionHandler,
    ExecuteCopyTradeHandler,
)
from app.infrastructure.exchanges.factories import ExchangeFactory
from app.infrastructure.messaging import get_event_bus
from app.infrastructure.persistence.sqlalchemy import (
    SQLAlchemyUnitOfWork,
    create_unit_of_work,
)

# ============================================================================
# GLOBAL DEPENDENCIES (будуть initialized в main.py)
# ============================================================================

# Database session factory (буде встановлено при startup)
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Exchange factory (singleton)
_exchange_factory: ExchangeFactory | None = None


def init_dependencies(
    session_factory: async_sessionmaker[AsyncSession],
    exchange_factory: ExchangeFactory,
) -> None:
    """Initialize global dependencies.

    Args:
        session_factory: SQLAlchemy async session factory.
        exchange_factory: Exchange factory instance.

    Note:
        Викликається при FastAPI startup (в main.py).
    """
    global _session_factory, _exchange_factory
    _session_factory = session_factory
    _exchange_factory = exchange_factory


# ============================================================================
# AUTHENTICATION
# ============================================================================


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> int:
    """Get current user ID from Authorization header.

    Args:
        authorization: Authorization header (Bearer token).

    Returns:
        User ID.

    Raises:
        HTTPException: 401 if unauthorized.

    Note:
        TODO: Implement real authentication (JWT, API key, etc.)
        Зараз просто mock для тестування.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Mock authentication: витягуємо user_id з header
    # TODO: Replace with real JWT/token validation
    try:
        # Формат: "Bearer user_id=123"
        if not authorization.startswith("Bearer "):
            raise ValueError("Invalid authorization format")

        token = authorization.replace("Bearer ", "")
        if "user_id=" not in token:
            raise ValueError("Missing user_id")

        user_id_str = token.split("user_id=")[1]
        user_id = int(user_id_str)

        if user_id <= 0:
            raise ValueError("Invalid user_id")

        return user_id

    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authorization token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# UNIT OF WORK
# ============================================================================


async def get_unit_of_work() -> SQLAlchemyUnitOfWork:
    """Get Unit of Work instance.

    Returns:
        SQLAlchemyUnitOfWork instance.

    Raises:
        RuntimeError: If dependencies not initialized.

    Note:
        Unit of Work створюється для кожного request.
        Використовується як dependency в handlers.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Dependencies not initialized. Call init_dependencies() first."
        )

    return create_unit_of_work(_session_factory)


# ============================================================================
# EXCHANGE FACTORY
# ============================================================================


async def get_exchange_factory() -> ExchangeFactory:
    """Get Exchange Factory instance.

    Returns:
        ExchangeFactory singleton.

    Raises:
        RuntimeError: If dependencies not initialized.
    """
    if _exchange_factory is None:
        raise RuntimeError(
            "Dependencies not initialized. Call init_dependencies() first."
        )

    return _exchange_factory


# ============================================================================
# HANDLERS
# ============================================================================


async def get_execute_copy_trade_handler(
    uow: Annotated[SQLAlchemyUnitOfWork, Depends(get_unit_of_work)],
    exchange_factory: Annotated[ExchangeFactory, Depends(get_exchange_factory)],
) -> ExecuteCopyTradeHandler:
    """Get ExecuteCopyTradeHandler instance.

    Args:
        uow: Unit of Work (injected).
        exchange_factory: Exchange factory (injected).

    Returns:
        ExecuteCopyTradeHandler instance.

    Note:
        Handler створюється для кожного request з injected dependencies.
    """
    event_bus = get_event_bus()
    return ExecuteCopyTradeHandler(
        uow=uow, exchange_factory=exchange_factory, event_bus=event_bus
    )


async def get_close_position_handler(
    uow: Annotated[SQLAlchemyUnitOfWork, Depends(get_unit_of_work)],
    exchange_factory: Annotated[ExchangeFactory, Depends(get_exchange_factory)],
) -> ClosePositionHandler:
    """Get ClosePositionHandler instance.

    Args:
        uow: Unit of Work (injected).
        exchange_factory: Exchange factory (injected).

    Returns:
        ClosePositionHandler instance.

    Note:
        Handler створюється для кожного request з injected dependencies.
    """
    event_bus = get_event_bus()
    return ClosePositionHandler(
        uow=uow, exchange_factory=exchange_factory, event_bus=event_bus
    )


# ============================================================================
# TYPE ALIASES (для cleaner route signatures)
# ============================================================================

# User authentication
CurrentUserId = Annotated[int, Depends(get_current_user_id)]

# Handlers
ExecuteCopyTradeHandlerDep = Annotated[
    ExecuteCopyTradeHandler, Depends(get_execute_copy_trade_handler)
]
ClosePositionHandlerDep = Annotated[
    ClosePositionHandler, Depends(get_close_position_handler)
]
