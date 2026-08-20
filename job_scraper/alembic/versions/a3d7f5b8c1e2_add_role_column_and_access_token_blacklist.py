"""add role column and access token blacklist table

Revision ID: a3d7f5b8c1e2
Revises: cead0912f46d
Create Date: 2026-08-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3d7f5b8c1e2'
down_revision: Union[str, Sequence[str], None] = 'cead0912f46d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(20), nullable=False, server_default='user'))
    op.add_column('refresh_tokens', sa.Column('access_token_jti', sa.String(255), nullable=True))

    op.create_table('access_token_blacklist',
        sa.Column('blacklist_id', sa.String(36), nullable=False),
        sa.Column('jti', sa.String(255), nullable=False),
        sa.Column('token', sa.String(500), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('blacklist_id')
    )
    op.create_index(op.f('ix_access_token_blacklist_jti'), 'access_token_blacklist', ['jti'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_access_token_blacklist_jti'), table_name='access_token_blacklist')
    op.drop_table('access_token_blacklist')
    op.drop_column('refresh_tokens', 'access_token_jti')
    op.drop_column('users', 'role')
