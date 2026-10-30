"""booking email verification token hash

Revision ID: f8c9d2e3a4b5
Revises: e6f7a8b9c0d1
Create Date: 2026-09-01 12:00:00

The ``OnlineBooking.email_verification_token`` column used to store the
plaintext email-verification token. A database breach therefore let an
attacker forge email confirmations for every pending booking in the
queue.

This change:

1. Adds ``OnlineBooking.email_verification_token_hash`` (SHA-256 hex).
2. Backfills the new column from any legacy plaintext rows so the
   ``verify_email`` endpoint can match them during the cut-over window.
3. Leaves the legacy plaintext column in place but unused. It can be
   dropped in a follow-up migration once all in-flight verifications
   have completed.

SQLite note: batch mode is used for every DDL so the table is recreated
rather than failing on in-place ALTER. Offline (--sql) rendering emits
the static form per the repo convention.
"""
import hashlib
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "f8c9d2e3a4b5"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    has_inspection = True
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        has_inspection = False

    # 1. Add the hash column (nullable so the existing rows can stay in
    # place while we backfill).
    if has_inspection:
        with op.batch_alter_table("online_bookings") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "email_verification_token_hash", sa.String(128), nullable=True
                )
            )
    else:
        op.add_column(
            "online_bookings",
            sa.Column("email_verification_token_hash", sa.String(128), nullable=True),
        )

    # 2. Backfill: hash any legacy plaintext tokens that are still present
    # (rows that have NOT yet been verified). We do this in Python so it
    # works identically on Postgres and SQLite; the row count is bounded
    # by the number of in-flight verifications, which is small.
    rows = bind.execute(
        sa.text(
            "SELECT id, email_verification_token FROM online_bookings "
            "WHERE email_verified = false "
            "  AND email_verification_token IS NOT NULL "
            "  AND email_verification_token <> ''"
        )
    ).fetchall()
    for row_id, plaintext in rows:
        if not plaintext:
            continue
        digest = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        bind.execute(
            sa.text(
                "UPDATE online_bookings SET email_verification_token_hash = :h "
                "WHERE id = :id"
            ),
            {"h": digest, "id": row_id},
        )

    # 3. Index for the verify-time lookup. The hash column is small and
    # highly selective; a btree keeps the verify-email endpoint fast.
    if has_inspection:
        with op.batch_alter_table("online_bookings") as batch_op:
            batch_op.create_index(
                "ix_online_bookings_email_verification_token_hash",
                ["email_verification_token_hash"],
            )
    else:
        op.create_index(
            "ix_online_bookings_email_verification_token_hash",
            "online_bookings",
            ["email_verification_token_hash"],
        )

    logger.info(
        "%s: email_verification_token_hash added and backfilled (%d rows)",
        revision,
        len(rows),
    )


def downgrade() -> None:
    bind = op.get_bind()
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        op.drop_index(
            "ix_online_bookings_email_verification_token_hash",
            table_name="online_bookings",
        )
        op.drop_column("online_bookings", "email_verification_token_hash")
        return

    with op.batch_alter_table("online_bookings") as batch_op:
        batch_op.drop_index("ix_online_bookings_email_verification_token_hash")
        batch_op.drop_column("email_verification_token_hash")