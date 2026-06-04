"""business_config json columns

Revision ID: eae69e3ea00b
Revises: b2da1da41f46
Create Date: 2026-06-04 19:19:54.247671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eae69e3ea00b'
down_revision: Union[str, None] = 'b2da1da41f46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_JSON_COLUMNS = ("business_rules", "table_descriptions", "kpi_definitions", "starter_questions")


def upgrade() -> None:
    # Existing values are already valid JSON text (stored via json.dumps), so the
    # USING cast converts them cleanly to the json type.
    for col in _JSON_COLUMNS:
        op.alter_column(
            "business_config", col,
            existing_type=sa.TEXT(), type_=sa.JSON(),
            existing_nullable=False, postgresql_using=f"{col}::json",
        )


def downgrade() -> None:
    for col in _JSON_COLUMNS:
        op.alter_column(
            "business_config", col,
            existing_type=sa.JSON(), type_=sa.TEXT(),
            existing_nullable=False, postgresql_using=f"{col}::text",
        )
