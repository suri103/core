"""
SMS Service
Twilio integration for SMS messaging
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class SMSProvider(str, Enum):
    TWILIO = "twilio"
    CONSOLE = "console"  # For development


class SMSService:
    """
    SMS service supporting multiple providers:
    - Twilio
    - Console (development)
    """

    def __init__(self, provider: Optional[SMSProvider] = None):
        raw_provider = os.getenv(
            "SMS_PROVIDER",
            "twilio" if os.getenv("ENVIRONMENT", "development").strip().lower() == "production" else "console",
        ).strip().lower()
        self.provider = provider or SMSProvider(raw_provider)
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
        self.client = None
        self._configuration_error = None

        # Initialize Twilio client if credentials are available
        if self.provider == SMSProvider.TWILIO:
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")

            if account_sid and auth_token:
                try:
                    from twilio.rest import Client
                    from twilio.http.http_client import TwilioHttpClient
                    timeout = float(os.getenv("TWILIO_TIMEOUT", "10.0"))
                    http_client = TwilioHttpClient(timeout=timeout)
                    self.client = Client(account_sid, auth_token, http_client=http_client)
                    logger.info("Twilio SMS client initialized successfully")
                except ImportError:
                    self._configuration_error = "Twilio library is not installed"
                    logger.error(self._configuration_error)
                except Exception as e:
                    self._configuration_error = "Twilio client initialization failed"
                    logger.error("Failed to initialize Twilio client: %s", e)
            else:
                self._configuration_error = "Twilio credentials are not configured"
                logger.error(self._configuration_error)

    async def send_sms(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an SMS using the configured provider
        
        Args:
            to: Phone number in E.164 format (e.g., +1234567890)
            message: SMS message content (max 160 chars for single SMS)
            media_url: Optional URL for MMS media
        
        Returns:
            Dict with success status, provider, message_id, etc.
        """
        if not to or not message:
            return {"success": False, "provider": self.provider.value, "error": "Recipient and message are required"}
        if not to.startswith('+'):
            logger.warning("Phone number should be in E.164 format")

        if self.provider == SMSProvider.TWILIO:
            if not self.client:
                return {"success": False, "provider": "twilio", "error": self._configuration_error or "SMS provider is unavailable"}
            return await self._send_twilio(to, message, media_url)
        if self.provider == SMSProvider.CONSOLE:
            if os.getenv("ENVIRONMENT", "development").strip().lower() == "production":
                return {"success": False, "provider": "console", "error": "Console SMS delivery is disabled in production"}
            return await self._send_console(to, message, media_url)
        return {"success": False, "provider": str(self.provider), "error": "Unsupported SMS provider"}

    async def _send_twilio(
        self,
        to: str,
        message: str,
        media_url: Optional[str],
    ) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        try:
            params = {
                "to": to,
                "from_": self.from_number,
                "body": message
            }

            if media_url:
                params["media_url"] = [media_url]

            import asyncio
            message_obj = await asyncio.to_thread(self.client.messages.create, **params)

            logger.info(f"Twilio SMS sent successfully: {message_obj.sid}")
            return {
                "success": True,
                "provider": "twilio",
                "message_id": message_obj.sid,
                "status": message_obj.status,
                "to": message_obj.to,
                "from": message_obj.from_,
                "cost": message_obj.price,
                "currency": message_obj.price_unit,
                "segments": message_obj.num_segments,
            }
        except Exception as e:
            logger.error(f"Twilio error: {str(e)}")
            return {
                "success": False,
                "provider": "twilio",
                "error": "SMS delivery failed",
            }

    async def _send_console(
        self,
        to: str,
        message: str,
        media_url: Optional[str],
    ) -> Dict[str, Any]:
        """Log SMS to console (development)"""
        logger.info("=" * 60)
        logger.info("📱 SMS (Development Mode)")
        logger.info("=" * 60)
        logger.info(f"From: {self.from_number}")
        logger.info(f"To: {to}")
        logger.info(f"Message: {message}")
        if media_url:
            logger.info(f"Media: {media_url}")
        logger.info(f"Length: {len(message)} characters")
        logger.info(f"Segments: {(len(message) // 160) + 1}")
        logger.info("=" * 60)

        return {
            "success": True,
            "provider": "console",
            "message_id": f"dev-sms-{datetime.now(timezone.utc).timestamp()}",
            "status": "sent",
            "to": to,
            "from": self.from_number,
            "cost": "0.00",
            "currency": "USD",
            "segments": (len(message) // 160) + 1,
        }

    # Convenience methods for common SMS types

    async def send_appointment_reminder(
        self,
        to: str,
        patient_name: str,
        appointment_date: str,
        appointment_time: str,
        practice_name: str = "CoreDent",
    ) -> Dict[str, Any]:
        """Send appointment reminder SMS"""
        message = (
            f"Hi {patient_name}, reminder: You have an appointment at "
            f"{practice_name} on {appointment_date} at {appointment_time}. "
            f"Reply CONFIRM to confirm or call us to reschedule."
        )
        return await self.send_sms(to=to, message=message)

    async def send_appointment_confirmation(
        self,
        to: str,
        patient_name: str,
        appointment_date: str,
        appointment_time: str,
        practice_name: str = "CoreDent",
    ) -> Dict[str, Any]:
        """Send appointment confirmation SMS"""
        message = (
            f"Hi {patient_name}, your appointment at {practice_name} is "
            f"confirmed for {appointment_date} at {appointment_time}. "
            f"See you then!"
        )
        return await self.send_sms(to=to, message=message)

    async def send_appointment_cancellation(
        self,
        to: str,
        patient_name: str,
        appointment_date: str,
        practice_name: str = "CoreDent",
    ) -> Dict[str, Any]:
        """Send appointment cancellation SMS"""
        message = (
            f"Hi {patient_name}, your appointment at {practice_name} on "
            f"{appointment_date} has been cancelled. Call us to reschedule."
        )
        return await self.send_sms(to=to, message=message)

    async def send_recall_reminder(
        self,
        to: str,
        patient_name: str,
        months_since_visit: int,
        practice_name: str = "CoreDent",
        practice_phone: str = "",
    ) -> Dict[str, Any]:
        """Send recall reminder SMS"""
        message = (
            f"Hi {patient_name}, it's been {months_since_visit} months since "
            f"your last visit to {practice_name}. Time for a checkup! "
            f"Call {practice_phone} to schedule."
        )
        return await self.send_sms(to=to, message=message)

    async def send_payment_reminder(
        self,
        to: str,
        patient_name: str,
        amount: float,
        due_date: str,
        practice_name: str = "CoreDent",
    ) -> Dict[str, Any]:
        """Send payment reminder SMS"""
        message = (
            f"Hi {patient_name}, friendly reminder: You have a balance of "
            f"${amount:.2f} due on {due_date} at {practice_name}. "
            f"Pay online or call us."
        )
        return await self.send_sms(to=to, message=message)

    async def send_insurance_update(
        self,
        to: str,
        patient_name: str,
        claim_status: str,
        practice_name: str = "CoreDent",
    ) -> Dict[str, Any]:
        """Send insurance claim update SMS"""
        message = (
            f"Hi {patient_name}, update on your insurance claim at "
            f"{practice_name}: {claim_status}. "
            f"Call us if you have questions."
        )
        return await self.send_sms(to=to, message=message)

    async def send_verification_code(
        self,
        to: str,
        code: str,
        practice_name: str = "CoreDent",
    ) -> Dict[str, Any]:
        """Send verification code SMS"""
        message = (
            f"Your {practice_name} verification code is: {code}. "
            f"This code expires in 10 minutes. Do not share this code."
        )
        return await self.send_sms(to=to, message=message)

    def get_status(self) -> Dict[str, Any]:
        """Get SMS service status"""
        return {
            "provider": self.provider.value,
            "configured": self.client is not None if self.provider == SMSProvider.TWILIO else True,
            "from_number": self.from_number,
        }


# Singleton instance
sms_service = SMSService()
