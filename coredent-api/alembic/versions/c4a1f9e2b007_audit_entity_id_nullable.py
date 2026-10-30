"""audit_logs.entity_id nullable

Revision ID: c4a1f9e2b007
Revises: bb372b5f2d4a
Create Date: 2026-05-10

List/search audit events (e.g. "patient_list_viewed") log an action
without a specific entity. The entity_id column was NOT NULL which
caused all such inserts to fail. Make it nullable.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4a1f9e2b007"
down_revision: Union[str, None] = "bb372b5f2d4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column(
            "entity_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column(
            "entity_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
        )
