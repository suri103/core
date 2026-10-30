"""insurance_claims code columns: text -> json

Revision ID: b1c2d3e4f5a6
Revises: a3d2b4c5e6f0
Create Date: 2026-09-17 13:00:00

WHY
---
``insurance_claims.procedure_codes`` and ``diagnosis_codes`` were created as
``sa.Text()`` by the baseline migration while the model declares them as JSON and
the application treats them as lists:

    procedure_codes=[pc.model_dump(mode='json') for pc in ...]

PostgreSQL rejects a JSON parameter against a text column with
DatatypeMismatchError, so every claim insert failed. SQLite stored it without
complaint, which is why the test suite never noticed.

The model is the authority here, not the baseline migration. Claims pass real
lists at the ORM layer, the test suite constructs them that way, and the column's
own comment documents a structured array. The alternative - making the model
Text - was tried and broke four tests, which is the evidence that settled it.

DATA SAFETY
-----------
The existing text values are JSON documents written by ``json.dumps`` (see
edi.py and the pre-authorization route), so they cast cleanly. NULLIF guards the
empty string. On a database with no rows this is a metadata-only change.

Note for a follow-up, not fixed here: those two call sites still ``json.dumps``
before assigning, which stores a JSON *string* rather than an array. The reader
at insurance.py:~690 tolerates both shapes, which is how the discrepancy
survived. They should be changed to pass the value directly now that the column
is JSON.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a3d2b4c5e6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("procedure_codes", "diagnosis_codes")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for column in _COLUMNS:
            op.execute(
                f"ALTER TABLE insurance_claims ALTER COLUMN {column} "
                f"TYPE JSON USING NULLIF({column}, '')::json"
            )
    else:
        # SQLite cannot alter a column in place; batch mode recreates the table.
        with op.batch_alter_table("insurance_claims") as batch_op:
            for column in _COLUMNS:
                batch_op.alter_column(
                    column, existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=True
                )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for column in _COLUMNS:
            op.execute(
                f"ALTER TABLE insurance_claims ALTER COLUMN {column} "
                f"TYPE TEXT USING {column}::text"
            )
    else:
        with op.batch_alter_table("insurance_claims") as batch_op:
            for column in _COLUMNS:
                batch_op.alter_column(
                    column, existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=True
                )
