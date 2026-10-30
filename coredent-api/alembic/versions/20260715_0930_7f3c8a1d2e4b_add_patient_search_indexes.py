"""add patient encrypted-field search indexes

Revision ID: 7f3c8a1d2e4b
Revises: 68d3f2d3ac00
Create Date: 2026-07-15 09:30:00

The ORM has long expected these columns, but the migration history never
created them. They remain nullable until the separate key-aware backfill has
run because Alembic cannot safely decrypt PHI without the deployment keyring.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "7f3c8a1d2e4b"
down_revision: str | None = "68d3f2d3ac00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = (
    "search_index_email",
    "search_index_phone",
    "search_index_last_name",
)


def _inspect_patients(bind) -> tuple[set, set]:
    """Return ``(existing_columns, existing_indexes)`` for ``patients``.

    Online (real connection) the inspector answers against the live
    catalog.  Offline rendering (``alembic upgrade --sql``) provides a mock
    connection that cannot be inspected, so fall back to empty sets and let
    the callers emit idempotent DDL.
    """
    try:
        inspector = sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return set(), set()
    return (
        {c["name"] for c in inspector.get_columns("patients")},
        {i["name"] for i in inspector.get_indexes("patients")},
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns, existing_indexes = _inspect_patients(bind)
    offline = not existing_columns and not existing_indexes

    for column_name in _COLUMNS:
        if column_name not in existing_columns:
            if offline:
                # Idempotent DDL valid on PostgreSQL (deployment target)
                # when no live catalog is available to check first.
                op.execute(
                    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS "
                    f"{column_name} VARCHAR(64)"
                )
            else:
                op.add_column(
                    "patients",
                    sa.Column(column_name, sa.String(length=64), nullable=True),
                )

    for column_name in _COLUMNS:
        index_name = f"ix_patients_{column_name}"
        if index_name not in existing_indexes:
            if offline:
                op.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON patients ({column_name})"
                )
            else:
                op.create_index(
                    index_name,
                    "patients",
                    [column_name],
                    unique=False,
                )


def downgrade() -> None:
    bind = op.get_bind()
    existing_columns, existing_indexes = _inspect_patients(bind)
    # Offline mode cannot know which objects exist; emit nothing.
    if not existing_columns and not existing_indexes:
        return

    for column_name in reversed(_COLUMNS):
        index_name = f"ix_patients_{column_name}"
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="patients")

    for column_name in reversed(_COLUMNS):
        if column_name in existing_columns:
            op.drop_column("patients", column_name)