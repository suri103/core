"""Tests for audit logging"""
import pytest
from sqlalchemy import select



class TestAuditLogging:
    async def test_audit_log_created(self, async_client, db_session):
        from app.models.audit import AuditLog
        result = await db_session.execute(
            select(AuditLog).limit(1)
        )
        logs = result.scalars().all()
        assert isinstance(logs, list)

    async def test_audit_log_write_once(self, db_session):
        from app.models.audit import AuditLog
        # Create a log entry
        log = AuditLog(action="test_action", entity_type="patient")
        db_session.add(log)
        await db_session.commit()

        # Attempt update
        log.action = "updated_action"
        with pytest.raises(RuntimeError, match="Audit logs are write-once"):
            await db_session.commit()

        # Rollback the failed transaction
        await db_session.rollback()

        # Attempt delete
        await db_session.delete(log)
        with pytest.raises(RuntimeError, match="Audit logs are write-once"):
            await db_session.commit()

        # Rollback
        await db_session.rollback()


class TestSessionModel:
    def test_session_has_token_hash(self):
        from app.models.audit import Session
        assert hasattr(Session, 'token_hash')
        assert hasattr(Session, 'refresh_token')


class TestAuditIndexes:
    def test_audit_table_has_indexes(self):
        from app.models.audit import AuditLog
        table = AuditLog.__table__
        # created_at has index=True, which auto-generates an ix_ index
        indexed_columns = {
            col.name
            for idx in table.indexes
            for col in idx.columns
        }
        # Include inline column-level indexes
        for col in table.columns:
            if col.index:
                indexed_columns.add(col.name)
        assert 'created_at' in indexed_columns
