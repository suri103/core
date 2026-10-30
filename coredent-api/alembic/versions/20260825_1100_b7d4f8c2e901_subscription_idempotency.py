"""make Stripe subscription identity durable and race-safe

Revision ID: b7d4f8c2e901
Revises: a1c9e5b73f60
Create Date: 2026-08-25 11:00:00

H-13: subscription creation and webhook handling used check-then-insert
without a database uniqueness guard. This migration refuses to guess when
legacy data already contains duplicate Stripe subscription IDs, then adds a
unique non-null identity index so concurrent writers converge on one row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4f8c2e901"
down_revision: str | None = "a1c9e5b73f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_subscriptions_stripe_subscription_id"


def _inspector():
    try:
        return sa.inspect(op.get_bind())
    except sa.exc.NoInspectionAvailable:
        # Offline (--sql) rendering uses a mock connection.
        return None


def _has_table(name: str) -> bool:
    insp = _inspector()
    return insp is not None and name in insp.get_table_names()


def _has_index(table: str, index: str) -> bool:
    if not _has_table(table):
        return False
    insp = _inspector()
    names = {ix["name"] for ix in insp.get_indexes(table)}
    names.update(
        uc["name"] for uc in insp.get_unique_constraints(table) if uc.get("name")
    )
    return index in names


def _abort_on_duplicate_stripe_ids() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT stripe_subscription_id, COUNT(*) AS row_count "
            "FROM subscriptions "
            "WHERE stripe_subscription_id IS NOT NULL "
            "GROUP BY stripe_subscription_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        sample = ", ".join(
            f"{row[0]} ({row[1]} rows)" for row in duplicates[:20]
        )
        raise RuntimeError(
            "Refusing to create the subscription idempotency index because "
            "duplicate Stripe subscription IDs already exist: "
            f"{sample}. Reconcile the rows explicitly, then rerun Alembic."
        )


def upgrade() -> None:
    if _inspector() is None:
        # Offline (--sql): the duplicate check needs a live connection. On a
        # chain-built database subscriptions always exists, so emit the
        # warning and the static partial unique index (M-04 convention).
        op.execute(
            "DO $$ BEGIN RAISE WARNING 'b7d4f8c2e901: this script was "
            "rendered offline, so the duplicate stripe_subscription_id check "
            "did NOT run. If this database has subscription history, "
            "reconcile duplicated Stripe subscription IDs before applying "
            "this script; the unique index below will fail on duplicates.'; "
            "END $$"
        )
        op.create_index(
            _INDEX_NAME,
            "subscriptions",
            ["stripe_subscription_id"],
            unique=True,
            postgresql_where=sa.text("stripe_subscription_id IS NOT NULL"),
        )
        return

    if not _has_table("subscriptions"):
        return

    _abort_on_duplicate_stripe_ids()
    if _has_index("subscriptions", _INDEX_NAME):
        return

    bind = op.get_bind()
    kwargs = {}
    if bind.dialect.name == "postgresql":
        kwargs["postgresql_where"] = sa.text("stripe_subscription_id IS NOT NULL")
    elif bind.dialect.name == "sqlite":
        kwargs["sqlite_where"] = sa.text("stripe_subscription_id IS NOT NULL")

    op.create_index(
        _INDEX_NAME,
        "subscriptions",
        ["stripe_subscription_id"],
        unique=True,
        **kwargs,
    )


def downgrade() -> None:
    if _has_index("subscriptions", _INDEX_NAME):
        op.drop_index(_INDEX_NAME, table_name="subscriptions")
