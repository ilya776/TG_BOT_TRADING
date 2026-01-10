"""API v1 routes."""

from .auth import router as auth_router
from .balance import router as balance_router
from .signals import router as signals_router
from .trades import router as trades_router
from .trading import router as trading_router
from .users import router as users_router
from .whales import router as whales_router

__all__ = [
    "auth_router",
    "balance_router",
    "signals_router",
    "trades_router",
    "trading_router",
    "users_router",
    "whales_router",
]
