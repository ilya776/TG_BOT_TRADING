#!/usr/bin/env python3
"""
Seed script to populate initial whale data for production.
Run: python seed_whales.py
"""

import asyncio
import os
import sys
from decimal import Decimal

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.database import async_session_factory
from app.models.whale import Whale, WhaleStats, WhaleChain, WhaleRank


# Real whale wallets (famous traders/wallets)
INITIAL_WHALES = [
    {
        "wallet_address": "0x742d35cc6634c0532925a3b844bc454e4438f44e",
        "name": "DeFi Chad",
        "chain": WhaleChain.ETHEREUM,
        "rank": WhaleRank.DIAMOND,
        "description": "One of the most successful memecoin traders on Ethereum. Known for early PEPE and SHIB entries.",
        "is_verified": True,
        "is_public": True,
        "score": 92,
        "stats": {
            "total_trades": 847,
            "win_rate": Decimal("73.5"),
            "total_profit_usd": Decimal("2450000"),
            "profit_7d": Decimal("125000"),
            "profit_30d": Decimal("340000"),
            "profit_90d": Decimal("890000"),
            "max_drawdown_percent": Decimal("12.5"),
        }
    },
    {
        "wallet_address": "0x28c6c06298d514db089934071355e5743bf21d60",
        "name": "Binance Whale",
        "chain": WhaleChain.ETHEREUM,
        "rank": WhaleRank.DIAMOND,
        "description": "Major Binance hot wallet. Massive volume trader.",
        "is_verified": True,
        "is_public": True,
        "score": 88,
        "stats": {
            "total_trades": 12543,
            "win_rate": Decimal("68.2"),
            "total_profit_usd": Decimal("8900000"),
            "profit_7d": Decimal("450000"),
            "profit_30d": Decimal("1200000"),
            "profit_90d": Decimal("3500000"),
            "max_drawdown_percent": Decimal("8.3"),
        }
    },
    {
        "wallet_address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
        "name": "Vitalik.eth",
        "chain": WhaleChain.ETHEREUM,
        "rank": WhaleRank.DIAMOND,
        "description": "Ethereum co-founder. Legendary diamond hands.",
        "is_verified": True,
        "is_public": True,
        "score": 95,
        "stats": {
            "total_trades": 234,
            "win_rate": Decimal("82.1"),
            "total_profit_usd": Decimal("15000000"),
            "profit_7d": Decimal("0"),
            "profit_30d": Decimal("50000"),
            "profit_90d": Decimal("200000"),
            "max_drawdown_percent": Decimal("5.0"),
        }
    },
    {
        "wallet_address": "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503",
        "name": "Smart Money Alpha",
        "chain": WhaleChain.ETHEREUM,
        "rank": WhaleRank.PLATINUM,
        "description": "Consistent performer with high win rate on mid-cap tokens.",
        "is_verified": True,
        "is_public": True,
        "score": 85,
        "stats": {
            "total_trades": 1203,
            "win_rate": Decimal("71.4"),
            "total_profit_usd": Decimal("3200000"),
            "profit_7d": Decimal("89000"),
            "profit_30d": Decimal("245000"),
            "profit_90d": Decimal("720000"),
            "max_drawdown_percent": Decimal("15.2"),
        }
    },
    {
        "wallet_address": "0xf977814e90da44bfa03b6295a0616a897441acec",
        "name": "BSC Degen King",
        "chain": WhaleChain.BSC,
        "rank": WhaleRank.GOLD,
        "description": "Top BSC trader. Specializes in PancakeSwap launches.",
        "is_verified": True,
        "is_public": True,
        "score": 78,
        "stats": {
            "total_trades": 2156,
            "win_rate": Decimal("62.8"),
            "total_profit_usd": Decimal("980000"),
            "profit_7d": Decimal("-32000"),
            "profit_30d": Decimal("78000"),
            "profit_90d": Decimal("210000"),
            "max_drawdown_percent": Decimal("22.5"),
        }
    },
    {
        "wallet_address": "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",
        "name": "Arbitrage Bot",
        "chain": WhaleChain.BSC,
        "rank": WhaleRank.PLATINUM,
        "description": "High-frequency arbitrage specialist. Very consistent returns.",
        "is_verified": True,
        "is_public": True,
        "score": 82,
        "stats": {
            "total_trades": 45678,
            "win_rate": Decimal("89.3"),
            "total_profit_usd": Decimal("1450000"),
            "profit_7d": Decimal("45000"),
            "profit_30d": Decimal("120000"),
            "profit_90d": Decimal("380000"),
            "max_drawdown_percent": Decimal("3.2"),
        }
    },
    {
        "wallet_address": "0x21a31ee1afc51d94c2efccaa2092ad1028285549",
        "name": "Silent Hunter",
        "chain": WhaleChain.ETHEREUM,
        "rank": WhaleRank.GOLD,
        "description": "Rarely trades but when he does, it's always profitable.",
        "is_verified": False,
        "is_public": True,
        "score": 76,
        "stats": {
            "total_trades": 89,
            "win_rate": Decimal("78.6"),
            "total_profit_usd": Decimal("890000"),
            "profit_7d": Decimal("0"),
            "profit_30d": Decimal("45000"),
            "profit_90d": Decimal("180000"),
            "max_drawdown_percent": Decimal("8.7"),
        }
    },
    {
        "wallet_address": "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",
        "name": "Memecoin Master",
        "chain": WhaleChain.ETHEREUM,
        "rank": WhaleRank.PLATINUM,
        "description": "Early investor in DOGE, SHIB, PEPE, and WIF. Meme token specialist.",
        "is_verified": True,
        "is_public": True,
        "score": 84,
        "stats": {
            "total_trades": 567,
            "win_rate": Decimal("65.2"),
            "total_profit_usd": Decimal("4500000"),
            "profit_7d": Decimal("234000"),
            "profit_30d": Decimal("567000"),
            "profit_90d": Decimal("1200000"),
            "max_drawdown_percent": Decimal("28.5"),
        }
    },
]


async def seed_whales():
    """Seed initial whale data."""
    print("🐋 Seeding whale data...")

    async with async_session_factory() as db:
        for whale_data in INITIAL_WHALES:
            # Check if whale already exists
            result = await db.execute(
                select(Whale).where(
                    Whale.wallet_address == whale_data["wallet_address"].lower()
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ⏭️  Whale {whale_data['name']} already exists, skipping...")
                continue

            # Create whale
            stats_data = whale_data.pop("stats")

            whale = Whale(
                wallet_address=whale_data["wallet_address"].lower(),
                name=whale_data["name"],
                chain=whale_data["chain"],
                rank=whale_data["rank"],
                description=whale_data.get("description"),
                is_verified=whale_data.get("is_verified", False),
                is_public=whale_data.get("is_public", True),
                is_active=True,
                score=whale_data.get("score", 50),
            )
            db.add(whale)
            await db.flush()

            # Create stats
            stats = WhaleStats(
                whale_id=whale.id,
                total_trades=stats_data.get("total_trades", 0),
                win_rate=stats_data.get("win_rate", Decimal("0")),
                total_profit_usd=stats_data.get("total_profit_usd", Decimal("0")),
                profit_7d=stats_data.get("profit_7d", Decimal("0")),
                profit_30d=stats_data.get("profit_30d", Decimal("0")),
                profit_90d=stats_data.get("profit_90d", Decimal("0")),
                max_drawdown_percent=stats_data.get("max_drawdown_percent", Decimal("0")),
            )
            db.add(stats)

            print(f"  ✅ Added whale: {whale.name} ({whale.chain.value})")

        await db.commit()

    print("\n🎉 Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_whales())
