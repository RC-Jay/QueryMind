"""conversation summary columns

Adds `summary` and `summary_checkpoint` to the conversations table to support
LLM-based history summarisation. Both columns are nullable — existing rows are
unaffected; the summary is generated lazily on the first turn where the
conversation exceeds the history_turns window.

Revision ID: c4f8a2e91d03
Revises: eae69e3ea00b
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f8a2e91d03'
down_revision: Union[str, None] = 'eae69e3ea00b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('conversations', sa.Column('summary_checkpoint', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'summary_checkpoint')
    op.drop_column('conversations', 'summary')
