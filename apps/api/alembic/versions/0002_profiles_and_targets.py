"""profiles and target roles

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30

The full profile - experience, seniority, skills, languages, and the
deal-breakers (locations, work arrangements, work permits, salary) - and the
roles each user is after (profile_targets).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMPTY_LIST = sa.text("'[]'")
LIST_COLUMNS = ('seniority_levels', 'skills', 'languages', 'locations', 'work_arrangements', 'authorized_countries')


def upgrade() -> None:
    with op.batch_alter_table('profiles') as batch:
        batch.add_column(sa.Column('summary', sa.Text(), server_default='', nullable=False))
        batch.add_column(sa.Column('years_experience', sa.Integer(), nullable=True))
        for name in LIST_COLUMNS:
            batch.add_column(sa.Column(name, sa.JSON(), server_default=EMPTY_LIST, nullable=False))
        batch.add_column(sa.Column('open_to_sponsorship', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column('salary_min', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('salary_currency', sa.String(length=3), server_default='', nullable=False))
        batch.add_column(sa.Column('salary_period', sa.String(length=8), server_default='year', nullable=False))
        batch.add_column(sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table('profile_targets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=80), nullable=False),
        sa.Column('titles', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('exclude', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('search', sa.JSON(), server_default=EMPTY_LIST, nullable=False),
        sa.Column('preset_role', sa.String(length=130), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_profile_targets_user_id', 'profile_targets', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_profile_targets_user_id', table_name='profile_targets')
    op.drop_table('profile_targets')
    with op.batch_alter_table('profiles') as batch:
        for name in ('onboarded_at', 'salary_period', 'salary_currency', 'salary_min', 'open_to_sponsorship',
                     *reversed(LIST_COLUMNS), 'years_experience', 'summary'):
            batch.drop_column(name)
