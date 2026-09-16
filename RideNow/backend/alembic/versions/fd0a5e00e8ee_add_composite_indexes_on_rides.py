"""add_composite_indexes_on_rides

Revision ID: fd0a5e00e8ee
Revises: 748da6335c13
Create Date: 2026-09-12 08:42:36.740824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd0a5e00e8ee'
down_revision: Union[str, Sequence[str], None] = '748da6335c13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for efficient paginated ride history queries."""
    # Composite index: (passenger_id, created_at) for paginated passenger history with date filters
    op.create_index(
        'ix_rides_passenger_id_created_at',
        'rides',
        ['passenger_id', 'created_at'],
        unique=False,
    )
    # Composite index: (driver_id, created_at) for paginated driver history with date filters
    op.create_index(
        'ix_rides_driver_id_created_at',
        'rides',
        ['driver_id', 'created_at'],
        unique=False,
    )
    # Index on completed_at for earnings queries by time window
    op.create_index(
        'ix_rides_completed_at',
        'rides',
        ['completed_at'],
        unique=False,
    )


def downgrade() -> None:
    """Drop composite indexes."""
    op.drop_index('ix_rides_completed_at', table_name='rides')
    op.drop_index('ix_rides_driver_id_created_at', table_name='rides')
    op.drop_index('ix_rides_passenger_id_created_at', table_name='rides')
