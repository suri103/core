"""tenant scoped unique constraints and carrier/referral fields

Revision ID: f2c5d7e8b930
Revises: e1b4c8d5a926
Create Date: 2026-08-18 12:00:00

- Add practice_id to insurance_carriers
- Compound unique constraints scoped to practice_id for:
  * insurance_claims (practice_id, claim_number)
  * invoices (practice_id, invoice_number)
  * lab_cases (practice_id, case_number)
  * procedure_library (practice_id, ada_code)
  * inventory_items (practice_id, sku)
- Add referral_number to referrals

MIGRATION HISTORY / WHY THIS IS WRITTEN DEFENSIVELY
---------------------------------------------------
The first version of this migration was unrunnable and, where it did run,
silently did nothing useful.  Two separate defects:

1. ``sa.ForeignKey("practices.id")`` was inline and unnamed.  Alembic's batch
   mode (used on SQLite) recreates the table and must emit the constraint as a
   standalone DDL element, which requires a name -- it raised
   ``ValueError: Constraint must have a name`` and aborted the whole chain.
   The FK is now explicitly named.

2. The legacy single-column uniqueness was dropped by *guessed* PostgreSQL
   constraint names (``insurance_claims_claim_number_key`` etc.) wrapped in
   ``except Exception: pass``.  Those names never existed: the baseline schema
   created uniqueness as a mix of unique *indexes*
   (``ix_insurance_claims_claim_number``, ``ix_invoices_invoice_number``,
   ``ix_procedure_library_ada_code``) and *unnamed* ``UniqueConstraint``s
   (``lab_cases.case_number``, ``inventory_items.sku``).  Every drop therefore
   failed and was swallowed, so the global unique survived and tenant-scoped
   uniqueness was never actually achieved -- two practices still could not
   share an invoice number.  Worse, on PostgreSQL a failed DDL statement
   aborts the surrounding transaction, so the ``pass`` could not recover it.

   Uniqueness is now located by *reflection* (whatever its name or form) and
   dropped only when it genuinely exists, so this migration is correct and
   idempotent on both PostgreSQL and SQLite.

3. Offline ``--sql`` rendering originally short-circuited with a warning and
   emitted NO DDL (Phase-1 findings C-03/M-04), so a production database built
   with ``alembic upgrade head --sql | psql`` silently kept the global
   uniqueness and lacked the new columns. ``upgrade()`` now emits static DDL
   in offline mode, frozen from the baseline schema — the exact state this
   revision runs against in a chain-built database.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "f2c5d7e8b930"
down_revision: str | None = "e1b4c8d5a926"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Gives reflected-but-unnamed UNIQUE constraints a deterministic name inside
# batch mode, which is the only way SQLite can drop them.
_NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
}


def _inspect_safe(bind):
    """Return the live inspector, or None when inspection is unavailable
    (offline ``--sql`` rendering uses a mock connection)."""
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def _table_exists(bind, table: str) -> bool:
    insp = _inspect_safe(bind)
    return insp is not None and insp.has_table(table)


def _columns(bind, table: str) -> set[str]:
    insp = _inspect_safe(bind)
    return set() if insp is None else {c['name'] for c in insp.get_columns(table)}


def _single_column_uniques(bind, table: str, column: str) -> tuple[list[str], list[str]]:
    """Reflect uniqueness covering exactly ``[column]``.

    Returns ``(unique_index_names, unique_constraint_names)``.  Compound
    uniqueness (e.g. an already-applied ``(practice_id, column)``) is
    deliberately ignored so re-running this migration is a no-op.

    NOTE on unnamed constraints: the baseline created some uniqueness as a bare
    ``sa.UniqueConstraint('sku')``, which SQLite reflects with ``name=None``.
    Such a constraint cannot be dropped by name -- but inside a batch block
    carrying ``_NAMING_CONVENTION`` it is re-emitted under the deterministic
    name ``uq_<table>_<column>``, so that is what we target.  Filtering these
    out (an earlier mistake) left the global unique in place on ``lab_cases``
    and ``inventory_items`` while reporting success.
    """
    insp = sa.inspect(bind)

    constraint_names = [
        uc.get("name") or f"uq_{table}_{column}"
        for uc in insp.get_unique_constraints(table)
        if list(uc.get("column_names") or []) == [column]
    ]

    # PostgreSQL backs every unique CONSTRAINT with an index of the SAME name,
    # so ``get_indexes()`` reports it as a unique index too.  Such an index
    # cannot be dropped with DROP INDEX -- Postgres raises
    # "cannot drop index <name> because constraint <name> on table <t>
    # requires it" -- and dropping the constraint removes the backing index
    # anyway.  Without this exclusion the drop_index loop below aborted the
    # whole migration transaction on PostgreSQL (SQLite does not expose
    # constraint-backing indexes, which is why the test suite never caught it).
    constraint_name_set = set(constraint_names)
    index_names = [
        ix["name"]
        for ix in insp.get_indexes(table)
        if ix.get("unique")
        and ix.get("name")
        and ix["name"] not in constraint_name_set
        and list(ix.get("column_names") or []) == [column]
    ]

    return index_names, constraint_names


def _has_unique(bind, table: str, columns: list[str]) -> bool:
    """True if uniqueness already covers exactly ``columns`` (index or constraint)."""
    insp = sa.inspect(bind)
    for ix in insp.get_indexes(table):
        if ix.get("unique") and list(ix.get("column_names") or []) == columns:
            return True
    for uc in insp.get_unique_constraints(table):
        if list(uc.get("column_names") or []) == columns:
            return True
    return False


def _rescope_unique(
    bind,
    table: str,
    legacy_column: str,
    new_constraint_name: str,
    new_columns: list[str],
) -> None:
    """Replace single-column uniqueness with practice-scoped compound uniqueness."""
    if not _table_exists(bind, table):
        return

    present = _columns(bind, table)
    if not set(new_columns).issubset(present):
        # Nothing sensible to do if the schema doesn't have the columns yet.
        return

    if _has_unique(bind, table, new_columns):
        # Already applied (idempotent re-run).
        return

    index_names, constraint_names = _single_column_uniques(bind, table, legacy_column)

    # Unique indexes drop cleanly outside batch mode on both engines.
    for name in index_names:
        op.drop_index(name, table_name=table)

    with op.batch_alter_table(
        table, schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        for name in constraint_names:
            batch_op.drop_constraint(name, type_="unique")
        batch_op.create_unique_constraint(new_constraint_name, new_columns)


# Frozen offline targets: exactly what baseline bb372b5f2d4a created, so the
# emitted script is correct for any database built by running this chain in
# order. Unnamed UNIQUE constraints in the baseline get PostgreSQL's automatic
# <table>_<column>_key name.
_RESCOPE_OFFLINE = [
    # (table, legacy_column, new_constraint_name, legacy_kind, legacy_name)
    ("insurance_claims", "claim_number", "uq_practice_claim_number",
     "index", "ix_insurance_claims_claim_number"),
    ("invoices", "invoice_number", "uq_practice_invoice_number",
     "index", "ix_invoices_invoice_number"),
    ("lab_cases", "case_number", "uq_practice_case_number",
     "constraint", "lab_cases_case_number_key"),
    ("procedure_library", "ada_code", "uq_practice_ada_code",
     "index", "ix_procedure_library_ada_code"),
    ("inventory_items", "sku", "uq_practice_inventory_sku",
     "constraint", "inventory_items_sku_key"),
]


def _upgrade_offline_static() -> None:
    # 1. insurance_carriers: add practice_id with the same named FK the
    #    online path creates.
    op.add_column(
        "insurance_carriers",
        sa.Column("practice_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_insurance_carriers_practice_id",
        "insurance_carriers",
        "practices",
        ["practice_id"],
        ["id"],
    )

    # 2-6. Replace global uniqueness with tenant-scoped compound uniqueness.
    for table_name, legacy_column, new_name, legacy_kind, legacy_name in (
        _RESCOPE_OFFLINE
    ):
        if legacy_kind == "index":
            op.drop_index(legacy_name, table_name=table_name)
        else:
            op.drop_constraint(legacy_name, table_name, type_="unique")
        op.create_unique_constraint(
            new_name, table_name, ["practice_id", legacy_column]
        )

    # 7. referrals: add referral_number, index it, and scope it unique.
    op.add_column(
        "referrals",
        sa.Column("referral_number", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_referrals_referral_number", "referrals", ["referral_number"]
    )
    op.create_unique_constraint(
        "uq_practice_referral_number",
        "referrals",
        ["practice_id", "referral_number"],
    )


def upgrade() -> None:
    bind = op.get_bind()
    if _inspect_safe(bind) is None:
        # Offline (--sql) rendering has no live database to reflect, but the
        # script it produces must still be complete (C-03/M-04). Emit the
        # static full-chain DDL for this revision.
        _upgrade_offline_static()
        return

    # 1. insurance_carriers: add practice_id.
    #    The FK is explicitly NAMED -- batch mode cannot emit an anonymous one.
    if _table_exists(bind, "insurance_carriers") and "practice_id" not in _columns(
        bind, "insurance_carriers"
    ):
        with op.batch_alter_table(
            "insurance_carriers", schema=None, naming_convention=_NAMING_CONVENTION
        ) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "practice_id",
                    sa.UUID(),
                    sa.ForeignKey(
                        "practices.id", name="fk_insurance_carriers_practice_id"
                    ),
                    nullable=True,
                )
            )

    # 2-6. Re-scope global uniqueness to the tenant.
    _rescope_unique(
        bind,
        "insurance_claims",
        "claim_number",
        "uq_practice_claim_number",
        ["practice_id", "claim_number"],
    )
    _rescope_unique(
        bind,
        "invoices",
        "invoice_number",
        "uq_practice_invoice_number",
        ["practice_id", "invoice_number"],
    )
    _rescope_unique(
        bind,
        "lab_cases",
        "case_number",
        "uq_practice_case_number",
        ["practice_id", "case_number"],
    )
    _rescope_unique(
        bind,
        "procedure_library",
        "ada_code",
        "uq_practice_ada_code",
        ["practice_id", "ada_code"],
    )
    _rescope_unique(
        bind,
        "inventory_items",
        "sku",
        "uq_practice_inventory_sku",
        ["practice_id", "sku"],
    )

    # 7. referrals: add referral_number.
    #    Backs the advisory-lock generator in endpoints/referrals.py; without a
    #    DB-level guarantee concurrent creates silently produced duplicates.
    if _table_exists(bind, "referrals"):
        referral_cols = _columns(bind, "referrals")
        if "referral_number" not in referral_cols:
            with op.batch_alter_table(
                "referrals", schema=None, naming_convention=_NAMING_CONVENTION
            ) as batch_op:
                batch_op.add_column(
                    sa.Column("referral_number", sa.String(length=50), nullable=True)
                )

        existing_indexes = {
            ix["name"] for ix in sa.inspect(bind).get_indexes("referrals")
        }
        if "ix_referrals_referral_number" not in existing_indexes:
            op.create_index(
                "ix_referrals_referral_number", "referrals", ["referral_number"]
            )

        if not _has_unique(bind, "referrals", ["practice_id", "referral_number"]):
            with op.batch_alter_table(
                "referrals", schema=None, naming_convention=_NAMING_CONVENTION
            ) as batch_op:
                batch_op.create_unique_constraint(
                    "uq_practice_referral_number", ["practice_id", "referral_number"]
                )


def _restore_global_unique(
    bind,
    table: str,
    compound_name: str,
    legacy_column: str,
) -> None:
    if not _table_exists(bind, table):
        return
    with op.batch_alter_table(
        table, schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        try:
            batch_op.drop_constraint(compound_name, type_="unique")
        except Exception:  # noqa: BLE001 - constraint may predate this revision
            return
    op.create_index(
        f"ix_{table}_{legacy_column}", table, [legacy_column], unique=True
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _inspect_safe(bind) is None:
        logger.warning(
            'f2c5d7e8b930: reflection unavailable in offline (--sql) '
            'downgrade; emitting no DDL (offline UPGRADE emits static DDL, '
            'but downgrade needs reflection to avoid dropping constraints '
            'that predate this revision)'
        )
        return

    if _table_exists(bind, "referrals"):
        with op.batch_alter_table(
            "referrals", schema=None, naming_convention=_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_constraint("uq_practice_referral_number", type_="unique")
        existing_indexes = {
            ix["name"] for ix in sa.inspect(bind).get_indexes("referrals")
        }
        if "ix_referrals_referral_number" in existing_indexes:
            op.drop_index("ix_referrals_referral_number", table_name="referrals")
        with op.batch_alter_table(
            "referrals", schema=None, naming_convention=_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_column("referral_number")

    _restore_global_unique(bind, "inventory_items", "uq_practice_inventory_sku", "sku")
    _restore_global_unique(bind, "procedure_library", "uq_practice_ada_code", "ada_code")
    _restore_global_unique(bind, "lab_cases", "uq_practice_case_number", "case_number")
    _restore_global_unique(bind, "invoices", "uq_practice_invoice_number", "invoice_number")
    _restore_global_unique(
        bind, "insurance_claims", "uq_practice_claim_number", "claim_number"
    )

    if _table_exists(bind, "insurance_carriers") and "practice_id" in _columns(
        bind, "insurance_carriers"
    ):
        with op.batch_alter_table(
            "insurance_carriers", schema=None, naming_convention=_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_column("practice_id")
