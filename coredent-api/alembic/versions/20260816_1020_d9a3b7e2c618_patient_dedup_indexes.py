"""unique per-practice patient contact indexes (dedup race guard)

Revision ID: d9a3b7e2c618
Revises: c8f1a6d3b527
Create Date: 2026-08-16 10:20:00

B8 REWRITE — fail-closed preflight, zero automatic data changes.

The create/update endpoints check duplicates via the HMAC search-index
columns, but check-then-insert races let concurrent creates both pass.
These unique partial indexes make the database the final arbiter over
non-inactive rows.

An earlier revision of this migration automatically marked duplicate rows
INACTIVE to force uniqueness. That destroyed information irreversibly
(downgrade could not restore statuses), could pick an older inactive record
as the survivor, and produced incoherent results across separate email and
phone passes. It is replaced by a fail-closed preflight:

1. NULL status rows are rejected — SQL NULL semantics would otherwise omit
   those rows from uniqueness protection entirely.
2. Rows whose encrypted email/phone exists but whose legacy HMAC index is
   NULL are rejected until ``scripts/backfill_patient_search_indexes.py``
   has completed — otherwise a later backfill can collide mid-run.
3. Duplicate HMAC groups within the covered predicate abort the migration,
   reporting only non-PHI counts and opaque hash fragments so an operator
   can perform an explicit, audited merge/adjudication.

No patient status is modified by this migration under any circumstance.

NOTE: enum columns store member NAMES (e.g. 'ACTIVE'), so the raw SQL
below uses the uppercase label form.

OFFLINE (``--sql``) MODE: the fail-closed preflight needs a live connection,
which offline rendering lacks. The generated script carries an explicit
``DO ... RAISE WARNING`` block listing the three skipped checks and then
emits the index DDL statically; on a fresh database (no patients) the
indexes simply build.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d9a3b7e2c618"
down_revision: str | None = "c8f1a6d3b527"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COVERED = "(status IS NOT NULL AND status <> 'INACTIVE')"


def _inspect_safe(bind):
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def _abort(message: str) -> None:
    raise RuntimeError(
        "Refusing to apply migration d9a3b7e2c618: " + message
        + "\n\nResolve the reported condition (operator adjudication for "
        "duplicates, backfill for missing indexes) and re-run the "
        "migration. No rows were modified."
    )


def _preflight() -> None:
    conn = op.get_bind()

    # 1. Non-null status policy: NULL-status rows are invisible to the
    #    partial-index predicate and therefore unprotected.
    null_status = conn.execute(
        sa.text("SELECT COUNT(*) FROM patients WHERE status IS NULL")
    ).scalar_one()
    if null_status:
        _abort(
            f"{null_status} patient row(s) have a NULL status. Repair the "
            "statuses first; NULL rows would bypass uniqueness protection."
        )

    # 2. Key-aware backfill completeness: an encrypted contact without its
    #    HMAC index means historical rows are not yet searchable/dedupable.
    unindexed_email = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM patients "
            "WHERE search_index_email IS NULL AND email IS NOT NULL"
        )
    ).scalar_one()
    unindexed_phone = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM patients "
            "WHERE search_index_phone IS NULL AND phone IS NOT NULL"
        )
    ).scalar_one()
    if unindexed_email or unindexed_phone:
        _abort(
            f"Search-index backfill incomplete: {unindexed_email} row(s) with "
            f"an email but no search_index_email, {unindexed_phone} row(s) "
            "with a phone but no search_index_phone. Run "
            "`python scripts/backfill_patient_search_indexes.py` against this "
            "database first."
        )

    # 3. Unresolved duplicates fail closed. Only counts and opaque hash
    #    fragments are emitted — never plaintext PHI.
    for column in ("search_index_email", "search_index_phone"):
        groups = conn.execute(
            sa.text(
                f"SELECT practice_id, {column}, COUNT(*) AS row_count "
                f"FROM patients WHERE {column} IS NOT NULL AND {_COVERED} "
                f"GROUP BY practice_id, {column} HAVING COUNT(*) > 1 "
                f"ORDER BY row_count DESC"
            )
        ).fetchall()
        if groups:
            total_extra = sum(int(row.row_count) - 1 for row in groups)
            sample = ", ".join(
                f"practice={str(row.practice_id)[:8]}… hmac={str(row[1])[:12]}… "
                f"x{row.row_count}"
                for row in groups[:10]
            )
            if len(groups) > 10:
                sample += f", … and {len(groups) - 10} more group(s)"
            _abort(
                f"{len(groups)} duplicate {column} group(s) covering "
                f"{total_extra} extra row(s) among active patients: {sample}. "
                "Perform an explicit operator merge/adjudication before "
                "enforcing uniqueness."
            )


def _create_indexes() -> None:
    active_email = sa.text(f"search_index_email IS NOT NULL AND {_COVERED}")
    active_phone = sa.text(f"search_index_phone IS NOT NULL AND {_COVERED}")
    op.create_index(
        "uq_patient_practice_email_idx",
        "patients",
        ["practice_id", "search_index_email"],
        unique=True,
        postgresql_where=active_email,
        sqlite_where=active_email,
    )
    op.create_index(
        "uq_patient_practice_phone_idx",
        "patients",
        ["practice_id", "search_index_phone"],
        unique=True,
        postgresql_where=active_phone,
        sqlite_where=active_phone,
    )


def upgrade() -> None:
    if _inspect_safe(op.get_bind()) is None:
        # Offline (--sql): the fail-closed preflight needs a live connection,
        # so embed the skipped checks as a warning in the generated script.
        op.execute(
            "DO $$ BEGIN RAISE WARNING 'd9a3b7e2c618: this script was "
            "rendered offline, so the fail-closed preflight did NOT run. "
            "If this database has patient records, verify before applying: "
            "(1) no patients.status IS NULL, (2) search-index backfill is "
            "complete (scripts/backfill_patient_search_indexes.py), "
            "(3) no duplicate search_index_email/search_index_phone groups "
            "among active patients. On a fresh database this warning is "
            "informational only.'; END $$"
        )
        _create_indexes()
        return

    _preflight()
    _create_indexes()


def downgrade() -> None:
    op.drop_index("uq_patient_practice_phone_idx", table_name="patients")
    op.drop_index("uq_patient_practice_email_idx", table_name="patients")
