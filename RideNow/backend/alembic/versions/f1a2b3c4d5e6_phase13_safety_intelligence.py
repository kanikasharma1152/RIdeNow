"""phase13_safety_intelligence

Revision ID: f1a2b3c4d5e6
Revises: e8f9a1b2c3d4
Create Date: 2026-10-01 08:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e8f9a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Alter safety_events.ride_id to be nullable
    op.alter_column('safety_events', 'ride_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    # 2. Add description column to safety_events
    op.add_column('safety_events', sa.Column('description', sa.String(length=500), nullable=True))

    # 3. Add resolved_by column to safety_events
    op.add_column('safety_events', sa.Column('resolved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))

    # 4. Add updated_at column to safety_events
    op.add_column('safety_events', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # 5. Add updated_at column to trusted_contacts
    op.add_column('trusted_contacts', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_column('trusted_contacts', 'updated_at')
    op.drop_column('safety_events', 'updated_at')
    op.drop_column('safety_events', 'resolved_by')
    op.drop_column('safety_events', 'description')
    op.alter_column('safety_events', 'ride_id',
               existing_type=sa.INTEGER(),
               nullable=False)
