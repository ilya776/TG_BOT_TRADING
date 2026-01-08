"""
Proxy Manager Service
Manages rotating proxy pool for exchange API requests.

Features:
- Load balancing across multiple proxies
- Per-exchange rate limit tracking
- Automatic failover on proxy failures
- Health monitoring and statistics
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import redis
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy import Proxy, ProxyStatus
from app.utils.encryption import get_encryption_manager

logger = logging.getLogger(__name__)

# Redis for proxy state (faster than DB for real-time decisions)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Proxy health thresholds
MAX_CONSECUTIVE_FAILURES = 5
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60
PROXY_HEALTH_CHECK_INTERVAL = 300  # 5 minutes


class ProxyManager:
    """
    Manages rotating proxy pool for distributed API requests.

    Usage:
        manager = ProxyManager(redis_client)
        proxy = await manager.get_best_proxy("BINANCE")
        # ... make request ...
        await manager.record_request(proxy, success=True, response_time_ms=200)
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or redis.from_url(REDIS_URL, decode_responses=True)
        self._proxies_cache: list[Proxy] = []
        self._cache_updated_at: Optional[datetime] = None

    async def get_best_proxy(
        self,
        exchange: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[Proxy]:
        """
        Get the best available proxy for an exchange.

        Selection criteria:
        1. Status is ACTIVE
        2. Not rate-limited for this exchange
        3. Lowest recent usage (round-robin style)
        4. Best success rate

        Args:
            exchange: Exchange name (BINANCE, OKX, BITGET)
            db: Optional database session (uses cache if not provided)

        Returns:
            Best available proxy or None if no proxies available
        """
        if db:
            # Fetch fresh from database
            result = await db.execute(
                select(Proxy)
                .where(Proxy.status == ProxyStatus.ACTIVE)
                .order_by(Proxy.last_used_at.nulls_first())
            )
            proxies = list(result.scalars().all())
        else:
            # Use cached proxies (refreshed periodically)
            proxies = await self._get_cached_proxies()

        if not proxies:
            logger.warning("No proxies available in pool")
            return None

        # Filter by exchange availability
        available = [p for p in proxies if p.is_available_for_exchange(exchange)]

        if not available:
            logger.warning(f"No proxies available for {exchange} (all rate limited)")
            return None

        # Sort by: least recently used, then by success rate
        available.sort(
            key=lambda p: (
                p.last_used_at or datetime.min,
                -p.success_rate,
            )
        )

        best_proxy = available[0]
        logger.debug(
            f"Selected proxy {best_proxy.id} ({best_proxy.host}) for {exchange}, "
            f"success_rate={best_proxy.success_rate:.1f}%"
        )

        return best_proxy

    async def get_proxies_for_exchange(
        self,
        exchange: str,
        limit: int = 10,
        db: Optional[AsyncSession] = None,
    ) -> list[Proxy]:
        """Get multiple available proxies for parallel requests."""
        if db:
            result = await db.execute(
                select(Proxy)
                .where(Proxy.status == ProxyStatus.ACTIVE)
                .order_by(Proxy.last_used_at.nulls_first())
                .limit(limit * 2)  # Fetch extra in case some are rate limited
            )
            proxies = list(result.scalars().all())
        else:
            proxies = await self._get_cached_proxies()

        available = [p for p in proxies if p.is_available_for_exchange(exchange)]
        return available[:limit]

    async def record_request(
        self,
        proxy: Proxy,
        exchange: str,
        success: bool,
        response_time_ms: int,
        rate_limited: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Record the outcome of a request made through a proxy.

        Updates:
        - Request counters (total, success, failed)
        - Average response time
        - Last used timestamp
        - Rate limit status if applicable
        """
        now = datetime.utcnow()

        # Update counters
        proxy.total_requests += 1
        proxy.last_used_at = now

        if success:
            proxy.successful_requests += 1
            proxy.consecutive_failures = 0
            proxy.last_success_at = now

            # Update average response time (exponential moving average)
            if proxy.avg_response_time_ms:
                proxy.avg_response_time_ms = int(
                    0.8 * proxy.avg_response_time_ms + 0.2 * response_time_ms
                )
            else:
                proxy.avg_response_time_ms = response_time_ms
        else:
            proxy.failed_requests += 1
            proxy.consecutive_failures += 1
            proxy.last_failure_at = now

            # Check if proxy should be disabled
            if proxy.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    f"Proxy {proxy.id} disabled after {proxy.consecutive_failures} failures"
                )
                proxy.status = ProxyStatus.DISABLED

        # Handle rate limiting
        if rate_limited:
            await self.mark_rate_limited(
                proxy, exchange, DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS, db
            )

        # Persist to Redis for fast access
        await self._update_proxy_redis_state(proxy)

        if db:
            await db.commit()

    async def mark_rate_limited(
        self,
        proxy: Proxy,
        exchange: str,
        cooldown_seconds: int = 60,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Mark a proxy as rate-limited for a specific exchange."""
        now = datetime.utcnow()
        limit_until = now + timedelta(seconds=cooldown_seconds)

        # Update exchange-specific limits
        try:
            limits = json.loads(proxy.exchange_limits or "{}")
        except json.JSONDecodeError:
            limits = {}

        limits[exchange] = {
            "limited_until": limit_until.isoformat(),
            "requests_before_limit": proxy.total_requests,
        }
        proxy.exchange_limits = json.dumps(limits)

        logger.info(
            f"Proxy {proxy.id} rate-limited for {exchange} until "
            f"{limit_until.strftime('%H:%M:%S')}"
        )

        if db:
            await db.commit()

    async def clear_rate_limit(
        self,
        proxy: Proxy,
        exchange: str,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Clear rate limit for a specific exchange."""
        try:
            limits = json.loads(proxy.exchange_limits or "{}")
            if exchange in limits:
                del limits[exchange]
                proxy.exchange_limits = json.dumps(limits) if limits else None
        except json.JSONDecodeError:
            proxy.exchange_limits = None

        if db:
            await db.commit()

    async def get_pool_statistics(
        self,
        db: AsyncSession,
    ) -> dict:
        """Get statistics about the proxy pool."""
        result = await db.execute(select(Proxy))
        proxies = list(result.scalars().all())

        stats = {
            "total": len(proxies),
            "active": sum(1 for p in proxies if p.status == ProxyStatus.ACTIVE),
            "rate_limited": sum(1 for p in proxies if p.status == ProxyStatus.RATE_LIMITED),
            "disabled": sum(1 for p in proxies if p.status == ProxyStatus.DISABLED),
            "total_requests": sum(p.total_requests for p in proxies),
            "total_success": sum(p.successful_requests for p in proxies),
            "avg_success_rate": 0,
        }

        if stats["total_requests"] > 0:
            stats["avg_success_rate"] = (
                stats["total_success"] / stats["total_requests"] * 100
            )

        return stats

    async def load_proxies_from_file(
        self,
        file_path: str,
        db: AsyncSession,
    ) -> int:
        """
        Load proxies from a file into the database.

        File format (one per line):
        - Simple: host:port
        - With auth: user:pass@host:port
        - With protocol: socks5://host:port
        """
        loaded = 0

        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    proxy = self._parse_proxy_line(line)
                    if proxy:
                        db.add(proxy)
                        loaded += 1

            await db.commit()
            logger.info(f"Loaded {loaded} proxies from {file_path}")

        except Exception as e:
            logger.error(f"Error loading proxies from file: {e}")

        return loaded

    async def load_proxies_from_list(
        self,
        proxy_list: str,
        db: AsyncSession,
    ) -> int:
        """
        Load proxies from a comma-separated list (e.g., from environment variable).

        Format: "host:port,user:pass@host:port,socks5://host:port"
        """
        loaded = 0

        if not proxy_list:
            return 0

        try:
            for proxy_str in proxy_list.split(","):
                proxy_str = proxy_str.strip()
                if not proxy_str:
                    continue

                proxy = self._parse_proxy_line(proxy_str)
                if proxy:
                    # Check if proxy already exists
                    existing = await db.execute(
                        select(Proxy).where(
                            Proxy.host == proxy.host,
                            Proxy.port == proxy.port
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    db.add(proxy)
                    loaded += 1

            await db.commit()
            logger.info(f"Loaded {loaded} proxies from list")

        except Exception as e:
            logger.error(f"Error loading proxies from list: {e}")

        return loaded

    async def ensure_proxies_loaded(self, db: AsyncSession) -> int:
        """
        Ensure proxies are loaded from environment if not already present.
        Called at startup.
        """
        from app.config import get_settings
        settings = get_settings()

        # Check if we have any active proxies
        result = await db.execute(
            select(func.count(Proxy.id)).where(Proxy.status == ProxyStatus.ACTIVE)
        )
        count = result.scalar() or 0

        if count > 0:
            logger.info(f"Proxy pool: {count} active proxies already loaded")
            return count

        loaded = 0

        # Try to load from environment variable
        if settings.proxy_list:
            loaded = await self.load_proxies_from_list(settings.proxy_list, db)

        # Try to load from file
        if loaded == 0 and settings.proxy_pool_file:
            loaded = await self.load_proxies_from_file(settings.proxy_pool_file, db)

        if loaded == 0:
            logger.warning(
                "No proxies loaded. Set PROXY_LIST env var (comma-separated) "
                "or PROXY_POOL_FILE to enable proxy rotation."
            )

        return loaded

    def _parse_proxy_line(self, line: str) -> Optional[Proxy]:
        """Parse a proxy line into a Proxy object."""
        try:
            protocol = "http"
            username = None
            password = None

            # Check for protocol prefix
            if "://" in line:
                protocol, line = line.split("://", 1)

            # Check for authentication
            if "@" in line:
                auth, line = line.rsplit("@", 1)
                if ":" in auth:
                    username, password = auth.split(":", 1)

            # Parse host:port
            if ":" in line:
                host, port_str = line.rsplit(":", 1)
                port = int(port_str)
            else:
                host = line
                port = 8080  # Default port

            # Encrypt password for secure storage
            encryption_manager = get_encryption_manager()
            password_encrypted = encryption_manager.encrypt(password) if password else ""

            return Proxy(
                host=host,
                port=port,
                protocol=protocol,
                username=username,
                password_encrypted=password_encrypted,
                status=ProxyStatus.ACTIVE,
            )

        except Exception as e:
            logger.warning(f"Failed to parse proxy line '{line}': {e}")
            return None

    async def _get_cached_proxies(self) -> list[Proxy]:
        """Get proxies from cache or database."""
        # Simple in-memory cache, refresh every 5 minutes
        now = datetime.utcnow()
        if (
            not self._proxies_cache
            or not self._cache_updated_at
            or (now - self._cache_updated_at).seconds > 300
        ):
            # Refresh cache from database
            from app.database import get_db_context

            async with get_db_context() as db:
                result = await db.execute(
                    select(Proxy).where(Proxy.status == ProxyStatus.ACTIVE)
                )
                self._proxies_cache = list(result.scalars().all())
                self._cache_updated_at = now

        return self._proxies_cache

    async def _update_proxy_redis_state(self, proxy: Proxy) -> None:
        """Update proxy state in Redis for fast access."""
        key = f"proxy:{proxy.id}:state"
        state = {
            "last_used": proxy.last_used_at.isoformat() if proxy.last_used_at else None,
            "status": proxy.status,
            "consecutive_failures": proxy.consecutive_failures,
            "exchange_limits": proxy.exchange_limits,
        }
        self.redis.setex(key, 600, json.dumps(state))  # 10 min TTL


# Singleton instance
_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager() -> ProxyManager:
    """Get singleton ProxyManager instance."""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager
