"""Add whale status and polling fields

Revision ID: 001_whale_status
Revises: None
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_whale_status'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new enum types
    whale_type_enum = sa.Enum('CEX_TRADER', 'ONCHAIN_WALLET', name='whaletype')
    whale_type_enum.create(op.get_bind(), checkfirst=True)

    whale_data_status_enum = sa.Enum(
        'ACTIVE', 'SHARING_DISABLED', 'RATE_LIMITED', 'INACTIVE',
        name='whaledatastatus'
    )
    whale_data_status_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns to whales table
    op.add_column('whales', sa.Column(
        'whale_type',
        sa.Enum('CEX_TRADER', 'ONCHAIN_WALLET', name='whaletype'),
        nullable=False,
        server_default='CEX_TRADER'
    ))
    op.add_column('whales', sa.Column(
        'exchange',
        sa.String(20),
        nullable=True
    ))
    op.add_column('whales', sa.Column(
        'exchange_uid',
        sa.String(100),
        nullable=True
    ))
    op.add_column('whales', sa.Column(
        'data_status',
        sa.Enum('ACTIVE', 'SHARING_DISABLED', 'RATE_LIMITED', 'INACTIVE', name='whaledatastatus'),
        nullable=False,
        server_default='ACTIVE'
    ))
    op.add_column('whales', sa.Column(
        'consecutive_empty_checks',
        sa.Integer(),
        nullable=False,
        server_default='0'
    ))
    op.add_column('whales', sa.Column(
        'last_position_check',
        sa.DateTime(),
        nullable=True
    ))
    op.add_column('whales', sa.Column(
        'last_position_found',
        sa.DateTime(),
        nullable=True
    ))
    op.add_column('whales', sa.Column(
        'sharing_disabled_at',
        sa.DateTime(),
        nullable=True
    ))
    op.add_column('whales', sa.Column(
        'sharing_recheck_at',
        sa.DateTime(),
        nullable=True
    ))
    op.add_column('whales', sa.Column(
        'priority_score',
        sa.Integer(),
        nullable=False,
        server_default='50'
    ))
    op.add_column('whales', sa.Column(
        'polling_interval_seconds',
        sa.Integer(),
        nullable=False,
        server_default='60'
    ))

    # Modify wallet_address column to be longer (100 chars)
    op.alter_column('whales', 'wallet_address',
                    existing_type=sa.String(42),
                    type_=sa.String(100),
                    existing_nullable=False)

    # Create new indexes
    op.create_index(
        'ix_whales_data_status_priority',
        'whales',
        ['data_status', 'priority_score']
    )
    op.create_index(
        'ix_whales_exchange_status',
        'whales',
        ['exchange', 'data_status']
    )
    op.create_index(
        'ix_whales_recheck',
        'whales',
        ['sharing_recheck_at']
    )
    op.create_index(
        'ix_whales_exchange_uid',
        'whales',
        ['exchange_uid']
    )

    # Migrate existing data: extract exchange from wallet_address
    # Format is "exchange_uid" e.g. "binance_ABC123" or "bitget_XYZ789"
    op.execute("""
        UPDATE whales
        SET exchange = UPPER(SPLIT_PART(wallet_address, '_', 1)),
            exchange_uid = SUBSTRING(wallet_address FROM POSITION('_' IN wallet_address) + 1)
        WHERE wallet_address LIKE '%_%'
    """)

    # Set priority scores based on exchange
    # Bitget = 80 (always public), OKX = 70, Binance = 50
    op.execute("""
        UPDATE whales
        SET priority_score = CASE
            WHEN exchange = 'BITGET' THEN 80
            WHEN exchange = 'OKX' THEN 70
            WHEN exchange = 'BINANCE' THEN 50
            WHEN exchange = 'BYBIT' THEN 60
            ELSE 50
        END
        WHERE exchange IS NOT NULL
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_whales_exchange_uid', table_name='whales')
    op.drop_index('ix_whales_recheck', table_name='whales')
    op.drop_index('ix_whales_exchange_status', table_name='whales')
    op.drop_index('ix_whales_data_status_priority', table_name='whales')

    # Revert wallet_address column size
    op.alter_column('whales', 'wallet_address',
                    existing_type=sa.String(100),
                    type_=sa.String(42),
                    existing_nullable=False)

    # Drop columns
    op.drop_column('whales', 'polling_interval_seconds')
    op.drop_column('whales', 'priority_score')
    op.drop_column('whales', 'sharing_recheck_at')
    op.drop_column('whales', 'sharing_disabled_at')
    op.drop_column('whales', 'last_position_found')
    op.drop_column('whales', 'last_position_check')
    op.drop_column('whales', 'consecutive_empty_checks')
    op.drop_column('whales', 'data_status')
    op.drop_column('whales', 'exchange_uid')
    op.drop_column('whales', 'exchange')
    op.drop_column('whales', 'whale_type')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS whaledatastatus')
    op.execute('DROP TYPE IF EXISTS whaletype')
