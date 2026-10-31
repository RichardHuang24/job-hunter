"""job search: jobs, saved searches, runs, and each user's view of a job

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30

Jobs are stored once (jobs, unique per source and source id) and shared;
what each user makes of one - role, level, deal-breaker checks, saved or
hidden - is in user_jobs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMPTY_LIST = sa.text("'[]'")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table('jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.String(length=200), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('company', sa.String(length=200), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('arrangement', sa.String(length=8), nullable=False),
        sa.Column('salary_min', sa.Integer(), nullable=True),
        sa.Column('salary_max', sa.Integer(), nullable=True),
        sa.Column('salary_currency', sa.String(length=3), nullable=False),
        sa.Column('salary_period', sa.String(length=8), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('posted_at', UTC, nullable=True),
        sa.Column('fingerprint', sa.String(length=40), nullable=False),
        sa.Column('first_seen_at', UTC, nullable=False),
        sa.Column('last_seen_at', UTC, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_id', name='uq_jobs_source_id'),
    )
    op.create_index('ix_jobs_fingerprint', 'jobs', ['fingerprint'], unique=False)

    op.create_table('saved_searches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('terms', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('locations', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('countries', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('include_remote', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('sources', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('daily', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('next_run_at', UTC, nullable=True),
        sa.Column('last_run_at', UTC, nullable=True),
        sa.Column('created_at', UTC, nullable=False),
        sa.Column('updated_at', UTC, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_saved_searches_user_id', 'saved_searches', ['user_id'], unique=False)
    op.create_index('ix_saved_searches_due', 'saved_searches', ['daily', 'next_run_at'], unique=False)

    op.create_table('search_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('search_id', sa.String(length=36), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('trigger', sa.String(length=16), nullable=False),
        sa.Column('counts', sa.JSON(), nullable=False),
        sa.Column('errors', sa.JSON(), nullable=False),
        sa.Column('created_at', UTC, nullable=False),
        sa.Column('started_at', UTC, nullable=True),
        sa.Column('finished_at', UTC, nullable=True),
        sa.ForeignKeyConstraint(['search_id'], ['saved_searches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_search_runs_user_id', 'search_runs', ['user_id'], unique=False)
    op.create_index('ix_search_runs_search_id', 'search_runs', ['search_id'], unique=False)

    op.create_table('user_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('state', sa.String(length=8), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=True),
        sa.Column('role', sa.String(length=80), nullable=False),
        sa.Column('level', sa.String(length=16), nullable=False),
        sa.Column('verdict', sa.String(length=8), nullable=False),
        sa.Column('checks', sa.JSON(), nullable=False),
        sa.Column('first_run_id', sa.String(length=36), nullable=True),
        sa.Column('first_seen_at', UTC, nullable=False),
        sa.Column('last_seen_at', UTC, nullable=False),
        sa.Column('updated_at', UTC, nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_id'], ['profile_targets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'job_id', name='uq_user_jobs_user_job'),
    )
    op.create_index('ix_user_jobs_job_id', 'user_jobs', ['job_id'], unique=False)
    op.create_index('ix_user_jobs_list', 'user_jobs', ['user_id', 'verdict', 'state'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_jobs_list', table_name='user_jobs')
    op.drop_index('ix_user_jobs_job_id', table_name='user_jobs')
    op.drop_table('user_jobs')
    op.drop_index('ix_search_runs_search_id', table_name='search_runs')
    op.drop_index('ix_search_runs_user_id', table_name='search_runs')
    op.drop_table('search_runs')
    op.drop_index('ix_saved_searches_due', table_name='saved_searches')
    op.drop_index('ix_saved_searches_user_id', table_name='saved_searches')
    op.drop_table('saved_searches')
    op.drop_index('ix_jobs_fingerprint', table_name='jobs')
    op.drop_table('jobs')
