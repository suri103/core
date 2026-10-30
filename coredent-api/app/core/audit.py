"""
Audit Logging Utilities
Functions for logging HIPAA-compliant audit events
"""

from typing import Any, Optional
from uuid import UUID
from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.models.user import User


def _normalize_entity_id(entity_id: Any) -> Any:
    # For SQLite compatibility: convert entity_id to UUID when present
    if entity_id is None:
        return None
    if isinstance(entity_id, str):
        try:
            # Try to parse as UUID
            return UUID(entity_id)
        except (ValueError, AttributeError):
            # Not a valid UUID, create one from the string
            from uuid import uuid5, NAMESPACE_DNS
            return uuid5(NAMESPACE_DNS, entity_id)
    return entity_id


def _request_context(request: Optional[Request]):
    if not request:
        return None, None
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def log_audit_event(
    db: AsyncSession,
    user: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Any,  # Changed from UUID to Any to accept strings
    request: Optional[Request] = None,
    changes: Optional[dict] = None,
) -> None:
    """
    Log an audit event to the database
    """
    ip_address, user_agent = _request_context(request)
    entity_id = _normalize_entity_id(entity_id)

    audit_entry = AuditLog(
        user_id=user.id if user else None,  # Keep as UUID object
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(audit_entry)
    # We use await db.flush() instead of commit() to allow the caller to handle the transaction
    await db.flush()


def log_audit_event_sync(
    db: Session,
    user: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Any,
    request: Optional[Request] = None,
    changes: Optional[dict] = None,
) -> None:
    """Sync-session variant for endpoints bound to get_sync_db.

    Flushes without committing so the caller's transaction remains atomic
    with the audited operation.
    """
    ip_address, user_agent = _request_context(request)
    entity_id = _normalize_entity_id(entity_id)

    audit_entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(audit_entry)
    db.flush()
