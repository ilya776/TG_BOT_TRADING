"""Application Configuration.

Uses pydantic-settings for type-safe configuration from environment variables.
Supports multiple environments: development, staging, production.

Usage:
    from app.config import get_settings, setup_logging, get_logger
    settings = get_settings()
    setup_logging()  # Call once at startup
    logger = get_logger(__name__)
"""

from .settings import Settings, get_settings
from .logging import setup_logging, get_logger, bind_request_context, clear_request_context

__all__ = [
    "Settings",
    "get_settings",
    "setup_logging",
    "get_logger",
    "bind_request_context",
    "clear_request_context",
]
