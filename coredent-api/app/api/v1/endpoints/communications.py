"""
Communications API Endpoints
Patient messaging, SMS/email reminders, two-way messaging
"""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import and_

from uuid import UUID
from app.api.deps import (
    get_sync_db, get_current_user, get_current_practice, require_role,
    verify_csrf, verify_internal_job_token, verify_twilio_signature,
)
from app.services.communications_service import CommunicationsEngine
from app.core.audit import log_audit_event_sync
from app.models.user import User, UserRole
from app.models.communication import (
    # ORM models — imported with *Model aliases because the response schemas
    # below reuse the same bare names. Without the aliases every
    # db.query(PatientMessageModel) / PatientMessageModel(**data) here was bound to the
    # Pydantic schema and raised InvalidRequestError at runtime.
    MessageTemplate as MessageTemplateModel,
    PatientMessage as PatientMessageModel,
    ReminderSchedule as ReminderScheduleModel,
    Conversation as ConversationModel,
    ConversationMessage as ConversationMessageModel,
    MessageType, MessageDirection, MessageStatus, ReminderType
)
from app.models.patient import Patient
from app.schemas.communication import (
    MessageTemplateCreate, MessageTemplateUpdate, MessageTemplate,
    PatientMessageCreate, PatientMessageUpdate, PatientMessage,
    ReminderScheduleCreate, ReminderScheduleUpdate, ReminderSchedule,
    ConversationCreate, ConversationUpdate, Conversation,
    ConversationMessageCreate, ConversationMessage,
    CommunicationSummary, MessageStats, ReminderStats
)

router = APIRouter()


def _json_text(value):
    """Serialize list-like API fields stored in legacy TEXT columns."""
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)



# ============================================
# Message Templates
# ============================================

@router.get("/templates", response_model=List[MessageTemplate], tags=["Communications - Templates"])
def list_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    message_type: Optional[MessageType] = None,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """List all message templates for the current practice"""
    query = db.query(MessageTemplateModel).filter(
        MessageTemplateModel.practice_id == current_practice
    )

    if category:
        query = query.filter(MessageTemplateModel.category == category)
    if is_active is not None:
        query = query.filter(MessageTemplateModel.is_active == is_active)
    if message_type:
        query = query.filter(MessageTemplateModel.message_type == message_type)

    templates = query.order_by(MessageTemplateModel.is_default.desc(), MessageTemplateModel.name).offset(skip).limit(limit).all()
    return templates


