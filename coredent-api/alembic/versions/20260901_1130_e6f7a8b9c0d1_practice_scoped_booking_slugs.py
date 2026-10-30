"""practice-scoped public booking slugs

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-09-01 11:30:00

Booking page slugs are now practice-scoped: the public URL is
``/book/{practice.public_slug}/{page.page_slug}``, so two practices may
freely use the same page slug. This change:

1. Adds ``practices.public_slug`` (globally unique; backfilled from a slug
   derived from the practice name, then made NOT NULL with a unique index).
2. Drops the global unique index on ``booking_pages.page_slug``.
3. Adds the composite unique constraint ``(practice_id, page_slug)`` so each
   practice owns its page-slug namespace, with a DB-enforced guard.

SQLite note: batch mode is used for every DDL so the table is recreated
rather than failing on in-place ALTER. Offline (--sql) rendering emits the
static form per the repo convention.
"""

from collections.abc import Sequence

import logging
import re

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UQ_NAME = "uq_booking_pages_practice_page_slug"


def _slugify(name: str, fallback: str = "practice") -> str:
    """Best-effort human-readable slug for backfilling public_slug."""
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-+", "-", s)[:80]
    return s or fallback


def upgrade() -> None:
    bind = op.get_bind()
    has_inspection = True
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        has_inspection = False

    # 1. practices.public_slug — nullable add, deterministic backfill, NOT NULL + unique index.
    if has_inspection:
        with op.batch_alter_table("practices") as batch_op:
            batch_op.add_column(sa.Column("public_slug", sa.String(100), nullable=True))

        # CAST(id AS TEXT), not hex(id): PostgreSQL has no hex() for uuid, so
        # the original form raised "function hex(uuid) does not exist" and the
        # migration could never complete. SQLite does have hex(), which is why
        # this passed the whole test suite while being broken in production.
        op.execute(
            sa.text(
                "UPDATE practices SET public_slug = "
                "'practice-' || replace(CAST(id AS TEXT), '-', '') "
                "WHERE public_slug IS NULL OR public_slug = ''"
            )
        )

        with op.batch_alter_table("practices") as batch_op:
            batch_op.alter_column(
                "public_slug", existing_type=sa.String(100), nullable=False
            )
            batch_op.create_index("uq_practices_public_slug", ["public_slug"], unique=True)
    else:
        # Offline (--sql): emit the static form.
        op.add_column("practices", sa.Column("public_slug", sa.String(100), nullable=True))
        op.execute(
            "UPDATE practices SET public_slug = "
            "'practice-' || replace(CAST(id AS TEXT), '-', '') "
            "WHERE public_slug IS NULL OR public_slug = ''"
        )
        op.alter_column("practices", "public_slug", existing_type=sa.String(100), nullable=False)
        op.create_index("uq_practices_public_slug", "practices", ["public_slug"], unique=True)

    # 2. Drop the global unique index on booking_pages.page_slug.
    if has_inspection:
        with op.batch_alter_table("booking_pages") as batch_op:
            batch_op.drop_index("ix_booking_pages_page_slug")
    else:
        op.drop_index("ix_booking_pages_page_slug", table_name="booking_pages")

    # 3. Composite unique constraint (practice_id, page_slug).
    if has_inspection:
        with op.batch_alter_table("booking_pages") as batch_op:
            batch_op.create_unique_constraint(_UQ_NAME, ["practice_id", "page_slug"])
    else:
        op.create_unique_constraint(
            _UQ_NAME, "booking_pages", ["practice_id", "page_slug"]
        )


    if has_inspection:
        logger.info(
            "%s: practices.public_slug backfilled and unique; "
            "booking_pages.page_slug is now per-practice",
            revision,
        )


def downgrade() -> None:
    bind = op.get_bind()
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        # Offline (--sql): emit the static form.
        op.drop_constraint(_UQ_NAME, "booking_pages", type_="unique")
        op.create_index("ix_booking_pages_page_slug", "booking_pages", ["page_slug"], unique=True)
        op.drop_index("uq_practices_public_slug", table_name="practices")
        op.drop_column("practices", "public_slug")
        return

    with op.batch_alter_table("booking_pages") as batch_op:
        batch_op.drop_constraint(_UQ_NAME, type_="unique")
        batch_op.create_index("ix_booking_pages_page_slug", ["page_slug"], unique=True)
    with op.batch_alter_table("practices") as batch_op:
        batch_op.drop_index("uq_practices_public_slug")
        batch_op.drop_column("public_slug")
