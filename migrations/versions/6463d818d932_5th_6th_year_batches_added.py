"""5th & 6th year batches added

Revision ID: 6463d818d932
Revises: 6d8cfb329b96
Create Date: 2025-11-29 00:46:13.972791

"""
from typing import Sequence, Union
from sqlalchemy.sql import table, column
from sqlalchemy import String
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6463d818d932'
down_revision: Union[str, Sequence[str], None] = '6d8cfb329b96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

batch_table = table('batches', column('name', String))

def upgrade():
    op.bulk_insert(
        batch_table,
        [
            {'name': '5th year'},
            {'name': '6th year'}
        ]
    )

def downgrade():
    op.execute("DELETE FROM batches WHERE name IN ('5th year', '6th year')")