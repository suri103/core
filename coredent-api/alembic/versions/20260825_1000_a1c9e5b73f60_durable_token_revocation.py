"""durable access-token revocation table

Revision ID: a1c9e5b73f60
Revises: f6b2d4e8a391
Create Date: 2026-08-25 10:00:00

WHY (audit finding H-01)
------------------------
Access-token revocation lived only in Redis, with an in-process ``deque``
fallback. The deque is per-worker, so a revocation written by worker A was
invisible to worker B, and on a Redis error the check returned
``jti in _fallback`` — a revoked token kept authenticating on any worker whose
local deque did not contain it. Revocation failed **open**.

Failing closed on Redis errors alone would reject every authenticated request
during a Redis blip. Instead revocation is now durable: written here
(authoritative, shared, transactional) and cached in Redis. Reads use Redis and
fall through to this table, so neither correctness nor availability depends on
Redis.

Rows are pruned by the scheduled ``purge_expired_revocations`` sweep once
``expires_at`` has passed; after that the token is rejected by its own ``exp``
claim and the row carries no information.

Idempotent: reflection-guarded, safe to re-run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c9e5b73f60"
down_revision: str | None = "f6b2d4e8a391"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def upgrade() -> None:
    if not _has_table("revoked_tokens"):
        op.create_table(
            "revoked_tokens",
            sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("jti", sa.String(length=64), nullable=False),
            sa.Column(
                "user_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column(
                "revoked_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    # Unique: revoking the same token twice is idempotent, not an error.
    if not _has_index("revoked_tokens", "uq_revoked_tokens_jti"):
        op.create_index(
            "uq_revoked_tokens_jti", "revoked_tokens", ["jti"], unique=True
        )
    # Supports the pruning sweep without a table scan.
    if not _has_index("revoked_tokens", "ix_revoked_tokens_expires_at"):
        op.create_index(
            "ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"]
        )
    if not _has_index("revoked_tokens", "ix_revoked_tokens_user_id"):
        op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])


def downgrade() -> None:
    for index in (
        "ix_revoked_tokens_user_id",
        "ix_revoked_tokens_expires_at",
        "uq_revoked_tokens_jti",
    ):
        if _has_index("revoked_tokens", index):
            op.drop_index(index, table_name="revoked_tokens")
    if _has_table("revoked_tokens"):
        op.drop_table("revoked_tokens")
