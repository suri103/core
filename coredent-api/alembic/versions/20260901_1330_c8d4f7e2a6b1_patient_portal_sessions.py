"""patient portal multi-session table

Revision ID: c8d4f7e2a6b1
Revises: a9d3e4f5b6c7
Create Date: 2026-09-01 13:30:00

The single ``Patient.portal_access_token`` column only carried one
active token at a time — a second login overwrote the first session.
The new ``patient_portal_sessions`` table records every issued token
(hashed) so multiple concurrent sessions work and the patient can
revoke them all atomically.

The legacy column is retained for the cut-over window (the verify path
checks both); a follow-up migration can drop it once all issued
tokens expire (30-minute window).

SQLite note: batch mode is used for every DDL so the table is recreated
rather than failing on in-place ALTER. Offline (--sql) rendering emits
the static form per the repo convention.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4f7e2a6b1"
down_revision: str | None = "a9d3e4f5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    has_inspection = True
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        has_inspection = False

    if has_inspection:
        op.create_table(
            "patient_portal_sessions",
            sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
            sa.Column("patient_id", sa.UUID(as_uuid=True), nullable=False),
            sa.Column("practice_id", sa.UUID(as_uuid=True), nullable=False),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
            sa.ForeignKeyConstraint(["practice_id"], ["practices.id"]),
        )
        op.create_index(
            "ix_pps_token_hash",
            "patient_portal_sessions",
            ["token_hash"],
            unique=False,
        )
        op.create_index(
            "ix_pps_patient_active",
            "patient_portal_sessions",
            ["patient_id", "revoked_at", "expires_at"],
            unique=False,
        )
    else:
        op.execute(
            """
            CREATE TABLE patient_portal_sessions (
                id UUID PRIMARY KEY,
                patient_id UUID NOT NULL REFERENCES patients(id),
                practice_id UUID NOT NULL REFERENCES practices(id),
                token_hash VARCHAR(128) NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                revoked_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP WITH TIME ZONE,
                user_agent VARCHAR(500),
                ip_address VARCHAR(45)
            );
            CREATE INDEX ix_pps_token_hash ON patient_portal_sessions (token_hash);
            CREATE INDEX ix_pps_patient_active ON patient_portal_sessions (
                patient_id, revoked_at, expires_at
            );
            """
        )

    # Backfill: if any patient row already has a valid legacy token,
    # create one matching session row so the new verify path finds it.
    import uuid
    from datetime import datetime, timezone

    now_dt = datetime.now(timezone.utc)
    rows = bind.execute(
        sa.text(
            "SELECT id, practice_id, portal_access_token, portal_token_expires "
            "FROM patients "
            "WHERE portal_access_token IS NOT NULL "
            "  AND portal_token_expires IS NOT NULL "
            "  AND portal_token_expires > :now"
        ),
        {"now": now_dt},
    ).fetchall()
    for pid, prac_id, token_hash, expires_at in rows:
        if not token_hash:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO patient_portal_sessions "
                "(id, patient_id, practice_id, token_hash, expires_at, created_at) "
                "VALUES (:id, :pid, :prac, :h, :e, :created_at)"
            ),
            {
                "id": str(uuid.uuid4()) if bind.dialect.name == "sqlite" else uuid.uuid4(),
                "pid": pid,
                "prac": prac_id,
                "h": token_hash,
                "e": expires_at,
                "created_at": now_dt,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        op.execute("DROP TABLE IF EXISTS patient_portal_sessions;")
        return

    op.drop_table("patient_portal_sessions")