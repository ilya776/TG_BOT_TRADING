"""Add retry_count to whale_signals for infinite loop prevention

Revision ID: 003_signal_retry
Revises: 002_proxies
Create Date: 2026-01-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_signal_retry'
down_revision: Union[str, None] = '002_proxies'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add retry_count column to whale_signals table
    # This tracks how many times a stuck PROCESSING signal has been recovered
    # to prevent infinite retry loops (max 3 retries before FAILED status)
    op.add_column(
        'whale_signals',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('whale_signals', 'retry_count')
