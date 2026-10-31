"""Applications and their history

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table('applications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_job_id', sa.String(length=36), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('company', sa.String(length=200), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('applied_on', sa.Date(), nullable=True),
        sa.Column('next_step', sa.String(length=200), nullable=False),
        sa.Column('next_step_on', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('created_at', UTC, nullable=False),
        sa.Column('updated_at', UTC, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_job_id'], ['user_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_job_id', name='uq_applications_user_job'),
    )
    op.create_index('ix_applications_user', 'applications', ['user_id', 'status'], unique=False)
    op.create_table('application_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('application_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('at', UTC, nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_application_events_application_id', 'application_events', ['application_id'], unique=False)
    op.create_index('ix_application_events_user_id', 'application_events', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_application_events_user_id', table_name='application_events')
    op.drop_index('ix_application_events_application_id', table_name='application_events')
    op.drop_table('application_events')
    op.drop_index('ix_applications_user', table_name='applications')
    op.drop_table('applications')
