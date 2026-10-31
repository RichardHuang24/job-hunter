"""Jobs: where a remote job is open, and when it expires or closes

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    with op.batch_alter_table('jobs') as batch:
        batch.add_column(sa.Column('countries', sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch.add_column(sa.Column('worldwide', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column('expires_at', UTC, nullable=True))
        batch.add_column(sa.Column('closed_at', UTC, nullable=True))
        batch.add_column(sa.Column('checked_at', UTC, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('jobs') as batch:
        batch.drop_column('checked_at')
        batch.drop_column('closed_at')
        batch.drop_column('expires_at')
        batch.drop_column('worldwide')
        batch.drop_column('countries')
