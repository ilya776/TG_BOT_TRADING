"""Exponential backoff retry logic for exchange API calls.

Критично для надійності:
- Exchange APIs можуть тимчасово недоступні (rate limits, network issues)
- Без retry trade може fail через transient error
- Exponential backoff prevents overwhelming the exchange
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryableError(Exception):
    """Base exception для errors які можна retry.

    Example:
        >>> raise RetryableError("Rate limit exceeded, retry in 1s")
    """

    pass


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (RetryableError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator для retry з exponential backoff.

    Args:
        max_retries: Максимальна кількість спроб (default: 3).
        base_delay: Базова затримка в секундах (default: 1.0).
        max_delay: Максимальна затримка в секундах (default: 60.0).
        exponential_base: База для exponential backoff (default: 2.0).
        retryable_exceptions: Tuple exceptions які можна retry.

    Returns:
        Decorated function з retry logic.

    Example:
        >>> @retry_with_backoff(max_retries=3, base_delay=1.0)
        ... async def call_exchange_api():
        ...     # API call that might fail with rate limit
        ...     return await exchange.get_balance()
        
        >>> # Перша спроба fails → wait 1s
        >>> # Друга спроба fails → wait 2s (exponential)
        >>> # Третя спроба fails → wait 4s
        >>> # Четверта спроба fails → raise exception
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(
                            f"retry.success",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "total_attempts": max_retries + 1,
                            },
                        )
                    return result

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        # Calculate delay з exponential backoff
                        delay = min(base_delay * (exponential_base**attempt), max_delay)

                        logger.warning(
                            f"retry.attempt",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "delay_seconds": delay,
                                "error": str(e),
                            },
                        )

                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"retry.exhausted",
                            extra={
                                "function": func.__name__,
                                "total_attempts": max_retries + 1,
                                "error": str(e),
                            },
                        )

            # Всі спроби exhaust - raise останню exception
            if last_exception:
                raise last_exception
            
            # Unreachable, but makes type checker happy
            raise RuntimeError("Retry logic error: no exception raised")

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            # Синхронна версія (якщо потрібно)
            raise NotImplementedError("Sync retry not implemented - use async functions")

        # Return async wrapper для async functions
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
