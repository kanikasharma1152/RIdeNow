"""add_user_oauth_fields

Revision ID: c1a9f0e81b22
Revises: fd0a5e00e8ee
Create Date: 2026-09-21 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a9f0e81b22'
down_revision: Union[str, Sequence[str], None] = 'fd0a5e00e8ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make phone and password_hash nullable for OAuth accounts
    op.alter_column('users', 'phone', existing_type=sa.String(length=20), nullable=True)
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=True)

    # Add OAuth identity and preference columns
    op.add_column('users', sa.Column('oauth_provider', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('oauth_sub', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=512), nullable=True))
    op.add_column('users', sa.Column('preferred_language', sa.String(length=10), nullable=False, server_default='en'))
    op.add_column('users', sa.Column('onboarding_complete', sa.Boolean(), nullable=False, server_default='false'))

    # Indexes
    op.create_index('ix_users_oauth_provider', 'users', ['oauth_provider'], unique=False)
    op.create_index('ix_users_oauth_sub', 'users', ['oauth_sub'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_oauth_sub', table_name='users')
    op.drop_index('ix_users_oauth_provider', table_name='users')
    op.drop_column('users', 'onboarding_complete')
    op.drop_column('users', 'preferred_language')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'oauth_sub')
    op.drop_column('users', 'oauth_provider')
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=False)
    op.alter_column('users', 'phone', existing_type=sa.String(length=20), nullable=False)
