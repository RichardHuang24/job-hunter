"""AI scoring: a score per user job, and an AI usage ledger

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table('job_scores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_job_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('overall', sa.Integer(), nullable=True),
        sa.Column('band', sa.String(length=32), nullable=False),
        sa.Column('dimensions', sa.JSON(), nullable=False),
        sa.Column('analysis', sa.JSON(), nullable=False),
        sa.Column('inputs_hash', sa.String(length=32), nullable=False),
        sa.Column('error', sa.Text(), nullable=False),
        sa.Column('error_code', sa.String(length=16), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('requested_at', UTC, nullable=False),
        sa.Column('scored_at', UTC, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_job_id'], ['user_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_job_id'),
    )
    op.create_index('ix_job_scores_user_id', 'job_scores', ['user_id'], unique=False)

    op.create_table('ai_usage',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('cache_read_tokens', sa.Integer(), nullable=False),
        sa.Column('cache_write_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('created_at', UTC, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_usage_user_month', 'ai_usage', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ai_usage_user_month', table_name='ai_usage')
    op.drop_table('ai_usage')
    op.drop_index('ix_job_scores_user_id', table_name='job_scores')
    op.drop_table('job_scores')
