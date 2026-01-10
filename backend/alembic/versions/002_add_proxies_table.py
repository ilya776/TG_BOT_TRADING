"""Add proxies table for proxy pool

Revision ID: 002_proxies
Revises: 001_whale_status
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_proxies'
down_revision: Union[str, None] = '001_whale_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create proxies table
    op.create_table(
        'proxies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(10), nullable=False, server_default='http'),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('password_encrypted', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('rate_limited_until', sa.DateTime(), nullable=True),
        sa.Column('exchange_limits', sa.Text(), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        sa.Column('last_failure_reason', sa.String(500), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('is_residential', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_proxies_status', 'proxies', ['status'])
    op.create_index('ix_proxies_host_port', 'proxies', ['host', 'port'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_proxies_host_port', table_name='proxies')
    op.drop_index('ix_proxies_status', table_name='proxies')
    op.drop_table('proxies')
