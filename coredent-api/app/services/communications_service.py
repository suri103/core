from app.core.config_simple import settings
"""
Communications Engineering Service
Handles Twilio integration (Two-way SMS) and the Automated Recall Engine.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import logging
import os
import time

from app.models.practice import Practice
from app.models.patient import Patient, PatientStatus
from app.models.appointment import Appointment, AppointmentStatus, AppointmentTypeEnum
from app.models.communication import (
    PatientMessage, MessageTemplate, ReminderSchedule,
    Conversation, ConversationMessage, MessageType, MessageStatus, MessageDirection,
    ReminderType
)

logger = logging.getLogger(__name__)

class CommunicationsEngine:
    """Core Engine for Automated Reminders, Recalls, and Two-Way SMS"""

    def __init__(self, db: Session):
        self.db = db
        # In a real system, you would initialize twilio_client here:
        # self.twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def _replace_variables(self, template: str, context: dict) -> str:
        """Replace [variable] placeholders in template string"""
        result = template
        for key, value in context.items():
            result = result.replace(f"[{key}]", str(value or ''))
        return result

    def send_sms(self, to_phone: str, body: str) -> Dict[str, Any]:
        """Send SMS via Twilio and fail closed when the provider is unavailable."""
        if not to_phone:
            return {"status": "failed", "error": "No phone number provided"}

        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        from_number = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
        if not account_sid or not auth_token or not from_number:
            logger.error("SMS delivery unavailable: Twilio is not fully configured")
            return {"status": "failed", "error": "SMS provider is not configured"}

        try:
            from twilio.rest import Client
            from twilio.http.http_client import TwilioHttpClient
            client = Client(account_sid, auth_token, http_client=TwilioHttpClient(timeout=10.0))
            message = client.messages.create(
                body=body,
                from_=from_number,
                to=to_phone,
            )
            return {"status": "sent", "external_id": message.sid}
        except Exception as exc:
            logger.error("Twilio SMS delivery failed: %s", exc)
            return {"status": "failed", "error": "SMS delivery failed"}

    def send_sms_with_retry(self, to_phone: str, body: str, retries: int = 3, backoff: float = 0.5) -> Dict[str, Any]:
        """Send SMS with simple retry/backoff for transient failures"""
        attempt = 0
        while attempt <= retries:
            result = self.send_sms(to_phone, body)
            if result.get("status") != "failed":
                return result
            attempt += 1
            if attempt <= retries:
                time.sleep(backoff * attempt)
        return result

    def process_automated_recalls(self):
        """
        Automated Recall System Engine
        Runs daily. Finds patients due for hygiene recalls and sends SMS/Email.
        """
        logger.info("Starting Automated Recall Engine...")
        now = datetime.now(timezone.utc)
        counts = {
            "practices_scanned": 0,
            "schedules_scanned": 0,
            "appointments_scanned": 0,
            "created": 0,
            "existing": 0,
            "published": 0,
            "publish_failed": 0,
            "errors": 0,
        }

        # 1. Get all active practices
        practices = self.db.query(Practice).filter(Practice.is_active.is_(True)).all()
        counts["practices_scanned"] = len(practices)

        for practice in practices:
            # 2. Get active active recall schedules for this practice
            schedules = self.db.query(ReminderSchedule).filter(
                and_(
                    ReminderSchedule.practice_id == practice.id,
                    ReminderSchedule.is_active.is_(True),
                    ReminderSchedule.reminder_type == ReminderType.RECALL
                )
            ).all()
            counts["schedules_scanned"] += len(schedules)

            for schedule in schedules:
                if not schedule.template_id:
                    continue

                template = self.db.query(MessageTemplate).get(schedule.template_id)
                if not template:
                    continue

                # Logic: Find patients whose LAST completed hygiene appointment was X days ago
                # and who do NOT have a future matching appointment.

                # H-3 FIX: Compute target date using the practice's local calendar
                # and convert to exact UTC half-open query bounds.
                from app.core.business_time import business_date, day_bounds_utc, practice_timezone_of
                practice_tz = practice_timezone_of(practice)
                local_today = business_date(practice_tz, now)
                target_day = local_today - timedelta(days=schedule.days_before)
                target_start_utc, target_end_utc = day_bounds_utc(practice_tz, target_day)

                # Find appointments that were completed on target_date that are CLEANING/EXAM
                last_appointments = self.db.query(Appointment).filter(
                    and_(
                        Appointment.practice_id == practice.id,
                        Appointment.status == AppointmentStatus.COMPLETED,
                        Appointment.appointment_type.in_([AppointmentTypeEnum.CLEANING, AppointmentTypeEnum.EXAM]),
                        Appointment.end_time >= target_start_utc,
                        Appointment.end_time < target_end_utc
                    )
                ).all()
                counts["appointments_scanned"] += len(last_appointments)

                for apt in last_appointments:
                    patient = self.db.query(Patient).get(apt.patient_id)
                    if not patient or patient.status != PatientStatus.ACTIVE:
                        continue

                    # Check if they already have a future appointment schedule
                    future_apt = self.db.query(Appointment).filter(
                        and_(
                            Appointment.patient_id == patient.id,
                            Appointment.start_time > now,
                            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
                        )
                    ).first()

                    if future_apt:
                        continue # Already scheduled, skip recall

                    # Send Recall Message!
                    context = {
                        "patient_name": patient.first_name,
                        "practice_name": practice.name,
                        "last_visit_date": apt.start_time.strftime("%B %d, %Y") if apt.start_time else "recently",
                        "booking_link": (
                            f"{settings.FRONTEND_URL.rstrip('/')}/book/{getattr(practice, 'public_slug', None) or getattr(practice, 'slug', '')}"
                            if (getattr(practice, 'public_slug', None) or getattr(practice, 'slug', None))
                            else ""
                        )
                    }

                    body = self._replace_variables(template.content, context)

                    # Persist one recall delivery per schedule/appointment before
                    # publishing. A duplicated recall-engine run converges on
                    # this key; broker publication can be recovered from the
                    # PENDING row by the periodic dispatcher.
                    dedupe_key = f"recall:{schedule.id}:{apt.id}"
                    try:
                        existing = self.db.query(PatientMessage).filter(
                            PatientMessage.practice_id == practice.id,
                            PatientMessage.dedupe_key == dedupe_key,
                        ).first()
                        if existing:
                            counts["existing"] += 1
                            from app.core.communication_tasks import send_message_task

                            try:
                                send_message_task.delay(str(existing.id))
                                counts["published"] += 1
                            except Exception as publish_exc:
                                counts["publish_failed"] += 1
                                logger.warning(
                                    "Recall %s remains pending for dispatcher recovery: %s",
                                    existing.id,
                                    publish_exc,
                                )
                            continue

                        msg = PatientMessage(
                            practice_id=practice.id,
                            patient_id=patient.id,
                            template_id=template.id,
                            message_type=template.message_type,
                            direction=MessageDirection.OUTBOUND,
                            status=MessageStatus.PENDING,
                            content=body,
                            recipient_phone=patient.phone,
                            recipient_email=patient.email,
                            dedupe_key=dedupe_key,
                            next_attempt_at=now,
                        )
                        self.db.add(msg)
                        self.db.commit()
                        counts["created"] += 1

                        from app.core.communication_tasks import send_message_task

                        try:
                            send_message_task.delay(str(msg.id))
                            counts["published"] += 1
                        except Exception as publish_exc:
                            counts["publish_failed"] += 1
                            logger.warning(
                                "Recall %s remains pending for dispatcher recovery: %s",
                                msg.id,
                                publish_exc,
                            )
                        logger.info("Recall queued for %s at practice %s", patient.id, practice.id)
                    except Exception as exc:
                        counts["errors"] += 1
                        self.db.rollback()
                        logger.error("Failed to queue recall for %s: %s", patient.id, exc)

        return {"status": "completed", **counts}

    def handle_inbound_sms(self, from_phone: str, to_phone: str, body: str, external_id: str):
        """
        Two-Way SMS Webhook Handler
        Parses inbound SMS from Twilio and routes it to the correct patient Conversation.
        """
        now = datetime.now(timezone.utc)

        # Clean phone number
        cleaned_phone = from_phone[-10:] if len(from_phone) >= 10 else from_phone

        # 1. Match destination practice by to_phone if available
        destination_practice = None
        if to_phone:
            digits_to = "".join(filter(str.isdigit, str(to_phone)))
            to_last10 = digits_to[-10:] if len(digits_to) >= 10 else digits_to
            destination_practice = self.db.query(Practice).filter(
                (Practice.inbound_phone_number.like(f"%{to_last10}%")) |
                (Practice.phone.like(f"%{to_last10}%"))
            ).first()

        # Build candidate phone variants for blind index (search_index_phone)
        from app.core.search_index import hmac_index
        digits_from = "".join(filter(str.isdigit, str(from_phone)))
        from_last10 = digits_from[-10:] if len(digits_from) >= 10 else digits_from
        variants = {from_phone, f"+{digits_from}", digits_from, from_last10, f"+1{from_last10}"}
        candidate_hmacs = [h for h in (hmac_index(v) for v in variants) if h]

        patient_query = self.db.query(Patient)
        if candidate_hmacs:
            patient_query = patient_query.filter(Patient.search_index_phone.in_(candidate_hmacs))
        else:
            patient_query = patient_query.filter(func.lower(Patient.phone).like(f"%{cleaned_phone}%"))

        if destination_practice is not None:
            patient_query = patient_query.filter(Patient.practice_id == destination_practice.id)

        candidates = patient_query.limit(2).all()
        if len(candidates) != 1:
            if len(candidates) > 1:
                logger.warning("Inbound SMS rejected: phone matched %s active patient records across practices", len(candidates))
            else:
                redacted_number = f"***{from_phone[-4:]}" if from_phone and len(str(from_phone)) >= 4 else "***"
                logger.warning(f"Inbound SMS from unknown number: {redacted_number}")
            return False
        patient = candidates[0]

        if not patient:
            # PHI hygiene: never write a full phone number to logs. Keep the
            # last 4 digits for operator triage.
            redacted_number = f"***{from_phone[-4:]}" if from_phone and len(str(from_phone)) >= 4 else "***"
            logger.warning(f"Inbound SMS from unknown number: {redacted_number}")
            return False

        # Twilio can retry a webhook; never persist the same provider message twice.
        if isinstance(self.db, Session):
            duplicate = self.db.query(ConversationMessage).filter(
                ConversationMessage.external_id == external_id
            ).first()
            if duplicate:
                return True

        practice_id = patient.practice_id

        # 2. Add to existing Conversation or create a new one
        conversation = self.db.query(Conversation).filter(
            and_(
                Conversation.patient_id == patient.id,
                Conversation.channel == MessageType.SMS,
                Conversation.status == 'active'
            )
        ).first()

        if not conversation:
            conversation = Conversation(
                practice_id=practice_id,
                patient_id=patient.id,
                channel=MessageType.SMS,
                status='active',
                last_message_at=now,
                last_message_preview=body[:255],
                unread_count=1
            )
            self.db.add(conversation)
            self.db.flush()
        else:
            conversation.last_message_at = now
            conversation.last_message_preview = body[:255]
            conversation.unread_count += 1

        # 3. Save ConversationMessage
        conv_msg = ConversationMessage(
            conversation_id=conversation.id,
            sender_type="patient",
            content=body,
            external_id=external_id,
            is_read=False
        )
        self.db.add(conv_msg)

        # 4. Save to PatientMessage audit log
        pat_msg = PatientMessage(
            practice_id=practice_id,
            patient_id=patient.id,
            message_type=MessageType.SMS,
            direction=MessageDirection.INBOUND,
            status=MessageStatus.DELIVERED,
            content=body,
            recipient_phone=to_phone,
            delivered_at=now
        )
        self.db.add(pat_msg)

        self.db.commit()
        return True
