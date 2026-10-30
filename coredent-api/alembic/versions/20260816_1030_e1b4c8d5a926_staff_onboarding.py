"""staff onboarding: must_change_password flag + staff_invitations table

Revision ID: e1b4c8d5a926
Revises: d9a3b7e2c618
Create Date: 2026-08-16 10:30:00

- users.must_change_password: first-login force-change flag. Admin-
  provisioned accounts start with TRUE (the temporary password is known
  to the admin) and API access is restricted to the password-change
  endpoints until rotated. Existing accounts default to FALSE so nothing
  changes for already-operating users.
- staff_invitations: pending invitations for not-yet-created staff
  accounts. Tokens are stored hashed; the plaintext lives only in the
  emailed link. Replaces the dead invitation code removed in the 2026-08
  audit cleanup — onboarding stays admin-driven, but the invitee now
  chooses their own password instead of receiving one by hand.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e1b4c8d5a926"
down_revision: str | None = "d9a3b7e2c618"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "staff_invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "OWNER",
                "ADMIN",
                "DENTIST",
                "HYGIENIST",
                "FRONT_DESK",
                "GROUP_OWNER",
                "GROUP_ADMIN",
                name="userrole",
                create_type=False,  # enum type already exists (users.role)
            ),
            nullable=False,
        ),
        sa.Column("invited_by", sa.UUID(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["practice_id"], ["practices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "idx_staff_invitation_practice",
        "staff_invitations",
        ["practice_id"],
    )
    op.create_index("idx_staff_invitation_email", "staff_invitations", ["email"])


def downgrade() -> None:
    op.drop_index("idx_staff_invitation_email", table_name="staff_invitations")
    op.drop_index("idx_staff_invitation_practice", table_name="staff_invitations")
    op.drop_table("staff_invitations")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("must_change_password")
