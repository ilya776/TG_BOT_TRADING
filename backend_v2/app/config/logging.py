"""Structured Logging Configuration.

Production-ready logging with:
- JSON format for production (easy parsing by log aggregators)
- Human-readable format for development
- Request correlation IDs
- Sensitive data filtering

Usage:
    from app.config.logging import setup_logging, get_logger

    setup_logging()  # Call once at startup
    logger = get_logger(__name__)
    logger.info("message", extra={"user_id": 123})
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any

import structlog
from structlog.typing import EventDict

from app.config import get_settings

settings = get_settings()


# ============================================================================
# SENSITIVE DATA FILTER
# ============================================================================


SENSITIVE_KEYS = frozenset({
    "password",
    "secret",
    "api_key",
    "api_secret",
    "token",
    "authorization",
    "private_key",
    "passphrase",
})


def filter_sensitive_data(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Filter sensitive data from log output.

    Replaces values of sensitive keys with '[REDACTED]'.

    Args:
        logger: The logger instance.
        method_name: The logging method name.
        event_dict: The event dictionary to filter.

    Returns:
        Filtered event dictionary.
    """
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], dict):
            event_dict[key] = _filter_dict(event_dict[key])
    return event_dict


def _filter_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively filter sensitive data from nested dicts."""
    result = {}
    for key, value in d.items():
        if key.lower() in SENSITIVE_KEYS:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _filter_dict(value)
        else:
            result[key] = value
    return result


# ============================================================================
# CUSTOM PROCESSORS
# ============================================================================


def add_timestamp(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add ISO format timestamp to log events."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_service_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add service context to log events."""
    event_dict["service"] = "trading-backend"
    event_dict["environment"] = settings.environment
    event_dict["version"] = "2.0.0"
    return event_dict


# ============================================================================
# LOGGING SETUP
# ============================================================================


def setup_logging() -> None:
    """Configure structured logging for the application.

    Call this once at application startup (in main.py lifespan).

    Configuration based on environment:
    - Development: Console output with colors
    - Production: JSON output for log aggregation
    """
    # Common processors for all environments
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_timestamp,
        add_service_context,
        filter_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_format == "json":
        # Production: JSON format
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        # Development: Human-readable with colors
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=shared_processors,
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.db_echo else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured structlog logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("user.created", user_id=123, email="user@example.com")
    """
    return structlog.get_logger(name)


# ============================================================================
# REQUEST CONTEXT (for correlation IDs)
# ============================================================================


def bind_request_context(
    request_id: str,
    user_id: int | None = None,
    **extra: Any,
) -> None:
    """Bind request context to all subsequent log calls.

    Call this at the start of request handling (middleware).

    Args:
        request_id: Unique request/correlation ID.
        user_id: Optional user ID if authenticated.
        **extra: Additional context to bind.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        user_id=user_id,
        **extra,
    )


def clear_request_context() -> None:
    """Clear request context (call at end of request)."""
    structlog.contextvars.clear_contextvars()