@router.get("/templates/{template_id}", response_model=MessageTemplate, tags=["Communications - Templates"])
def get_template(
    template_id: str,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """Get a specific template by ID"""
    template = db.query(MessageTemplateModel).filter(
        and_(
            MessageTemplateModel.id == template_id,
            MessageTemplateModel.practice_id == current_practice
        )
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.post("/templates", response_model=MessageTemplate, status_code=status.HTTP_201_CREATED, tags=["Communications - Templates"])
def create_template(
    template: MessageTemplateCreate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Create a new message template"""
    # If this is set as default, unset other defaults
    if template.is_default:
        db.query(MessageTemplateModel).filter(
            and_(
                MessageTemplateModel.practice_id == current_practice,
                MessageTemplateModel.message_type == template.message_type,
                MessageTemplateModel.is_default.is_(True)
            )
        ).update({"is_default": False})

    template_data = template.model_dump()
    template_data["practice_id"] = current_practice
    template_data["variables"] = _json_text(template_data.get("variables"))
    db_template = MessageTemplateModel(**template_data)
    db.add(db_template)
    db.flush()
    log_audit_event_sync(
        db, current_user, "create_message_template", "message_template",
        db_template.id, request,
        changes={"name": db_template.name, "message_type": str(db_template.message_type)},
    )
    db.commit()
    db.refresh(db_template)
    return db_template


@router.put("/templates/{template_id}", response_model=MessageTemplate, tags=["Communications - Templates"])
def update_template(
    template_id: str,
    template_update: MessageTemplateUpdate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Update an existing template"""
    db_template = db.query(MessageTemplateModel).filter(
        and_(
            MessageTemplateModel.id == template_id,
            MessageTemplateModel.practice_id == current_practice
        )
    ).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    # If setting as default, unset other defaults
    if template_update.is_default:
        db.query(MessageTemplateModel).filter(
            and_(
                MessageTemplateModel.practice_id == current_practice,
                MessageTemplateModel.message_type == db_template.message_type,
                MessageTemplateModel.is_default.is_(True),
                MessageTemplateModel.id != template_id
            )
        ).update({"is_default": False})

    update_data = template_update.model_dump(exclude_unset=True)
    if 'variables' in update_data and update_data['variables'] is not None:
        update_data['variables'] = _json_text(update_data['variables'])

    for field, value in update_data.items():
        setattr(db_template, field, value)

    log_audit_event_sync(
        db, current_user, "update_message_template", "message_template",
        db_template.id, request,
        changes={"fields": sorted(update_data.keys())},
    )
    db.commit()
    db.refresh(db_template)
    return db_template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Communications - Templates"])
def delete_template(
    template_id: str,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Delete a template"""
    db_template = db.query(MessageTemplateModel).filter(
        and_(
            MessageTemplateModel.id == template_id,
            MessageTemplateModel.practice_id == current_practice
        )
    ).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    log_audit_event_sync(
        db, current_user, "delete_message_template", "message_template",
        db_template.id, request,
        changes={"name": db_template.name},
    )
    db.delete(db_template)
    db.commit()
    return None


# ============================================
# Patient Messages
# ============================================

@router.get("/messages", response_model=List[PatientMessage], tags=["Communications - Messages"])
def list_messages(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    patient_id: Optional[str] = None,
    message_type: Optional[MessageType] = None,
    status: Optional[MessageStatus] = None,
    direction: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """List patient messages"""
    query = db.query(PatientMessageModel).filter(
        PatientMessageModel.practice_id == current_practice
    )

    if patient_id:
        query = query.filter(PatientMessageModel.patient_id == patient_id)
    if message_type:
        query = query.filter(PatientMessageModel.message_type == message_type)
    if status:
        query = query.filter(PatientMessageModel.status == status)
    if direction:
        query = query.filter(PatientMessageModel.direction == direction)
    if date_from:
        query = query.filter(PatientMessageModel.created_at >= date_from)
    if date_to:
        query = query.filter(PatientMessageModel.created_at <= date_to)

    messages = query.order_by(PatientMessageModel.created_at.desc()).offset(skip).limit(limit).all()

    log_audit_event_sync(
        db, current_user, "list_messages", "patient_message", None, request
    )
    db.commit()
    return messages


@router.get("/messages/{message_id}", response_model=PatientMessage, tags=["Communications - Messages"])
def get_message(
    message_id: str,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """Get a specific message by ID"""
    message = db.query(PatientMessageModel).filter(
        and_(
            PatientMessageModel.id == message_id,
            PatientMessageModel.practice_id == current_practice
        )
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    log_audit_event_sync(
        db, current_user, "view_message", "patient_message", message.id, request
    )
    db.commit()
    return message


@router.post("/messages", response_model=PatientMessage, status_code=status.HTTP_201_CREATED, tags=["Communications - Messages"])
def send_message(
    message: PatientMessageCreate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Persist a message before dispatching its durable delivery task.

    ``Idempotency-Key`` is optional for compatibility, but when supplied it
    makes a client retry return the original message instead of creating and
    delivering another one. The persisted PENDING row is the outbox: broker
    publication can fail without losing the delivery because Beat recovers it.
    """
    idempotency_key = (request.headers.get("Idempotency-Key") or "").strip()[:255] or None
    if idempotency_key:
        existing = db.query(PatientMessageModel).filter(
            PatientMessageModel.practice_id == current_practice,
            PatientMessageModel.dedupe_key == idempotency_key,
        ).first()
        if existing:
            if (
                existing.patient_id != message.patient_id
                or existing.message_type != message.message_type
                or existing.content != message.content
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key is already used by a different message",
                )
            return existing

    patient = db.query(Patient).filter(
        and_(
            Patient.id == message.patient_id,
            Patient.practice_id == current_practice,
        )
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if message.template_id:
        template = db.query(MessageTemplateModel).filter(
            and_(
                MessageTemplateModel.id == message.template_id,
                MessageTemplateModel.practice_id == current_practice,
            )
        ).first()
        if template:
            template.times_used += 1

    recipient_phone = message.recipient_phone or patient.phone
    recipient_email = message.recipient_email or patient.email
    message_data = message.model_dump(
        exclude={
            "template_id", "appointment_id", "parent_message_id", "direction",
            "attachments", "recipient_phone", "recipient_email",
        }
    )
    message_data["attachments"] = _json_text(message.attachments)
    message_data["direction"] = MessageDirection.OUTBOUND
    db_message = PatientMessageModel(
        **message_data,
        practice_id=current_practice,
        user_id=current_user.id,
        recipient_phone=recipient_phone,
        recipient_email=recipient_email,
        status=MessageStatus.PENDING,
        dedupe_key=idempotency_key,
        next_attempt_at=message_data.get("scheduled_at") or datetime.now(timezone.utc),
    )

    db.add(db_message)
    db.flush()
    log_audit_event_sync(
        db, current_user, "send_message", "patient_message", db_message.id, request,
        changes={
            "patient_id": str(message.patient_id),
            "message_type": str(message.message_type),
        },
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        if not idempotency_key:
            raise
        existing = db.query(PatientMessageModel).filter(
            PatientMessageModel.practice_id == current_practice,
            PatientMessageModel.dedupe_key == idempotency_key,
        ).first()
        if existing:
            return existing
        raise
    db.refresh(db_message)

    from app.core.communication_tasks import send_message_task

    # If the broker is unavailable this raises after the row is committed;
    # the caller can safely retry with the same key and Beat will recover the
    # pending delivery independently.
    send_message_task.delay(str(db_message.id))
    return db_message


@router.put("/messages/{message_id}", response_model=PatientMessage, tags=["Communications - Messages"])
def update_message(
    message_id: str,
    message_update: PatientMessageUpdate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Update a message (e.g., mark as sent, update status)"""
    db_message = db.query(PatientMessageModel).filter(
        and_(
            PatientMessageModel.id == message_id,
            PatientMessageModel.practice_id == current_practice
        )
    ).first()

    if not db_message:
        raise HTTPException(status_code=404, detail="Message not found")

    update_data = message_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_message, field, value)

    # Field names only — message content is PHI and stays out of the audit log.
    log_audit_event_sync(
        db, current_user, "update_message", "patient_message",
        db_message.id, request,
        changes={"fields": sorted(update_data.keys())},
    )
    db.commit()
    db.refresh(db_message)
    return db_message


# ============================================
# Reminder Schedules
# ============================================

@router.get("/reminders", response_model=List[ReminderSchedule], tags=["Communications - Reminders"])
def list_reminders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = None,
    reminder_type: Optional[ReminderType] = None,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """List all reminder schedules"""
    query = db.query(ReminderScheduleModel).filter(
        ReminderScheduleModel.practice_id == current_practice
    )

    if is_active is not None:
        query = query.filter(ReminderScheduleModel.is_active == is_active)
    if reminder_type:
        query = query.filter(ReminderScheduleModel.reminder_type == reminder_type)

    reminders = query.order_by(ReminderScheduleModel.name).offset(skip).limit(limit).all()
    return reminders


@router.get("/reminders/{reminder_id}", response_model=ReminderSchedule, tags=["Communications - Reminders"])
def get_reminder(
    reminder_id: str,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """Get a specific reminder schedule"""
    reminder = db.query(ReminderScheduleModel).filter(
        and_(
            ReminderScheduleModel.id == reminder_id,
            ReminderScheduleModel.practice_id == current_practice
        )
    ).first()

    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder schedule not found")

    return reminder


@router.post("/reminders", response_model=ReminderSchedule, status_code=status.HTTP_201_CREATED, tags=["Communications - Reminders"])
def create_reminder(
    reminder: ReminderScheduleCreate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Create a new reminder schedule"""
    # Verify template exists
    template = db.query(MessageTemplateModel).filter(
        and_(
            MessageTemplateModel.id == reminder.template_id,
            MessageTemplateModel.practice_id == current_practice
        )
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    reminder_data = reminder.model_dump()
    reminder_data["practice_id"] = current_practice
    reminder_data["patient_types"] = _json_text(reminder_data.get("patient_types"))
    db_reminder = ReminderScheduleModel(**reminder_data)
    db.add(db_reminder)
    db.flush()
    log_audit_event_sync(
        db, current_user, "create_reminder_schedule", "reminder_schedule",
        db_reminder.id, request,
        changes={"name": db_reminder.name, "reminder_type": str(db_reminder.reminder_type)},
    )
    db.commit()
    db.refresh(db_reminder)
    return db_reminder


@router.put("/reminders/{reminder_id}", response_model=ReminderSchedule, tags=["Communications - Reminders"])
def update_reminder(
    reminder_id: str,
    reminder_update: ReminderScheduleUpdate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Update a reminder schedule"""
    db_reminder = db.query(ReminderScheduleModel).filter(
        and_(
            ReminderScheduleModel.id == reminder_id,
            ReminderScheduleModel.practice_id == current_practice
        )
    ).first()

    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder schedule not found")

    update_data = reminder_update.model_dump(exclude_unset=True)
    if "template_id" in update_data and update_data["template_id"] is not None:
        template = db.query(MessageTemplateModel).filter(
            and_(
                MessageTemplateModel.id == update_data["template_id"],
                MessageTemplateModel.practice_id == current_practice,
            )
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    if 'patient_types' in update_data and update_data['patient_types'] is not None:
        update_data['patient_types'] = _json_text(update_data['patient_types'])

    for field, value in update_data.items():
        setattr(db_reminder, field, value)

    log_audit_event_sync(
        db, current_user, "update_reminder_schedule", "reminder_schedule",
        db_reminder.id, request,
        changes={"fields": sorted(update_data.keys())},
    )
    db.commit()
    db.refresh(db_reminder)
    return db_reminder


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Communications - Reminders"])
def delete_reminder(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Delete a reminder schedule"""
    db_reminder = db.query(ReminderScheduleModel).filter(
        and_(
            ReminderScheduleModel.id == reminder_id,
            ReminderScheduleModel.practice_id == current_practice
        )
    ).first()

    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder schedule not found")

    log_audit_event_sync(
        db, current_user, "delete_reminder_schedule", "reminder_schedule",
        db_reminder.id, request,
        changes={"name": db_reminder.name},
    )
    db.delete(db_reminder)
    db.commit()
    return None


# ============================================
# Conversations
# ============================================

@router.get("/conversations", response_model=List[Conversation], tags=["Communications - Conversations"])
def list_conversations(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = None,
    patient_id: Optional[str] = None,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """List all conversations"""
    query = db.query(ConversationModel).filter(
        ConversationModel.practice_id == current_practice
    )

    if status:
        query = query.filter(ConversationModel.status == status)
    if patient_id:
        query = query.filter(ConversationModel.patient_id == patient_id)

    conversations = query.order_by(ConversationModel.last_message_at.desc().nullsfirst()).offset(skip).limit(limit).all()

    log_audit_event_sync(
        db, current_user, "list_conversations", "conversation", None, request
    )
    db.commit()
    return conversations


@router.get("/conversations/{conversation_id}", response_model=Conversation, tags=["Communications - Conversations"])
def get_conversation(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """Get a specific conversation"""
    conversation = db.query(ConversationModel).filter(
        and_(
            ConversationModel.id == conversation_id,
            ConversationModel.practice_id == current_practice
        )
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    log_audit_event_sync(
        db, current_user, "view_conversation", "conversation",
        conversation.id, request
    )
    db.commit()
    return conversation


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED, tags=["Communications - Conversations"])
def create_conversation(
    conversation: ConversationCreate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Create a new conversation"""
    # Verify patient exists
    patient = db.query(Patient).filter(
        and_(
            Patient.id == conversation.patient_id,
            Patient.practice_id == current_practice
        )
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Check if conversation already exists
    existing = db.query(ConversationModel).filter(
        and_(
            ConversationModel.practice_id == current_practice,
            ConversationModel.patient_id == conversation.patient_id,
            ConversationModel.channel == conversation.channel,
            ConversationModel.status == 'active'
        )
    ).first()

    if existing:
        return existing

    db_conversation = ConversationModel(
        **conversation.model_dump(),
        practice_id=current_practice,
        assigned_user_id=current_user.id
    )
    db.add(db_conversation)
    db.flush()
    log_audit_event_sync(
        db, current_user, "create_conversation", "conversation",
        db_conversation.id, request,
        changes={
            "patient_id": str(conversation.patient_id),
            "channel": str(conversation.channel),
        },
    )
    db.commit()
    db.refresh(db_conversation)
    return db_conversation


@router.put("/conversations/{conversation_id}", response_model=Conversation, tags=["Communications - Conversations"])
def update_conversation(
    conversation_id: str,
    conversation_update: ConversationUpdate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Update a conversation"""
    db_conversation = db.query(ConversationModel).filter(
        and_(
            ConversationModel.id == conversation_id,
            ConversationModel.practice_id == current_practice
        )
    ).first()

    if not db_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    update_data = conversation_update.model_dump(exclude_unset=True)
    if "assigned_user_id" in update_data and update_data["assigned_user_id"] is not None:
        assigned_user = db.query(User).filter(
            and_(
                User.id == update_data["assigned_user_id"],
                User.practice_id == current_practice,
                User.is_active.is_(True),
            )
        ).first()
        if not assigned_user:
            raise HTTPException(status_code=404, detail="Assigned user not found")
    for field, value in update_data.items():
        setattr(db_conversation, field, value)

    log_audit_event_sync(
        db, current_user, "update_conversation", "conversation",
        db_conversation.id, request,
        changes={"fields": sorted(update_data.keys())},
    )
    db.commit()
    db.refresh(db_conversation)
    return db_conversation


@router.get("/conversations/{conversation_id}/messages", response_model=List[ConversationMessage], tags=["Communications - Conversations"])
def get_conversation_messages(
    conversation_id: str,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """Get messages in a conversation"""
    # Verify conversation exists
    conversation = db.query(ConversationModel).filter(
        and_(
            ConversationModel.id == conversation_id,
            ConversationModel.practice_id == current_practice
        )
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.query(ConversationMessageModel).filter(
        ConversationMessageModel.conversation_id == conversation_id
    ).order_by(ConversationMessageModel.created_at.asc()).offset(skip).limit(limit).all()

    log_audit_event_sync(
        db, current_user, "view_conversation_messages", "conversation",
        conversation.id, request
    )
    db.commit()
    return messages


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationMessage, status_code=status.HTTP_201_CREATED, tags=["Communications - Conversations"])
def send_conversation_message(
    conversation_id: str,
    message: ConversationMessageCreate,
    request: Request,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    current_practice: UUID = Depends(get_current_practice),
    _csrf: bool = Depends(verify_csrf)
):
    """Send a message in a conversation (Staff -> Patient)"""
    # Verify conversation exists
    conversation = db.query(ConversationModel).filter(
        and_(
            ConversationModel.id == conversation_id,
            ConversationModel.practice_id == current_practice
        )
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    engine = CommunicationsEngine(db)

    external_id = None

    # Direct conversation SMS is persisted only after provider acceptance.
    if conversation.channel == MessageType.SMS:
        patient = db.get(Patient, conversation.patient_id)
        if not patient or not patient.phone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Patient phone number is unavailable",
            )

        delivery = engine.send_sms(patient.phone, message.content)
        if delivery.get("status") != "sent":
            # Provider details are intentionally not exposed to API clients.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SMS delivery was not accepted",
            )
        external_id = delivery.get("external_id")
    elif conversation.channel == MessageType.EMAIL:
        import html as _html

        from app.core.email_tasks import enqueue_email

        patient = db.get(Patient, conversation.patient_id)
        if not patient or not patient.email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Patient email address is unavailable",
            )
        # enqueue_email publishes to the broker (one Message-ID across retries);
        # the ConversationMessage row committed below is the durable record.
        enqueue_email(
            to=patient.email,
            subject=getattr(conversation, "subject", None) or "Message from your dental practice",
            html_content=f"<p>{_html.escape(message.content)}</p>",
            text_content=message.content,
        )

    message_data = message.model_dump(exclude={"conversation_id", "sender_id", "sender_type", "attachments"})
    message_data["attachments"] = _json_text(message.attachments)
    db_message = ConversationMessageModel(
        **message_data,
        conversation_id=conversation_id,
        sender_type="staff",
        sender_id=current_user.id,
        external_id=external_id,
    )
    db.add(db_message)
    db.flush()

    log_audit_event_sync(
        db, current_user, "send_conversation_message", "conversation_message",
        db_message.id, request,
        changes={
            "conversation_id": str(conversation.id),
            "patient_id": str(conversation.patient_id),
            "channel": str(conversation.channel),
        },
    )

    # Update conversation's last message info in the same transaction.
    conversation.last_message_at = db_message.created_at
    conversation.last_message_preview = message.content[:255]
    # Staff messages are outbound and must not increment the patient-unread counter.
    db.commit()
    db.refresh(db_message)

    return db_message


# ============================================
# Engine & Webhooks
# ============================================

@router.post("/webhook/twilio", tags=["Communications - Webhooks"])
async def twilio_inbound_sms(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    db: Session = Depends(get_sync_db),
    _twilio_signature: bool = Depends(verify_twilio_signature),
):
    """Receive and authenticate a Twilio inbound SMS webhook."""
    engine = CommunicationsEngine(db)
    engine.handle_inbound_sms(From, To, Body, MessageSid)
    return Response(content="<Response></Response>", media_type="application/xml")


@router.post("/engine/run-recalls", tags=["Communications - Engine"])
def trigger_recall_engine(
    db: Session = Depends(get_sync_db),
    _internal_job: bool = Depends(verify_internal_job_token),
):
    """Run recalls from a trusted scheduler using X-Internal-Job-Token."""
    engine = CommunicationsEngine(db)
    engine.process_automated_recalls()
    return {"status": "success", "message": "Automated recall engine executed"}


# ============================================
# Communication Settings
# ============================================

@router.get("/settings", response_model=CommunicationSummary, tags=["Communications - Settings"])
def get_communication_settings(
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    current_practice: UUID = Depends(get_current_practice)
):
    """Get communication settings and statistics"""
    # Message stats (aware UTC — M8: window must not depend on host TZ)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    messages_sent = db.query(PatientMessageModel).filter(
        and_(
            PatientMessageModel.practice_id == current_practice,
            PatientMessageModel.sent_at >= week_ago
        )
    ).count()

    messages_delivered = db.query(PatientMessageModel).filter(
        and_(
            PatientMessageModel.practice_id == current_practice,
            PatientMessageModel.status == MessageStatus.DELIVERED,
            PatientMessageModel.delivered_at >= week_ago
        )
    ).count()

    messages_failed = db.query(PatientMessageModel).filter(
        and_(
            PatientMessageModel.practice_id == current_practice,
            PatientMessageModel.status == MessageStatus.FAILED,
            PatientMessageModel.sent_at >= week_ago
        )
    ).count()

    delivery_rate = (messages_delivered / messages_sent * 100) if messages_sent > 0 else 0.0

    # Reminder stats
    reminders_scheduled = db.query(ReminderScheduleModel).filter(
        and_(
            ReminderScheduleModel.practice_id == current_practice,
            ReminderScheduleModel.is_active.is_(True)
        )
    ).count()

    reminders_pending = db.query(PatientMessageModel).filter(
        and_(
            PatientMessageModel.practice_id == current_practice,
            PatientMessageModel.status == MessageStatus.PENDING,
            PatientMessageModel.scheduled_at.isnot(None)
        )
    ).count()

    # Conversation stats
    active_conversations = db.query(ConversationModel).filter(
        and_(
            ConversationModel.practice_id == current_practice,
            ConversationModel.status == 'active'
        )
    ).count()

    unread_messages = db.query(ConversationModel).filter(
        and_(
            ConversationModel.practice_id == current_practice,
            ConversationModel.status == 'active'
        )
    ).with_entities(ConversationModel.unread_count).all()
    unread_messages = sum((row[0] or 0) for row in unread_messages)

    return CommunicationSummary(
        messages=MessageStats(
            total_sent=messages_sent,
            total_delivered=messages_delivered,
            total_failed=messages_failed,
            delivery_rate=round(delivery_rate, 1),
            total_cost="0.00"  # Would need to calculate from message costs
        ),
        reminders=ReminderStats(
            total_scheduled=reminders_scheduled,
            total_sent=0,  # Would need to track separately
            total_delivered=0,
            pending=reminders_pending,
            failed=0
        ),
        active_conversations=active_conversations,
        unread_messages=unread_messages
    )
