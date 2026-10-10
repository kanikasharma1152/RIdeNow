"""add_safety_and_trusted_contacts

Revision ID: e4b819f07a33
Revises: c1a9f0e81b22
Create Date: 2026-09-22 19:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b819f07a33'
down_revision: Union[str, Sequence[str], None] = 'c1a9f0e81b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. safety_events table
    op.create_table(
        'safety_events',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ride_id', sa.Integer(), sa.ForeignKey('rides.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('drivers.id'), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='INFO'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_safety_events_id', 'safety_events', ['id'], unique=False)
    op.create_index('ix_safety_events_ride_id', 'safety_events', ['ride_id'], unique=False)
    op.create_index('ix_safety_events_user_id', 'safety_events', ['user_id'], unique=False)
    op.create_index('ix_safety_events_driver_id', 'safety_events', ['driver_id'], unique=False)
    op.create_index('ix_safety_events_event_type', 'safety_events', ['event_type'], unique=False)
    op.create_index('ix_safety_events_created_at', 'safety_events', ['created_at'], unique=False)

    # 2. trusted_contacts table
    op.create_table(
        'trusted_contacts',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('relationship', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_trusted_contacts_id', 'trusted_contacts', ['id'], unique=False)
    op.create_index('ix_trusted_contacts_user_id', 'trusted_contacts', ['user_id'], unique=False)

    # 3. ride_share_tokens table
    op.create_table(
        'ride_share_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ride_id', sa.Integer(), sa.ForeignKey('rides.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ride_share_tokens_id', 'ride_share_tokens', ['id'], unique=False)
    op.create_index('ix_ride_share_tokens_ride_id', 'ride_share_tokens', ['ride_id'], unique=False)
    op.create_index('ix_ride_share_tokens_user_id', 'ride_share_tokens', ['user_id'], unique=False)
    op.create_index('ix_ride_share_tokens_token', 'ride_share_tokens', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_ride_share_tokens_token', table_name='ride_share_tokens')
    op.drop_index('ix_ride_share_tokens_user_id', table_name='ride_share_tokens')
    op.drop_index('ix_ride_share_tokens_ride_id', table_name='ride_share_tokens')
    op.drop_index('ix_ride_share_tokens_id', table_name='ride_share_tokens')
    op.drop_table('ride_share_tokens')

    op.drop_index('ix_trusted_contacts_user_id', table_name='trusted_contacts')
    op.drop_index('ix_trusted_contacts_id', table_name='trusted_contacts')
    op.drop_table('trusted_contacts')

    op.drop_index('ix_safety_events_created_at', table_name='safety_events')
    op.drop_index('ix_safety_events_event_type', table_name='safety_events')
    op.drop_index('ix_safety_events_driver_id', table_name='safety_events')
    op.drop_index('ix_safety_events_user_id', table_name='safety_events')
    op.drop_index('ix_safety_events_ride_id', table_name='safety_events')
    op.drop_index('ix_safety_events_id', table_name='safety_events')
    op.drop_table('safety_events')
