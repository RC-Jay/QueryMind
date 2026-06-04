"""add outcome to audit_log

Revision ID: b2da1da41f46
Revises: db573742b279
Create Date: 2026-06-04 15:59:07.292031

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2da1da41f46'
down_revision: Union[str, None] = 'db573742b279'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_log', sa.Column('outcome', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_log', 'outcome')
