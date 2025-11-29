
"""add scheduler fields and fix admin_id

Revision ID: adf7e9709e89
Revises:  3565a41b8354
Create Date: 2025-04-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'adf7e9709e89'
down_revision = '3565a41b8354'
branch_labels = None
depends_on = None


def upgrade():
    # === 1. Change admin_id: INTEGER → BIGINT ===
    op.alter_column(
        'schedules',
        'admin_id',
        existing_type=sa.INTEGER(),
        type_=sa.BIGINT(),
        postgresql_using='admin_id::bigint',
        nullable=False
    )

    # === 2. Add new scheduler columns ===
    op.add_column('schedules', sa.Column('cron_expr', sa.Text(), nullable=True))
    op.add_column('schedules', sa.Column('next_run', sa.DateTime(), nullable=True))
    op.add_column('schedules', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Optional: Add index on next_run for performance
    op.create_index('ix_schedules_next_run', 'schedules', ['next_run'])


def downgrade():
    # === Reverse: Drop index ===
    op.drop_index('ix_schedules_next_run', table_name='schedules')

    # === Reverse: Drop columns ===
    op.drop_column('schedules', 'is_active')
    op.drop_column('schedules', 'next_run')
    op.drop_column('schedules', 'cron_expr')

    # === Reverse: Change admin_id back to INTEGER ===
    op.alter_column(
        'schedules',
        'admin_id',
        existing_type=sa.BIGINT(),
        type_=sa.INTEGER(),
        postgresql_using='admin_id::integer',
        nullable=False
    )