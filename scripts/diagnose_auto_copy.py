#!/usr/bin/env python3
"""
Diagnose Auto-Copy Issue
========================
Checks why trades aren't being created from signals.

Usage:
    python scripts/diagnose_auto_copy.py

Requires:
    - Database connection via DATABASE_URL environment variable
    - Or: Set in .env file
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from sqlalchemy import create_engine, text
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Missing dependencies. Install with:")
    print("  pip install sqlalchemy psycopg2-binary python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment")
    print("Set it in .env file or export it:")
    print("  export DATABASE_URL='postgresql://user:pass@host:5432/trading_bot'")
    sys.exit(1)


def diagnose():
    """Run diagnostic checks."""
    print("=" * 60)
    print("Auto-Copy Diagnostic Tool")
    print("=" * 60)
    print()

    # Connect to database
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    print()

    # Check 1: User whale follows with auto_copy status
    print("1. Checking User Whale Follows")
    print("-" * 60)
    result = conn.execute(text("""
        SELECT
            uwf.id,
            uwf.user_id,
            uwf.whale_id,
            w.name as whale_name,
            uwf.auto_copy_enabled,
            uwf.notify_on_trade,
            uwf.trade_size_percent,
            u.available_balance,
            u.is_active as user_active
        FROM user_whale_follows uwf
        JOIN whales w ON uwf.whale_id = w.id
        JOIN users u ON uwf.user_id = u.id
        WHERE u.is_active = true
        ORDER BY uwf.user_id, uwf.created_at DESC;
    """))

    follows = result.fetchall()
    if not follows:
        print("❌ No active user whale follows found!")
        print("   Users must follow whales first.")
    else:
        auto_copy_enabled_count = sum(1 for f in follows if f.auto_copy_enabled)
        print(f"   Total follows: {len(follows)}")
        print(f"   Auto-copy enabled: {auto_copy_enabled_count}")
        print(f"   Auto-copy disabled: {len(follows) - auto_copy_enabled_count}")
        print()

        for follow in follows[:5]:  # Show first 5
            status = "✅" if follow.auto_copy_enabled else "❌"
            print(f"   {status} User {follow.user_id} → {follow.whale_name}")
            print(f"      Auto-copy: {follow.auto_copy_enabled}, "
                  f"Size: {follow.trade_size_percent}%, "
                  f"Balance: ${follow.available_balance}")

        if len(follows) > 5:
            print(f"   ... and {len(follows) - 5} more")

    print()

    # Check 2: Recent signals
    print("2. Checking Recent Signals")
    print("-" * 60)
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
            COUNT(*) FILTER (WHERE status = 'PROCESSING') as processing,
            COUNT(*) FILTER (WHERE status = 'PROCESSED') as processed,
            COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
            COUNT(*) FILTER (WHERE cex_available = true) as cex_available,
            COUNT(*) FILTER (WHERE cex_symbol IS NOT NULL) as has_cex_symbol
        FROM whale_signals
        WHERE detected_at >= NOW() - INTERVAL '1 hour';
    """))

    signals = result.fetchone()
    print(f"   Last hour: {signals.total} signals")
    print(f"   ├─ PENDING: {signals.pending}")
    print(f"   ├─ PROCESSING: {signals.processing}")
    print(f"   ├─ PROCESSED: {signals.processed}")
    print(f"   ├─ FAILED: {signals.failed}")
    print(f"   ├─ CEX available: {signals.cex_available}")
    print(f"   └─ Has CEX symbol: {signals.has_cex_symbol}")

    print()

    # Check 3: Recent trades
    print("3. Checking Recent Trades")
    print("-" * 60)
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
            COUNT(*) FILTER (WHERE status = 'EXECUTING') as executing,
            COUNT(*) FILTER (WHERE status = 'FILLED') as filled,
            COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
            MAX(created_at) as last_trade
        FROM trades
        WHERE created_at >= NOW() - INTERVAL '1 hour';
    """))

    trades = result.fetchone()
    print(f"   Last hour: {trades.total} trades")
    print(f"   ├─ PENDING: {trades.pending}")
    print(f"   ├─ EXECUTING: {trades.executing}")
    print(f"   ├─ FILLED: {trades.filled}")
    print(f"   ├─ FAILED: {trades.failed}")
    if trades.last_trade:
        print(f"   └─ Last trade: {trades.last_trade}")
    else:
        print("   └─ ❌ No trades in last hour!")

    print()

    # Check 4: Diagnosis
    print("4. Diagnosis")
    print("-" * 60)

    issues_found = []

    if not follows:
        issues_found.append("No user whale follows configured")
    elif auto_copy_enabled_count == 0:
        issues_found.append("All follows have auto_copy_enabled = FALSE")
        issues_found.append("This is the ROOT CAUSE - signals can't execute!")

    if signals.processed > 0 and trades.total == 0:
        issues_found.append(f"{signals.processed} signals marked PROCESSED but 0 trades created")

    if not issues_found:
        print("✅ No obvious issues found")
        print("   If trades still not working, check:")
        print("   - Celery workers are running")
        print("   - Exchange API keys are valid")
        print("   - User has sufficient balance")
        print("   - Check backend logs for errors")
    else:
        print("❌ Issues found:")
        for i, issue in enumerate(issues_found, 1):
            print(f"   {i}. {issue}")

        if auto_copy_enabled_count == 0:
            print()
            print("🔧 FIX:")
            print("   Run this SQL to enable auto-copy:")
            print()
            print("   UPDATE user_whale_follows")
            print("   SET auto_copy_enabled = true,")
            print("       notify_on_trade = true,")
            print("       trade_size_percent = COALESCE(trade_size_percent, 100)")
            print("   WHERE auto_copy_enabled = false;")
            print()
            print("   Or use: scripts/fix_auto_copy.sh")

    print()
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    diagnose()
