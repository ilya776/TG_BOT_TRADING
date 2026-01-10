"""
On-Chain Wallet Model
Tracks whale wallets on DEX chains (ETH, BSC, Arbitrum, etc.)
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChainType(str, Enum):
    """Supported blockchain networks."""
    ETHEREUM = "ETHEREUM"
    BSC = "BSC"
    ARBITRUM = "ARBITRUM"
    OPTIMISM = "OPTIMISM"
    POLYGON = "POLYGON"
    BASE = "BASE"
    AVALANCHE = "AVALANCHE"


class WalletType(str, Enum):
    """Classification of wallet types."""
    SMART_MONEY = "SMART_MONEY"      # Profitable DeFi traders
    WHALE = "WHALE"                   # Large holders
    FUND = "FUND"                     # Known fund/VC wallet
    DEX_TRADER = "DEX_TRADER"         # Active DEX trader
    MEV_BOT = "MEV_BOT"               # MEV/arbitrage bot
    EXCHANGE = "EXCHANGE"             # CEX hot/cold wallet
    CONTRACT = "CONTRACT"             # Smart contract
    UNKNOWN = "UNKNOWN"


class DiscoverySource(str, Enum):
    """How the wallet was discovered."""
    ETHERSCAN_TOP_HOLDERS = "ETHERSCAN_TOP_HOLDERS"
    DUNE_QUERY = "DUNE_QUERY"
    KNOWN_WHALE = "KNOWN_WHALE"
    MANUAL = "MANUAL"
    TOKEN_TRANSFER = "TOKEN_TRANSFER"
    DEX_ACTIVITY = "DEX_ACTIVITY"


class OnChainWallet(Base):
    """
    On-chain whale wallet for DEX/DeFi monitoring.

    Tracks wallets across multiple chains and monitors their
    DEX swaps to generate trading signals.
    """

    __tablename__ = "onchain_wallets"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Link to main Whale record (optional - may exist independently)
    whale_id: Mapped[int | None] = mapped_column(
        ForeignKey("whales.id", ondelete="SET NULL"),
        index=True
    )

    # Wallet identification
    address: Mapped[str] = mapped_column(String(42), index=True)
    chain: Mapped[str] = mapped_column(String(20), index=True)  # ETHEREUM, BSC, etc.

    # Unique constraint on address + chain (same address on different chains = different wallets)
    # This is defined in __table_args__

    # Discovery metadata
    discovery_source: Mapped[str] = mapped_column(
        String(50), default=DiscoverySource.MANUAL
    )
    discovery_data: Mapped[str | None] = mapped_column(Text)  # JSON with context
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Wallet classification
    wallet_type: Mapped[str] = mapped_column(
        String(20), default=WalletType.UNKNOWN
    )
    label: Mapped[str | None] = mapped_column(String(100))  # Known label (e.g., "Alameda Research")
    tags: Mapped[str | None] = mapped_column(String(500))  # Comma-separated tags

    # Tracking status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Transaction tracking
    last_tx_hash: Mapped[str | None] = mapped_column(String(66))
    last_tx_block: Mapped[int] = mapped_column(BigInteger, default=0)
    last_tx_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Activity metrics
    total_swaps_detected: Mapped[int] = mapped_column(Integer, default=0)
    total_transfers_detected: Mapped[int] = mapped_column(Integer, default=0)

    # Portfolio metrics (estimated)
    estimated_portfolio_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    last_portfolio_update: Mapped[datetime | None] = mapped_column(DateTime)

    # Performance metrics (calculated from signal outcomes)
    win_rate_7d: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    win_rate_30d: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    avg_trade_size_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    total_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Priority for monitoring
    priority_score: Mapped[int] = mapped_column(Integer, default=50)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    whale: Mapped["Whale | None"] = relationship(back_populates="onchain_wallets")

    __table_args__ = (
        # Unique constraint: same address on different chains = different wallets
        Index("ix_onchain_wallets_address_chain", "address", "chain", unique=True),
        Index("ix_onchain_wallets_chain_active", "chain", "is_active"),
        Index("ix_onchain_wallets_type_priority", "wallet_type", "priority_score"),
    )

    def __repr__(self) -> str:
        return f"<OnChainWallet(id={self.id}, address={self.address[:10]}..., chain={self.chain})>"

    @property
    def explorer_url(self) -> str:
        """Get block explorer URL for this wallet."""
        explorers = {
            "ETHEREUM": "https://etherscan.io/address/",
            "BSC": "https://bscscan.com/address/",
            "ARBITRUM": "https://arbiscan.io/address/",
            "OPTIMISM": "https://optimistic.etherscan.io/address/",
            "POLYGON": "https://polygonscan.com/address/",
            "BASE": "https://basescan.org/address/",
            "AVALANCHE": "https://snowtrace.io/address/",
        }
        base_url = explorers.get(self.chain, "https://etherscan.io/address/")
        return f"{base_url}{self.address}"


# Add relationship to Whale model
from app.models.whale import Whale
Whale.onchain_wallets = relationship(
    "OnChainWallet",
    back_populates="whale",
    cascade="all, delete-orphan"
)
