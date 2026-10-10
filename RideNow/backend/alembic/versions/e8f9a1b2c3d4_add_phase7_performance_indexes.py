"""add_phase7_performance_indexes

Revision ID: e8f9a1b2c3d4
Revises: e4b819f07a33
Create Date: 2026-09-23 21:18:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'e4b819f07a33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Index on rides(created_at) for analytics rolling 7-day trend & ML hotspot queries
    op.create_index(
        'ix_rides_created_at',
        'rides',
        ['created_at'],
        unique=False,
    )
    # 2. Index on drivers(is_online) for fleet radar and available driver lookups
    op.create_index(
        'ix_drivers_is_online',
        'drivers',
        ['is_online'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_drivers_is_online', table_name='drivers')
    op.drop_index('ix_rides_created_at', table_name='rides')
