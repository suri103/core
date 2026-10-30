"""widen encrypted string columns to TEXT

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-17 18:30:00

WHY
---
``EncryptedString`` declared ``impl = String``, so ``EncryptedString(100)``
created a ``VARCHAR(100)``. But the column stores a Fernet envelope and its
length is a function of the ciphertext, not the plaintext: a four-character name
still produces a token well over 100 characters. PostgreSQL rejected the insert:

    StringDataRightTruncationError: value too long for type character varying(100)

SQLite does not enforce VARCHAR length, which is why every local run passed and
this only appeared once the suite ran against PostgreSQL.

The type is now ``Text`` so this cannot recur. This migration widens the columns
that already exist.

NOT A DATA REWRITE
------------------
varchar -> text is a binary-coercible cast in PostgreSQL, so this is a metadata
change; no rows are read, written or re-encrypted. Existing ciphertext is
untouched and stays valid.

SCOPE
-----
Enumerated from the models at run time, so it covers every EncryptedString
column rather than a hand-written list that would drift. SQLite is skipped
because it does not enforce the length and batch mode would rebuild every table
for no benefit.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _encrypted_string_columns() -> list[tuple[str, str]]:
    import app.models  # noqa: F401  - populates Base.metadata
    from app.core.base import Base
    from app.core.encryption import EncryptedString

    targets: list[tuple[str, str]] = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, EncryptedString):
                targets.append((table.name, column.name))
    return targets


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table, column in _encrypted_string_columns():
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE TEXT')


def downgrade() -> None:
    # Intentionally not reversible. The per-column lengths that existed before
    # are precisely what made these columns too small to hold their own
    # ciphertext, so restoring them would reintroduce the defect.
    pass
