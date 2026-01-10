"""
Free Proxy Fetcher

Fetches and validates free proxies from public sources.
WARNING: Free proxies are unreliable - for development/testing only.

Sources:
- proxyscrape.com API
- geonode.com API
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy import Proxy, ProxyStatus

logger = logging.getLogger(__name__)

# Public free proxy sources
PROXY_SOURCES = [
    {
        "name": "proxyscrape_http",
        "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=elite",
        "format": "text",  # host:port per line
    },
    {
        "name": "proxyscrape_socks5",
        "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all",
        "format": "text",
    },
    {
        "name": "geonode",
        "url": "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps%2Csocks5",
        "format": "geonode_json",
    },
]

# Test URLs for different exchanges
EXCHANGE_TEST_URLS = {
    "BINANCE": "https://fapi.binance.com/fapi/v1/ping",
    "OKX": "https://www.okx.com/api/v5/public/time",
    "BITGET": "https://api.bitget.com/api/v2/public/time",
}

# Minimum proxies to maintain in pool
MIN_ACTIVE_PROXIES = 10
MAX_PROXIES_TO_TEST = 500  # Test more to find working ones


class FreeProxyFetcher:
    """Fetches and validates free proxies."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self.client.aclose()

    async def fetch_all_proxies(self) -> list[tuple[str, int, str]]:
        """
        Fetch proxies from all sources.

        Returns:
            List of (host, port, protocol) tuples
        """
        all_proxies = []

        for source in PROXY_SOURCES:
            try:
                proxies = await self._fetch_from_source(source)
                all_proxies.extend(proxies)
                logger.info(f"Fetched {len(proxies)} proxies from {source['name']}")
            except Exception as e:
                logger.warning(f"Failed to fetch from {source['name']}: {e}")

        # Deduplicate by (host, port)
        seen = set()
        unique_proxies = []
        for host, port, protocol in all_proxies:
            key = (host, port)
            if key not in seen:
                seen.add(key)
                unique_proxies.append((host, port, protocol))

        logger.info(f"Total unique proxies fetched: {len(unique_proxies)}")
        return unique_proxies

    async def _fetch_from_source(
        self, source: dict
    ) -> list[tuple[str, int, str]]:
        """Fetch proxies from a single source."""
        response = await self.client.get(source["url"])
        response.raise_for_status()

        proxies = []
        fmt = source.get("format", "text")

        if fmt == "text":
            # Format: host:port per line
            for line in response.text.strip().split("\n"):
                line = line.strip()
                if ":" in line:
                    try:
                        host, port_str = line.split(":", 1)
                        port = int(port_str)
                        protocol = "socks5" if "socks5" in source["name"] else "http"
                        proxies.append((host, port, protocol))
                    except (ValueError, IndexError):
                        continue

        elif fmt == "geonode_json":
            # GeoNode JSON format
            data = response.json()
            for item in data.get("data", []):
                host = item.get("ip")
                port = item.get("port")
                protocols = item.get("protocols", ["http"])
                if host and port:
                    protocol = protocols[0] if protocols else "http"
                    proxies.append((host, int(port), protocol))

        return proxies

    async def test_proxy(
        self,
        host: str,
        port: int,
        protocol: str = "http",
        test_url: Optional[str] = None,
    ) -> tuple[bool, int]:
        """
        Test if a proxy is working.

        Returns:
            (success, response_time_ms)
        """
        # First test against httpbin (more permissive)
        if test_url is None:
            test_url = "https://httpbin.org/ip"

        proxy_url = f"{protocol}://{host}:{port}"

        try:
            start = datetime.utcnow()
            async with httpx.AsyncClient(
                proxies={"all://": proxy_url},
                timeout=self.timeout,
            ) as client:
                response = await client.get(test_url)
                elapsed = (datetime.utcnow() - start).total_seconds() * 1000

                if response.status_code == 200:
                    return True, int(elapsed)

        except Exception as e:
            logger.debug(f"Proxy {host}:{port} failed: {e}")

        return False, 0

    async def test_proxy_for_exchange(
        self,
        host: str,
        port: int,
        protocol: str = "http",
        exchange: str = "OKX",
    ) -> tuple[bool, int]:
        """
        Test if a proxy works for a specific exchange.
        """
        test_url = EXCHANGE_TEST_URLS.get(exchange, "https://httpbin.org/ip")
        return await self.test_proxy(host, port, protocol, test_url)

    async def test_proxy_for_exchanges(
        self,
        host: str,
        port: int,
        protocol: str = "http",
    ) -> dict[str, bool]:
        """
        Test proxy against all supported exchanges.

        Returns:
            Dict of exchange -> works (True/False)
        """
        results = {}

        for exchange, test_url in EXCHANGE_TEST_URLS.items():
            success, _ = await self.test_proxy(host, port, protocol, test_url)
            results[exchange] = success

        return results


