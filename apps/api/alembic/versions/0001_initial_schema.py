"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-30

Auth.js's tables (users, accounts, sessions, verification_token - the schema
@auth/pg-adapter expects, with foreign keys and unique indexes added), the
users' profiles, and the background task queue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('emailVerified', sa.DateTime(timezone=True), nullable=True),
    sa.Column('image', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('verification_token',
    sa.Column('identifier', sa.Text(), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('expires', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('identifier', 'token')
    )
    op.create_table('accounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('userId', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=255), nullable=False),
    sa.Column('provider', sa.String(length=255), nullable=False),
    sa.Column('providerAccountId', sa.String(length=255), nullable=False),
    sa.Column('refresh_token', sa.Text(), nullable=True),
    sa.Column('access_token', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.BigInteger(), nullable=True),
    sa.Column('id_token', sa.Text(), nullable=True),
    sa.Column('scope', sa.Text(), nullable=True),
    sa.Column('session_state', sa.Text(), nullable=True),
    sa.Column('token_type', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['userId'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'providerAccountId', name='uq_accounts_provider_account')
    )
    op.create_index(op.f('ix_accounts_userId'), 'accounts', ['userId'], unique=False)
    op.create_table('profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('headline', sa.String(length=255), nullable=False),
    sa.Column('industry', sa.String(length=64), nullable=False),
    sa.Column('market', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('userId', sa.Integer(), nullable=False),
    sa.Column('expires', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sessionToken', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['userId'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sessionToken')
    )
    op.create_index(op.f('ix_sessions_userId'), 'sessions', ['userId'], unique=False)
    op.create_table('tasks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_by', sa.String(length=128), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tasks_claim', 'tasks', ['status', 'run_after'], unique=False)
    op.create_index(op.f('ix_tasks_user_id'), 'tasks', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tasks_user_id'), table_name='tasks')
    op.drop_index('ix_tasks_claim', table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_sessions_userId'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_table('profiles')
    op.drop_index(op.f('ix_accounts_userId'), table_name='accounts')
    op.drop_table('accounts')
    op.drop_table('verification_token')
    op.drop_table('users')
