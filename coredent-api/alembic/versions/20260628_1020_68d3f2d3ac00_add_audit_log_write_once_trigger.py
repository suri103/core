"""add_audit_log_write_once_trigger

Revision ID: 68d3f2d3ac00
Revises: c4a1f9e2b007
Create Date: 2026-06-28 10:20:57.631890

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '68d3f2d3ac00'
down_revision = 'c4a1f9e2b007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Create function
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'HIPAA Compliance: Audit logs are write-once and cannot be modified or deleted.';
            END;
            $$ LANGUAGE plpgsql;
        """)
        # Create triggers
        op.execute("""
            CREATE TRIGGER check_audit_log_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
        """)
        op.execute("""
            CREATE TRIGGER check_audit_log_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS check_audit_log_update ON audit_logs;")
        op.execute("DROP TRIGGER IF EXISTS check_audit_log_delete ON audit_logs;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")
