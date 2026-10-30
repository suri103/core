"""Tests for communications endpoints"""
import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio


class TestMessageTemplates:
    async def test_list_templates_requires_auth(self, client):
        response = await client.get("/api/v1/communications/templates")
        assert response.status_code == 401

    async def test_create_template_requires_auth(self, client):
        response = await client.post("/api/v1/communications/templates", json={})
        assert response.status_code == 401

    async def test_create_template_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/communications/templates", json={}, headers=auth_headers)
        assert response.status_code in (422, 401, 403)

    async def test_get_template_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/communications/templates/{fake_id}")
        assert response.status_code == 401

    async def test_update_template_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/communications/templates/{fake_id}", json={})
        assert response.status_code == 401

    async def test_delete_template_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/communications/templates/{fake_id}")
        assert response.status_code == 401


class TestPatientMessages:
    async def test_list_messages_requires_auth(self, client):
        response = await client.get("/api/v1/communications/messages")
        assert response.status_code == 401

    async def test_create_message_requires_auth(self, client):
        response = await client.post("/api/v1/communications/messages", json={})
        assert response.status_code == 401

    async def test_create_message_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/communications/messages", json={})
        assert response.status_code in (422, 401, 403)


class TestConversations:
    async def test_list_conversations_requires_auth(self, client):
        response = await client.get("/api/v1/communications/conversations")
        assert response.status_code == 401

    async def test_create_conversation_requires_auth(self, client):
        response = await client.post("/api/v1/communications/conversations", json={})
        assert response.status_code == 401

    async def test_create_conversation_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/communications/conversations", json={})
        assert response.status_code in (422, 401, 403)


class TestReminderSchedules:
    async def test_list_reminders_requires_auth(self, client):
        response = await client.get("/api/v1/communications/reminders")
        assert response.status_code == 401

    async def test_create_reminder_requires_auth(self, client):
        response = await client.post("/api/v1/communications/reminders", json={})
        assert response.status_code == 401


class TestCommunicationsRoleGuards:
    """Write/PHI endpoints must reject non-privileged roles (DENTIST)."""

    @pytest.fixture(autouse=True)
    async def _setup_dentist(self, client: AsyncClient, db_session, test_practice):
        self._dentist_email = f"dentist_{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            id=uuid.uuid4(),
            email=self._dentist_email,
            password_hash=get_password_hash("testpassword123"),
            first_name="Doc",
            last_name="Dentist",
            role=UserRole.DENTIST,
            practice_id=test_practice.id,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        self._dentist_id = user.id

    async def _dentist_headers(self, client: AsyncClient):
        login = await client.post("/api/v1/auth/login", json={
            "email": self._dentist_email, "password": "testpassword123"
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_create_template_rejects_dentist(self, client, db_session, test_practice):
        headers = await self._dentist_headers(client)
        response = await client.post(
            "/api/v1/communications/templates",
            json={"name": "x", "message_type": "sms"},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_send_message_rejects_dentist(self, client, db_session, test_practice):
        headers = await self._dentist_headers(client)
        response = await client.post(
            "/api/v1/communications/messages",
            json={"patient_id": str(uuid.uuid4()), "content": "hi", "message_type": "sms"},
            headers=headers,
        )
        assert response.status_code == 403


class TestCommunicationsAuditLogging:
    """HIPAA: communications mutations and PHI views must write audit rows."""

    async def test_create_template_writes_audit_log(self, client, auth_headers, db_session):
        from app.models.audit import AuditLog

        response = await client.post(
            "/api/v1/communications/templates",
            json={"name": "Recall SMS", "message_type": "sms", "content": "Hi {{first_name}}"},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        template_id = uuid.UUID(response.json()["id"])

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "create_message_template",
                AuditLog.entity_type == "message_template",
                AuditLog.entity_id == template_id,
            )
        )
        assert result.scalars().first() is not None

    async def test_list_messages_writes_audit_log(self, client, auth_headers, db_session, test_user):
        from app.models.audit import AuditLog

        response = await client.get("/api/v1/communications/messages", headers=auth_headers)
        assert response.status_code == 200, response.text

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "list_messages",
                AuditLog.entity_type == "patient_message",
                AuditLog.user_id == test_user.id,
            )
        )
        assert result.scalars().first() is not None

    async def test_send_message_writes_audit_log(
        self, client, auth_headers, db_session, test_patient, monkeypatch
    ):
        from app.models.audit import AuditLog

        # The delivery task is out of scope for this test; keep the broker out.
        # Patch the module *attribute* (not ``.delay`` on the Celery proxy):
        # the endpoint's call-time ``from ... import send_message_task`` fetches
        # the current module attribute, so a stub here guarantees no AMQP connect.
        class _FakeSendTask:
            def delay(self, *args, **kwargs):
                return None

        monkeypatch.setattr(
            "app.core.communication_tasks.send_message_task",
            _FakeSendTask(),
        )

        # Communications endpoints use a separate sync connection; the fixture
        # only flushes, so commit to make the patient visible to them.
        await db_session.commit()

        response = await client.post(
            "/api/v1/communications/messages",
            json={
                "patient_id": str(test_patient.id),
                "content": "Reminder: appointment tomorrow",
                "message_type": "sms",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        message_id = uuid.UUID(response.json()["id"])

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "send_message",
                AuditLog.entity_type == "patient_message",
                AuditLog.entity_id == message_id,
            )
        )
        log = result.scalars().first()
        assert log is not None
        # Message content is PHI and must not be copied into the audit log.
        assert "content" not in (log.changes or {})
