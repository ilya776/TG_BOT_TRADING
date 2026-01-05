#!/usr/bin/env python3
"""
Script to clean up test/demo data from the database.
Run on the server: python scripts/cleanup_test_data.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.signal import WhaleSignal


async def cleanup_test_signals():
    """Remove test/demo signals from the database."""
    settings = get_settings()

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Count current signals
        count_result = await db.execute(select(text("COUNT(*)")).select_from(WhaleSignal.__table__))
        total_count = count_result.scalar()
        print(f"Total signals in database: {total_count}")

        # Option 1: Delete signals with known test tx_hashes
        test_hashes = [
            # Add known test transaction hashes here
            "0xtest",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ]

        # Option 2: Delete signals older than 30 days with status EXPIRED or FAILED
        from datetime import datetime, timedelta
        from app.models.signal import SignalStatus

        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # Delete old expired/failed signals
        delete_old = delete(WhaleSignal).where(
            WhaleSignal.detected_at < cutoff_date,
            WhaleSignal.status.in_([SignalStatus.EXPIRED, SignalStatus.FAILED])
        )
        result = await db.execute(delete_old)
        deleted_old = result.rowcount
        print(f"Deleted {deleted_old} old expired/failed signals")

        # Delete signals with test tx_hashes
        for test_hash in test_hashes:
            delete_test = delete(WhaleSignal).where(
                WhaleSignal.tx_hash.like(f"{test_hash}%")
            )
            result = await db.execute(delete_test)
            if result.rowcount > 0:
                print(f"Deleted {result.rowcount} signals with hash starting '{test_hash}'")

        # Commit changes
        await db.commit()

        # Count remaining signals
        count_result = await db.execute(select(text("COUNT(*)")).select_from(WhaleSignal.__table__))
        remaining = count_result.scalar()
        print(f"Remaining signals: {remaining}")

    await engine.dispose()
    print("Cleanup complete!")


async def list_recent_signals():
    """List recent signals for inspection."""
    settings = get_settings()

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(
            select(WhaleSignal)
            .order_by(WhaleSignal.detected_at.desc())
            .limit(20)
        )
        signals = result.scalars().all()

        print("\nRecent signals:")
        print("-" * 80)
        for s in signals:
            print(f"ID: {s.id}, Whale: {s.whale_id}, Token: {s.token_out}, Amount: ${s.amount_usd}, Status: {s.status.value}")
            print(f"   TX: {s.tx_hash[:20]}..., Detected: {s.detected_at}")

    await engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean up test data from database")
    parser.add_argument("--list", action="store_true", help="List recent signals instead of cleaning")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_recent_signals())
    else:
        print("Starting cleanup...")
        asyncio.run(cleanup_test_signals())
