"""Add position sizing strategy fields

Revision ID: 004_sizing_strategy
Revises: 003_signal_retry
Create Date: 2026-01-07

Adds new fields for smart position sizing:
- UserSettings: sizing_strategy, trade_size_percent, kelly_fraction
- UserWhaleFollow: sizing_strategy_override, kelly_fraction_override
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_sizing_strategy'
down_revision = '003_signal_retry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sizing strategy fields to user_settings
    op.add_column('user_settings', sa.Column(
        'sizing_strategy',
        sa.String(20),
        nullable=False,
        server_default='FIXED'
    ))
    op.add_column('user_settings', sa.Column(
        'trade_size_percent',
        sa.Numeric(5, 2),
        nullable=False,
        server_default='3.0'
    ))
    op.add_column('user_settings', sa.Column(
        'kelly_fraction',
        sa.Numeric(3, 2),
        nullable=False,
        server_default='0.50'
    ))

    # Add sizing strategy override fields to user_whale_follows
    op.add_column('user_whale_follows', sa.Column(
        'sizing_strategy_override',
        sa.String(20),
        nullable=True
    ))
    op.add_column('user_whale_follows', sa.Column(
        'kelly_fraction_override',
        sa.Numeric(3, 2),
        nullable=True
    ))


def downgrade() -> None:
    # Remove from user_whale_follows
    op.drop_column('user_whale_follows', 'kelly_fraction_override')
    op.drop_column('user_whale_follows', 'sizing_strategy_override')

    # Remove from user_settings
    op.drop_column('user_settings', 'kelly_fraction')
    op.drop_column('user_settings', 'trade_size_percent')
    op.drop_column('user_settings', 'sizing_strategy')
