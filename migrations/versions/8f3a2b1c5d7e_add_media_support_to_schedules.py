"""add media support to schedules

Revision ID: 8f3a2b1c5d7e
Revises: 1d4fa529ddea
Create Date: 2026-03-31 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f3a2b1c5d7e'
down_revision = '1d4fa529ddea'
branch_labels = None
depends_on = None


def upgrade():
    # Add media columns to schedules table
    op.add_column('schedules', sa.Column('media_type', sa.String(), nullable=True))
    op.add_column('schedules', sa.Column('media_file_id', sa.String(), nullable=True))
    op.add_column('schedules', sa.Column('caption', sa.Text(), nullable=True))
    
    # Make message column nullable since we can have media-only messages
    op.alter_column('schedules', 'message',
                    existing_type=sa.Text(),
                    nullable=True)


def downgrade():
    op.alter_column('schedules', 'message',
                    existing_type=sa.Text(),
                    nullable=False)
    op.drop_column('schedules', 'caption')
    op.drop_column('schedules', 'media_file_id')
    op.drop_column('schedules', 'media_type')
