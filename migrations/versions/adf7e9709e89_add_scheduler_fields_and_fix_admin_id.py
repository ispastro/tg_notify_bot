"""add scheduler fields and fix admin_id

Revision ID: adf7e9709e89
Revises: 3565a41b8354
Create Date: 2025-10-31 22:10:09.381696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adf7e9709e89'
down_revision: Union[str, Sequence[str], None] = '3565a41b8354'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
