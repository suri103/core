"""claim submission idempotency + submitting/failed claim statuses

Revision ID: f6b2d4e8a391
Revises: e5a1c3f7d284
Create Date: 2026-08-25 09:30:00

WHY (audit finding H-03)
------------------------
``submit_claim`` POSTed to the clearinghouse and only then committed the local
``InsuranceClaim``. If that commit failed, a retry submitted the same claim to
the payer a second time -- duplicate billing. The only guard was "any claim for
this patient in the last five minutes", which simultaneously blocked
legitimate same-day second claims and allowed duplicates after five minutes.

This revision adds the durable idempotency key the endpoint now reserves and
commits *before* the external call, plus the two claim statuses that make the
in-flight and failed states representable:

  SUBMITTING        - reserved locally, clearinghouse outcome unknown
  SUBMISSION_FAILED - the submission attempt itself failed (distinct from
                      DENIED, which is a payer adjudication result)

Idempotent: reflection-guarded, safe to re-run.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "f6b2d4e8a391"
down_revision: str | None = "e5a1c3f7d284"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_CLAIM_STATUSES = ("SUBMITTING", "SUBMISSION_FAILED")


def _inspector():
    try:
        return sa.inspect(op.get_bind())
    except sa.exc.NoInspectionAvailable:
        # Offline (--sql) rendering uses a mock connection.
        return None


def _columns(table: str) -> set[str]:
    insp = _inspector()
    if insp is None:
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(table: str) -> set[str]:
    insp = _inspector()
    if insp is None:
        return set()
    names = {ix["name"] for ix in insp.get_indexes(table)}
    names.update(
        uc["name"] for uc in insp.get_unique_constraints(table) if uc.get("name")
    )
    return names


def _add_enum_members(members: Sequence[str]) -> None:
    """Best-effort Postgres enum extension (no-op on SQLite/other dialects)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for member in members:
        try:
            op.execute(f"ALTER TYPE claimstatus ADD VALUE IF NOT EXISTS '{member}'")
        except Exception:
            # PG < 13 has no IF NOT EXISTS; tolerate duplicate-value errors.
            try:
                op.execute(f"ALTER TYPE claimstatus ADD VALUE '{member}'")
            except Exception:
                logger.info("claimstatus already contains %s", member)


def upgrade() -> None:
    if _inspector() is None:
        # Offline (--sql): none of these objects exist yet in a chain-built
        # database, and batch mode needs reflection, so emit the changeset
        # statically (M-04 convention).
        op.add_column(
            "insurance_claims",
            sa.Column("submission_idempotency_key", sa.String(length=255), nullable=True),
        )
        op.add_column(
            "insurance_claims",
            sa.Column(
                "submission_attempts", sa.Integer(), nullable=False, server_default="0"
            ),
        )
        op.add_column(
            "insurance_claims", sa.Column("submission_error", sa.Text(), nullable=True)
        )
        op.create_index(
            "ix_insurance_claims_submission_idempotency_key",
            "insurance_claims",
            ["submission_idempotency_key"],
        )
        op.create_index(
            "uq_practice_claim_idempotency_key",
            "insurance_claims",
            ["practice_id", "submission_idempotency_key"],
            unique=True,
        )
        for member in _NEW_CLAIM_STATUSES:
            op.execute(f"ALTER TYPE claimstatus ADD VALUE IF NOT EXISTS '{member}'")
        return

    existing = _columns("insurance_claims")

    with op.batch_alter_table("insurance_claims", schema=None) as batch_op:
        if "submission_idempotency_key" not in existing:
            batch_op.add_column(
                sa.Column("submission_idempotency_key", sa.String(length=255), nullable=True)
            )
        if "submission_attempts" not in existing:
            batch_op.add_column(
                sa.Column(
                    "submission_attempts",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if "submission_error" not in existing:
            batch_op.add_column(sa.Column("submission_error", sa.Text(), nullable=True))

    indexes = _index_names("insurance_claims")
    if "ix_insurance_claims_submission_idempotency_key" not in indexes:
        op.create_index(
            "ix_insurance_claims_submission_idempotency_key",
            "insurance_claims",
            ["submission_idempotency_key"],
        )
    # Unique per practice, not globally: two practices can legitimately derive
    # the same content hash for structurally identical claims.
    if "uq_practice_claim_idempotency_key" not in indexes:
        op.create_index(
            "uq_practice_claim_idempotency_key",
            "insurance_claims",
            ["practice_id", "submission_idempotency_key"],
            unique=True,
        )

    _add_enum_members(_NEW_CLAIM_STATUSES)


def downgrade() -> None:
    indexes = _index_names("insurance_claims")
    if "uq_practice_claim_idempotency_key" in indexes:
        op.drop_index("uq_practice_claim_idempotency_key", table_name="insurance_claims")
    if "ix_insurance_claims_submission_idempotency_key" in indexes:
        op.drop_index(
            "ix_insurance_claims_submission_idempotency_key",
            table_name="insurance_claims",
        )

    existing = _columns("insurance_claims")
    with op.batch_alter_table("insurance_claims", schema=None) as batch_op:
        if "submission_error" in existing:
            batch_op.drop_column("submission_error")
        if "submission_attempts" in existing:
            batch_op.drop_column("submission_attempts")
        if "submission_idempotency_key" in existing:
            batch_op.drop_column("submission_idempotency_key")

    # Enum members are intentionally not removed (Postgres cannot drop values).
