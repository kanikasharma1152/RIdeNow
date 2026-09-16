"""add distance to rides

Revision ID: ad8c8054e7a5
Revises: 66ae7fd03c39
Create Date: 2026-09-04 20:34:49.050151

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad8c8054e7a5'
down_revision: Union[str, Sequence[str], None] = '66ae7fd03c39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Step 1: Add column temporarily as nullable
    op.add_column(
        'rides',
        sa.Column(
            'distance_km',
            sa.Numeric(precision=10, scale=2),
            nullable=True
        )
    )

    # Step 2: Give existing rides a default distance
    op.execute(
        "UPDATE rides SET distance_km = 0 WHERE distance_km IS NULL"
    )

    # Step 3: Make column NOT NULL
    op.alter_column(
        'rides',
        'distance_km',
        existing_type=sa.Numeric(precision=10, scale=2),
        nullable=False
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column('rides', 'distance_km')