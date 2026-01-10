"""Extend tables for Clean Architecture support.

Adds columns needed for Clean Architecture patterns:
- Priority queue support for whale_signals
- Optimistic locking (version) for trades/positions
- New indexes for performance

Revision ID: 001
Revises: None
Create Date: 2026-01-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema.

    Changes:
    1. Add priority column to whale_signals for queue processing
    2. Add source column to whale_signals for multi-source support
    3. Add trade_type column to whale_signals for spot/futures
    4. Add version columns to trades/positions for optimistic locking
    5. Add composite indexes for performance
    """
    # ====================================
    # WHALE_SIGNALS TABLE - Priority Queue Support
    # ====================================

    # Check if column exists before adding (idempotent migration)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = {col["name"] for col in inspector.get_columns("whale_signals")}

    # Add priority column (for SignalQueue)
    if "priority" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "priority",
                sa.String(10),
                nullable=False,
                server_default="medium",
            ),
        )
        op.create_index(
            "ix_whale_signals_priority",
            "whale_signals",
            ["priority"],
        )

    # Add source column (whale, indicator, manual, etc.)
    if "source" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "source",
                sa.String(20),
                nullable=False,
                server_default="whale",
            ),
        )
        op.create_index(
            "ix_whale_signals_source",
            "whale_signals",
            ["source"],
        )

    # Add trade_type column (spot/futures)
    if "trade_type" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "trade_type",
                sa.String(20),
                nullable=False,
                server_default="spot",
            ),
        )

    # Add side column if missing (buy/sell)
    if "side" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "side",
                sa.String(10),
                nullable=False,
                server_default="buy",
            ),
        )

    # Add symbol column if missing (CEX symbol like BTCUSDT)
    if "symbol" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "symbol",
                sa.String(20),
                nullable=True,  # Can be null for on-chain only signals
            ),
        )
        # Note: cex_symbol already exists, can be used as fallback

    # Add entry_price column for signal queue
    if "entry_price" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "entry_price",
                sa.Numeric(20, 8),
                nullable=True,
            ),
        )

    # Add quantity column for signal queue
    if "quantity" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "quantity",
                sa.Numeric(20, 8),
                nullable=True,
            ),
        )

    # Add leverage column for futures
    if "leverage" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "leverage",
                sa.Integer(),
                nullable=True,
            ),
        )

    # Add metadata_json for SL/TP etc.
    if "metadata_json" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "metadata_json",
                sa.Text(),
                nullable=True,
            ),
        )

    # Add trades_executed counter
    if "trades_executed" not in existing_columns:
        op.add_column(
            "whale_signals",
            sa.Column(
                "trades_executed",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    # ====================================
    # COMPOSITE INDEXES for SignalQueue
    # ====================================

    # Check existing indexes
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("whale_signals")}

    # Priority queue index (status + priority + detected_at)
    if "ix_signals_queue" not in existing_indexes:
        op.create_index(
            "ix_signals_queue",
            "whale_signals",
            ["status", "priority", "detected_at"],
        )

    # Whale signals by status
    if "ix_signals_whale_status" not in existing_indexes:
        op.create_index(
            "ix_signals_whale_status",
            "whale_signals",
            ["whale_id", "status", "detected_at"],
        )

    # ====================================
    # TRADES TABLE - Optimistic Locking
    # ====================================

    trade_columns = {col["name"] for col in inspector.get_columns("trades")}

    # Add version column for optimistic locking
    if "version" not in trade_columns:
        op.add_column(
            "trades",
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )

    # ====================================
    # POSITIONS TABLE - Optimistic Locking
    # ====================================

    position_columns = {col["name"] for col in inspector.get_columns("positions")}

    # Add version column for optimistic locking
    if "version" not in position_columns:
        op.add_column(
            "positions",
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )


def downgrade() -> None:
    """Downgrade database schema.

    Removes columns added for Clean Architecture.
    Note: This is a destructive operation - only use in development.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    # ====================================
    # POSITIONS TABLE
    # ====================================
    position_columns = {col["name"] for col in inspector.get_columns("positions")}
    if "version" in position_columns:
        op.drop_column("positions", "version")

    # ====================================
    # TRADES TABLE
    # ====================================
    trade_columns = {col["name"] for col in inspector.get_columns("trades")}
    if "version" in trade_columns:
        op.drop_column("trades", "version")

    # ====================================
    # WHALE_SIGNALS TABLE - Drop indexes first
    # ====================================
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("whale_signals")}

    if "ix_signals_whale_status" in existing_indexes:
        op.drop_index("ix_signals_whale_status", table_name="whale_signals")

    if "ix_signals_queue" in existing_indexes:
        op.drop_index("ix_signals_queue", table_name="whale_signals")

    # Drop columns
    signal_columns = {col["name"] for col in inspector.get_columns("whale_signals")}

    columns_to_drop = [
        "trades_executed",
        "metadata_json",
        "leverage",
        "quantity",
        "entry_price",
        "symbol",
        "side",
        "trade_type",
        "source",
        "priority",
    ]

    for col in columns_to_drop:
        if col in signal_columns:
            # Drop index if exists
            if f"ix_whale_signals_{col}" in existing_indexes:
                op.drop_index(f"ix_whale_signals_{col}", table_name="whale_signals")
            op.drop_column("whale_signals", col)
