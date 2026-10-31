"""CVs as structured data, generated documents, and Stripe webhook events

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table('cvs',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('created_at', UTC, nullable=False),
        sa.Column('updated_at', UTC, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )
    op.create_table('documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('filename', sa.String(length=200), nullable=False),
        sa.Column('storage_key', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('pages', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=False),
        sa.Column('requested_at', UTC, nullable=False),
        sa.Column('finished_at', UTC, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_documents_user', 'documents', ['user_id', 'requested_at'], unique=False)
    op.create_table('billing_events',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('livemode', sa.Boolean(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('received_at', UTC, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('billing_events')
    op.drop_index('ix_documents_user', table_name='documents')
    op.drop_table('documents')
    op.drop_table('cvs')
