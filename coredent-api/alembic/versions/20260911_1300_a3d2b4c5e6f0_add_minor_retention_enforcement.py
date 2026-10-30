"""add minor-aware retention enforcement columns

Revision ID: a3d2b4c5e6f0
Revises: e9f1a4b3d0c6
Create Date: 2026-09-11 13:00:00

- practices.majority_age: age of majority for the minor-retention rule (default 18).
- practices.minor_retention_years: extra years past majority a minor record is kept.
- patients.purge_eligible_at: snapshot date when a record may be hard-purged under
  the minor rule. Computed AT ANONYMIZE TIME from DOB + practice config, before
  DOB is scrubbed, so the minor ceiling survives erasure without keeping PHI.

A patient is purged only when BOTH conditions hold:
  now >= billing_anchor + max(practice, platform floor)   [adult window]
  now >= purge_eligible_at                                 [minor ceiling, if set]
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a3d2b4c5e6f0"
down_revision: str | None = "e9f1a4b3d0c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("majority_age", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("minor_retention_years", sa.Integer(), nullable=True))
    with op.batch_alter_table("patients", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purge_eligible_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("patients", schema=None) as batch_op:
        batch_op.drop_column("purge_eligible_at")
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.drop_column("minor_retention_years")
        batch_op.drop_column("majority_age")