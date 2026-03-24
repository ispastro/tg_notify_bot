"""add_user_profile_fields

Revision ID: 1d4fa529ddea
Revises: 6463d818d932
Create Date: 2026-03-24 22:24:20.997671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d4fa529ddea'
down_revision: Union[str, Sequence[str], None] = '6463d818d932'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add full_name column
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))
    # Add gender column
    op.add_column('users', sa.Column('gender', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns in reverse order
    op.drop_column('users', 'gender')
    op.drop_column('users', 'full_name')