async def refresh_free_proxies(db: AsyncSession, min_active: int = MIN_ACTIVE_PROXIES) -> dict:
    """
    Refresh free proxy pool.

    1. Check current active proxy count
    2. If below minimum, fetch and test new proxies
    3. Remove stale/dead proxies

    Returns:
        Statistics about the refresh operation
    """
    stats = {
        "fetched": 0,
        "tested": 0,
        "added": 0,
        "removed": 0,
        "active": 0,
    }

    # Count current active proxies
    result = await db.execute(
        select(Proxy).where(Proxy.status == ProxyStatus.ACTIVE)
    )
    active_proxies = list(result.scalars().all())
    stats["active"] = len(active_proxies)

    logger.info(f"Current active proxies: {stats['active']}, minimum: {min_active}")

    # Remove proxies that haven't been used successfully in 1 hour
    stale_cutoff = datetime.utcnow() - timedelta(hours=1)
    stale_result = await db.execute(
        select(Proxy).where(
            Proxy.provider == "free",
            Proxy.last_success_at < stale_cutoff,
        )
    )
    stale_proxies = list(stale_result.scalars().all())
    for proxy in stale_proxies:
        await db.delete(proxy)
        stats["removed"] += 1

    if stats["removed"] > 0:
        logger.info(f"Removed {stats['removed']} stale free proxies")
        await db.commit()

    # If we have enough, skip fetching
    if stats["active"] >= min_active:
        logger.info(f"Proxy pool sufficient ({stats['active']} >= {min_active})")
        return stats

    # Fetch new proxies
    fetcher = FreeProxyFetcher()
    try:
        raw_proxies = await fetcher.fetch_all_proxies()
        stats["fetched"] = len(raw_proxies)

        # Filter out proxies we already have
        existing_result = await db.execute(select(Proxy.host, Proxy.port))
        existing = {(row[0], row[1]) for row in existing_result.all()}

        new_proxies = [
            (h, p, proto) for h, p, proto in raw_proxies
            if (h, p) not in existing
        ]

        # Shuffle and test proxies concurrently in batches
        random.shuffle(new_proxies)
        to_test = new_proxies[:MAX_PROXIES_TO_TEST]
        batch_size = 50  # Test 50 concurrently

        for i in range(0, len(to_test), batch_size):
            batch = to_test[i:i + batch_size]

            async def test_one(proxy_info):
                host, port, protocol = proxy_info
                success, response_time = await fetcher.test_proxy(host, port, protocol)
                return (host, port, protocol, success, response_time)

            # Test batch concurrently
            results = await asyncio.gather(
                *[test_one(p) for p in batch],
                return_exceptions=True
            )

            for result in results:
                if isinstance(result, Exception):
                    continue
                host, port, protocol, success, response_time = result
                stats["tested"] += 1

                if success:
                    proxy = Proxy(
                        host=host,
                        port=port,
                        protocol=protocol,
                        status=ProxyStatus.ACTIVE,
                        provider="free",
                        name=f"Free-{host}",
                        avg_response_time_ms=response_time,
                        last_success_at=datetime.utcnow(),
                    )
                    db.add(proxy)
                    stats["added"] += 1

            # Check if we have enough
            if stats["active"] + stats["added"] >= min_active:
                break

        await db.commit()

        # Update final active count
        final_result = await db.execute(
            select(Proxy).where(Proxy.status == ProxyStatus.ACTIVE)
        )
        stats["active"] = len(list(final_result.scalars().all()))

    except Exception as e:
        logger.error(f"Error refreshing free proxies: {e}")
    finally:
        await fetcher.close()

    logger.info(
        f"Proxy refresh complete: fetched={stats['fetched']}, "
        f"tested={stats['tested']}, added={stats['added']}, "
        f"active={stats['active']}"
    )

    return stats
