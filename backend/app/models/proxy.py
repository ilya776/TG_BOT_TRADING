"""
Proxy Pool Model
Manages rotating proxies for exchange API requests to bypass rate limits.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProxyStatus(str, Enum):
    """Status of a proxy in the pool."""
    ACTIVE = "ACTIVE"
    RATE_LIMITED = "RATE_LIMITED"
    BANNED = "BANNED"
    COOLING_DOWN = "COOLING_DOWN"
    DISABLED = "DISABLED"


class ProxyProtocol(str, Enum):
    """Supported proxy protocols."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class Proxy(Base):
    """
    Rotating proxy for exchange API requests.

    Used to distribute requests across multiple IPs to avoid
    rate limiting from exchanges.
    """

    __tablename__ = "proxies"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Proxy connection details
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(
        String(10), default="http"
    )  # http, https, socks5

    # Authentication (optional)
    username: Mapped[str | None] = mapped_column(String(100))
    password_encrypted: Mapped[str | None] = mapped_column(String(255))

    # Status tracking
    status: Mapped[ProxyStatus] = mapped_column(
        String(20), default=ProxyStatus.ACTIVE
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    rate_limited_until: Mapped[datetime | None] = mapped_column(DateTime)

    # Per-exchange rate limit tracking (JSON)
    # Format: {"BINANCE": {"limited_until": "2024-01-01T00:00:00", "requests_today": 100}}
    exchange_limits: Mapped[str | None] = mapped_column(Text)

    # Performance metrics
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Health tracking
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure_reason: Mapped[str | None] = mapped_column(String(500))

    # Metadata
    name: Mapped[str | None] = mapped_column(String(100))  # Friendly name
    provider: Mapped[str | None] = mapped_column(String(50))  # BrightData, Oxylabs, etc.
    is_residential: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Proxy(id={self.id}, host={self.host}:{self.port}, status={self.status})>"

    @property
    def url(self) -> str:
        """Get proxy URL for httpx/requests."""
        if self.username and self.password_encrypted:
            # Note: In production, decrypt password_encrypted first
            return f"{self.protocol}://{self.username}:{self.password_encrypted}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    def is_available(self) -> bool:
        """Check if proxy is available for use."""
        if self.status != ProxyStatus.ACTIVE:
            return False
        if self.rate_limited_until and self.rate_limited_until > datetime.utcnow():
            return False
        return True

    def is_available_for_exchange(self, exchange: str) -> bool:
        """Check if proxy is available for specific exchange."""
        if not self.is_available():
            return False

        if not self.exchange_limits:
            return True

        import json
        try:
            limits = json.loads(self.exchange_limits)
            if exchange in limits:
                limited_until = limits[exchange].get("limited_until")
                if limited_until:
                    limit_time = datetime.fromisoformat(limited_until)
                    if limit_time > datetime.utcnow():
                        return False
        except (json.JSONDecodeError, ValueError):
            pass

        return True
