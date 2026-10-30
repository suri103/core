"""
Email Service
SendGrid and AWS SES integration for transactional emails
"""

import os
import logging
import hashlib
from typing import Optional, List, Dict, Any
from enum import Enum
from email.message import EmailMessage
from uuid import uuid4
import asyncio
import html as html_module

logger = logging.getLogger(__name__)


def build_outbound_message_id(idempotency_key: Optional[str] = None) -> str:
    """Build one stable, RFC 5322 Message-ID for a logical delivery.

    Caller keys are hashed before entering mail headers so internal identifiers
    are not disclosed to recipients or providers. When no durable key exists,
    the caller gets a fresh identity for this one send invocation.
    """
    identity = idempotency_key or uuid4().hex
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    domain = os.getenv("EMAIL_MESSAGE_ID_DOMAIN", "coredent.app").strip().lower()
    if not domain or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for ch in domain):
        domain = "coredent.app"
    return f"<{digest}@{domain}>"


def log_email_failure(exc: Exception, kind: str, recipient: str) -> None:
    """
    SECURITY: Centralized email-failure reporting.

    A failed transactional email (password reset, email verification,
    payment receipt) is a HIPAA notification failure: the user thinks
    something happened that did not.  We log to Sentry at error level
    so the on-call engineer can act on it.  We do NOT include the raw
    email body or PHI, and the recipient's DNS domain is enough to tell a
    provider outage from a bad address - the local part (itself a HIPAA
    identifier) is never logged.
    """
    recipient_domain = recipient.split("@")[-1] if "@" in recipient else "unknown"
    logger.error(
        f"Failed to send {kind} email to a {recipient_domain} recipient: {exc}",
        extra={
            "event_type": "email_failure",
            "email_kind": kind,
            "recipient_domain": recipient_domain,
        },
    )
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("event_type", "email_failure")
            scope.set_tag("email_kind", kind)
            scope.set_context(
                "email_failure",
                {
                    "kind": kind,
                    "recipient_domain": (
                        recipient.split("@")[-1] if "@" in recipient else "unknown"
                    ),
                    "error": str(exc),
                },
            )
            sentry_sdk.capture_exception(exc)
    except Exception:
        # Sentry is optional; never let a logging error break the request.
        pass


class EmailProvider(str, Enum):
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"
    SMTP = "smtp"
    CONSOLE = "console"  # For development


class EmailService:
    """
    Email service supporting multiple providers:
    - SendGrid
    - AWS SES
    - Console (development)
    """

    def __init__(self, provider: Optional[EmailProvider] = None):
        raw_provider = os.getenv(
            "EMAIL_PROVIDER",
            "smtp" if os.getenv("ENVIRONMENT", "development").strip().lower() == "production" else "console",
        ).strip().lower()
        self.provider = provider or EmailProvider(raw_provider)
        self.from_email = os.getenv("EMAIL_FROM", os.getenv("SMTP_FROM", "noreply@coredent.app"))
        self.from_name = os.getenv("EMAIL_FROM_NAME", os.getenv("SMTP_FROM_NAME", "CoreDent"))

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        template_id: Optional[str] = None,
        dynamic_template_data: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email with a stable identity for this logical delivery."""
        recipients = [to] if isinstance(to, str) else to
        outbound_message_id = build_outbound_message_id(idempotency_key)

        email_data = {
            "from": f"{self.from_name} <{self.from_email}>",
            "to": recipients,
            "subject": subject,
            "html": html_content,
            "text": text_content,
            "attachments": attachments,
            "outbound_message_id": outbound_message_id,
        }

        if self.provider == EmailProvider.SENDGRID:
            return await self._send_sendgrid(email_data, template_id, dynamic_template_data)
        elif self.provider == EmailProvider.AWS_SES:
            return await self._send_aws_ses(email_data)
        elif self.provider == EmailProvider.SMTP:
            return await self._send_smtp(email_data)
        elif self.provider == EmailProvider.CONSOLE:
            return await self._send_console(email_data)
        raise RuntimeError(f"Unsupported email provider: {self.provider}")

    async def _send_sendgrid(
        self,
        email_data: Dict[str, Any],
        template_id: Optional[str],
        dynamic_template_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Send email via SendGrid"""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Header, Mail

            sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))

            message = Mail(
                from_email=email_data["from"],
                to_emails=email_data["to"],
                subject=email_data["subject"],
            )

            if template_id:
                message.template_id = template_id
                message.dynamic_template_data = dynamic_template_data or {}

            if email_data.get("html"):
                message.html_content = email_data["html"]
            if email_data.get("text"):
                message.content = [
                    {"type": "text/plain", "value": email_data["text"]}
                ]
            message.add_header(
                Header("Message-ID", email_data["outbound_message_id"])
            )

            response = await asyncio.to_thread(sg.send, message)

            logger.info(f"SendGrid email sent successfully: {response.status_code}")
            return {
                "success": True,
                "provider": "sendgrid",
                "outbound_message_id": email_data["outbound_message_id"],
                "provider_message_id": response.headers.get("x-message-id"),
                "status_code": response.status_code,
            }
        except Exception as e:
            logger.error(f"SendGrid error: {str(e)}")
            raise

    async def _send_aws_ses(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send an RFC 5322 message via SES while preserving Message-ID."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            ses_client = boto3.client(
                "ses",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )

            message = self._build_mime_message(email_data)
            response = await asyncio.to_thread(
                ses_client.send_raw_email,
                Source=email_data["from"],
                Destinations=email_data["to"],
                RawMessage={"Data": message.as_bytes()},
            )

            logger.info("AWS SES email sent successfully")
            return {
                "success": True,
                "provider": "aws_ses",
                "outbound_message_id": email_data["outbound_message_id"],
                "provider_message_id": response["MessageId"],
            }
        except ClientError as e:
            logger.error(f"AWS SES error: {str(e)}")
            raise

    @staticmethod
    def _build_mime_message(email_data: Dict[str, Any]) -> EmailMessage:
        """Create the same MIME envelope for SMTP and SES raw delivery."""
        message = EmailMessage()
        message["From"] = email_data["from"]
        message["To"] = ", ".join(email_data["to"])
        message["Subject"] = email_data["subject"]
        message["Message-ID"] = email_data["outbound_message_id"]
        message.set_content(email_data.get("text") or "")
        if email_data.get("html"):
            message.add_alternative(email_data["html"], subtype="html")
        return message

    async def _send_smtp(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send transactional email through the configured SMTP server."""
        import smtplib
        import ssl

        message = self._build_mime_message(email_data)
        host = os.getenv("SMTP_HOST", "")
        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USER", "")
        password = os.getenv("SMTP_PASSWORD", "")

        def send_message():
            tls_context = ssl.create_default_context()
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=20, context=tls_context) as client:
                    if username:
                        client.login(username, password)
                    client.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=20) as client:
                    client.ehlo()
                    if port == 587:
                        client.starttls(context=tls_context)
                        client.ehlo()
                    if username:
                        client.login(username, password)
                    client.send_message(message)

        await asyncio.to_thread(send_message)
        return {
            "success": True,
            "provider": "smtp",
            "outbound_message_id": email_data["outbound_message_id"],
            "provider_message_id": None,
        }

    async def _send_console(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Log email to console (development only)."""
        if os.getenv("ENVIRONMENT", "development").strip().lower() == "production":
            raise RuntimeError("Console email delivery is disabled in production")
        logger.info("=" * 50)
        logger.info("📧 EMAIL (Development Mode)")
        logger.info("=" * 50)
        logger.info(f"From: {email_data['from']}")
        logger.info(f"To: {', '.join(email_data['to'])}")
        logger.info(f"Subject: {email_data['subject']}")
        logger.info(f"Message-ID: {email_data['outbound_message_id']}")
        if email_data.get("text"):
            logger.info(f"Body: {email_data['text'][:200]}...")
        logger.info("=" * 50)

        return {
            "success": True,
            "provider": "console",
            "outbound_message_id": email_data["outbound_message_id"],
            "provider_message_id": None,
        }

    # Convenience methods for common emails

    async def send_welcome_email(self, to: str, first_name: str) -> Dict[str, Any]:
        """Send welcome email to new patients"""
        safe_first_name = html_module.escape(first_name)
        return await self.send_email(
            to=to,
            subject="Welcome to CoreDent!",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Welcome to CoreDent, {safe_first_name}!</h1>
                    <p>Thank you for choosing CoreDent for your dental care needs.</p>
                    <p>We're excited to have you as a patient!</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        This email was sent by CoreDent Dental Practice Management
                    </p>
                </body>
            </html>
            """,
            text_content=f"Welcome to CoreDent, {safe_first_name}! Thank you for choosing us.",
        )

    async def send_appointment_reminder(
        self,
        to: str,
        patient_name: str,
        appointment_date: str,
        appointment_time: str,
        dentist_name: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send appointment reminder"""
        safe_patient_name = html_module.escape(patient_name)
        safe_appointment_date = html_module.escape(appointment_date)
        safe_appointment_time = html_module.escape(appointment_time)
        safe_dentist_name = html_module.escape(dentist_name)
        return await self.send_email(
            to=to,
            subject="Appointment Reminder - CoreDent",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Appointment Reminder</h1>
                    <p>Dear {safe_patient_name},</p>
                    <p>This is a reminder about your upcoming dental appointment:</p>
                    <ul>
                        <li><strong>Date:</strong> {safe_appointment_date}</li>
                        <li><strong>Time:</strong> {safe_appointment_time}</li>
                        <li><strong>Dentist:</strong> {safe_dentist_name}</li>
                    </ul>
                    <p>Please arrive 15 minutes early.</p>
                    <p>Need to reschedule? Please call us.</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        CoreDent Dental Practice Management
                    </p>
                </body>
            </html>
            """,
            idempotency_key=idempotency_key,
        )

    async def send_appointment_confirmation(
        self,
        to: str,
        patient_name: str,
        appointment_date: str,
        appointment_time: str,
        procedure: str,
    ) -> Dict[str, Any]:
        """Send appointment confirmation"""
        safe_patient_name = html_module.escape(patient_name)
        safe_appointment_date = html_module.escape(appointment_date)
        safe_appointment_time = html_module.escape(appointment_time)
        safe_procedure = html_module.escape(procedure)
        return await self.send_email(
            to=to,
            subject="Appointment Confirmed - CoreDent",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Appointment Confirmed ✅</h1>
                    <p>Dear {safe_patient_name},</p>
                    <p>Your appointment has been confirmed:</p>
                    <ul>
                        <li><strong>Date:</strong> {safe_appointment_date}</li>
                        <li><strong>Time:</strong> {safe_appointment_time}</li>
                        <li><strong>Procedure:</strong> {safe_procedure}</li>
                    </ul>
                    <p>We look forward to seeing you!</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        CoreDent Dental Practice Management
                    </p>
                </body>
            </html>
            """,
        )

    async def send_insurance_claim_submitted(
        self,
        to: str,
        patient_name: str,
        claim_number: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Send insurance claim submission notification"""
        safe_patient_name = html_module.escape(patient_name)
        safe_claim_number = html_module.escape(claim_number)
        return await self.send_email(
            to=to,
            subject=f"Insurance Claim Submitted - {safe_claim_number}",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Insurance Claim Submitted</h1>
                    <p>Dear {safe_patient_name},</p>
                    <p>Your insurance claim has been submitted:</p>
                    <ul>
                        <li><strong>Claim Number:</strong> {safe_claim_number}</li>
                        <li><strong>Amount:</strong> ${amount:.2f}</li>
                    </ul>
                    <p>We'll notify you once we receive a response from your insurance.</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        CoreDent Dental Practice Management
                    </p>
                </body>
            </html>
            """,
        )

    # ==================== Subscription Email Templates ====================

    async def send_subscription_welcome(
        self,
        to: str,
        customer_name: str,
        plan_name: str,
        amount: float,
        interval: str,
        trial_end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send welcome email for new subscription"""
        trial_text = (
            f"<p>Your free trial ends on <strong>{trial_end_date}</strong>. "
            f"You will be charged automatically after the trial period.</p>"
            if trial_end_date
            else "<p>Your subscription is now active.</p>"
        )
        return await self.send_email(
            to=to,
            subject=f"Welcome to {plan_name} - CoreDent",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Welcome to CoreDent! 🎉</h1>
                    </div>
                    <div style="padding: 30px;">
                        <p>Dear {customer_name},</p>
                        <p>Thank you for subscribing to <strong>{plan_name}</strong>!</p>
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="margin-top: 0;">Subscription Details</h3>
                            <ul style="list-style: none; padding: 0;">
                                <li style="padding: 8px 0;"><strong>Plan:</strong> {plan_name}</li>
                                <li style="padding: 8px 0;"><strong>Amount:</strong> ${amount:.2f}/{interval}</li>
                                <li style="padding: 8px 0;"><strong>Status:</strong> <span style="color: #28a745;">Active</span></li>
                            </ul>
                        </div>
                        {trial_text}
                        <p>You can manage your subscription anytime from your account settings.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            CoreDent Dental Practice Management<br>
                            If you have any questions, please contact support.
                        </p>
                    </div>
                </body>
            </html>
            """,
            text_content=f"Welcome to CoreDent! You've subscribed to {plan_name} at ${amount:.2f}/{interval}.",
        )

    async def send_payment_receipt(
        self,
        to: str,
        customer_name: str,
        amount: float,
        invoice_number: str,
        payment_date: str,
        plan_name: str,
    ) -> Dict[str, Any]:
        """Send payment receipt email"""
        return await self.send_email(
            to=to,
            subject=f"Payment Receipt - Invoice {invoice_number}",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #28a745; padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Payment Successful ✅</h1>
                    </div>
                    <div style="padding: 30px;">
                        <p>Dear {customer_name},</p>
                        <p>We've received your payment. Here's your receipt:</p>
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="margin-top: 0;">Receipt Details</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 8px 0;"><strong>Invoice Number:</strong></td><td>{invoice_number}</td></tr>
                                <tr><td style="padding: 8px 0;"><strong>Amount Paid:</strong></td><td style="color: #28a745; font-weight: bold;">${amount:.2f}</td></tr>
                                <tr><td style="padding: 8px 0;"><strong>Payment Date:</strong></td><td>{payment_date}</td></tr>
                                <tr><td style="padding: 8px 0;"><strong>Plan:</strong></td><td>{plan_name}</td></tr>
                            </table>
                        </div>
                        <p>Thank you for your payment. Your subscription remains active.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            CoreDent Dental Practice Management
                        </p>
                    </div>
                </body>
            </html>
            """,
            text_content=f"Payment received: ${amount:.2f} for invoice {invoice_number}. Thank you!",
        )

    async def send_payment_failed(
        self,
        to: str,
        customer_name: str,
        amount: float,
        error_message: str,
        retry_date: str,
        attempt_number: int,
        max_attempts: int,
    ) -> Dict[str, Any]:
        """Send payment failure notification (dunning email)"""
        urgency_color = "#dc3545" if attempt_number >= 3 else "#ffc107"
        return await self.send_email(
            to=to,
            subject="⚠️ Payment Failed - Action Required",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: {urgency_color}; padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Payment Failed ⚠️</h1>
                    </div>
                    <div style="padding: 30px;">
                        <p>Dear {customer_name},</p>
                        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                            <p style="margin: 0;"><strong>Important:</strong> We were unable to process your subscription payment.</p>
                        </div>
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <table style="width: 100%;">
                                <tr><td style="padding: 8px 0;"><strong>Amount:</strong></td><td>${amount:.2f}</td></tr>
                                <tr><td style="padding: 8px 0;"><strong>Attempt:</strong></td><td>{attempt_number} of {max_attempts}</td></tr>
                                <tr><td style="padding: 8px 0;"><strong>Next Retry:</strong></td><td>{retry_date}</td></tr>
                                <tr><td style="padding: 8px 0;"><strong>Error:</strong></td><td style="color: #dc3545;">{error_message}</td></tr>
                            </table>
                        </div>
                        <p><strong>What you need to do:</strong></p>
                        <ol>
                            <li>Check your payment method is still valid</li>
                            <li>Ensure sufficient funds are available</li>
                            <li>Update your payment method in account settings if needed</li>
                        </ol>
                        <p style="color: #666;">If we cannot process payment after {max_attempts} attempts, your subscription will be canceled.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            CoreDent Dental Practice Management
                        </p>
                    </div>
                </body>
            </html>
            """,
            text_content=f"Payment failed: ${amount:.2f}. Attempt {attempt_number}/{max_attempts}. Next retry: {retry_date}. Error: {error_message}",
        )

    async def send_trial_expiring(
        self,
        to: str,
        customer_name: str,
        plan_name: str,
        trial_end_date: str,
        days_remaining: int,
        amount: float,
        interval: str,
    ) -> Dict[str, Any]:
        """Send trial expiration warning email"""
        return await self.send_email(
            to=to,
            subject=f"Your {plan_name} Trial Ends in {days_remaining} Days",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Trial Ending Soon ⏰</h1>
                    </div>
                    <div style="padding: 30px;">
                        <p>Dear {customer_name},</p>
                        <p>Your free trial of <strong>{plan_name}</strong> is ending soon!</p>
                        <div style="background: #e7f3ff; border-left: 4px solid #0066cc; padding: 20px; margin: 20px 0;">
                            <h3 style="margin-top: 0;">Trial Details</h3>
                            <ul style="list-style: none; padding: 0;">
                                <li style="padding: 8px 0;"><strong>Days Remaining:</strong> {days_remaining}</li>
                                <li style="padding: 8px 0;"><strong>Trial Ends:</strong> {trial_end_date}</li>
                                <li style="padding: 8px 0;"><strong>After Trial:</strong> ${amount:.2f}/{interval}</li>
                            </ul>
                        </div>
                        <p><strong>What happens next?</strong></p>
                        <ul>
                            <li>Your subscription will automatically convert to a paid plan</li>
                            <li>Your payment method will be charged ${amount:.2f}</li>
                            <li>You'll continue to have full access to all features</li>
                        </ul>
                        <p>No action is needed - we'll handle everything automatically!</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            CoreDent Dental Practice Management
                        </p>
                    </div>
                </body>
            </html>
            """,
            text_content=f"Your {plan_name} trial ends in {days_remaining} days. After trial: ${amount:.2f}/{interval}.",
        )

    async def send_subscription_canceled(
        self,
        to: str,
        customer_name: str,
        plan_name: str,
        cancellation_date: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send subscription cancellation confirmation"""
        safe_reason = html_module.escape(reason) if reason else ""
        reason_text = f"<p><strong>Reason:</strong> {safe_reason}</p>" if safe_reason else ""
        return await self.send_email(
            to=to,
            subject=f"Subscription Canceled - {plan_name}",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #6c757d; padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Subscription Canceled</h1>
                    </div>
                    <div style="padding: 30px;">
                        <p>Dear {customer_name},</p>
                        <p>Your subscription to <strong>{plan_name}</strong> has been canceled.</p>
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <ul style="list-style: none; padding: 0;">
                                <li style="padding: 8px 0;"><strong>Cancellation Date:</strong> {cancellation_date}</li>
                                <li style="padding: 8px 0;"><strong>Access Until:</strong> End of current billing period</li>
                            </ul>
                        </div>
                        {reason_text}
                        <p>We're sorry to see you go! If you change your mind, you can resubscribe anytime.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            CoreDent Dental Practice Management
                        </p>
                    </div>
                </body>
            </html>
            """,
            text_content=f"Your {plan_name} subscription has been canceled. Access continues until end of billing period.",
        )


# Singleton instance
email_service = EmailService()


# ==================== Module-level convenience functions ====================
# These are called from endpoint modules and patched directly in tests.

async def send_payment_confirmation_email(
    to_email: str,
    amount: float,
    currency: str = "usd",
    payment_id: Optional[Any] = None,
    description: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Send a payment confirmation email.

    Thin module-level wrapper used by the Stripe webhook handler. Delegates to
    the singleton EmailService. Called with minimal context (no customer name
    or invoice number from Stripe payloads), so we render a generic receipt.
    """
    try:
        # SECURITY: description may arrive from Stripe metadata (user-
        # influenced in self-serve signup) — escape before interpolating
        # into the HTML body.
        safe_description = html_module.escape(description or "")
        return await email_service.send_email(
            to=to_email,
            subject=f"Payment Received - ${amount:.2f} {currency.upper()}",
            html_content=(
                "<html><body style='font-family: Arial, sans-serif;'>"
                "<h2>Payment Received</h2>"
                f"<p>We've successfully processed your payment of "
                f"<strong>${amount:.2f} {currency.upper()}</strong>.</p>"
                + (f"<p>{safe_description}</p>" if safe_description else "")
                + (f"<p>Reference: {payment_id}</p>" if payment_id else "")
                + "<p>Thank you for your business.</p>"
                "<hr><p style='color:#666;font-size:12px;'>"
                "CoreDent Dental Practice Management</p>"
                "</body></html>"
            ),
            text_content=(
                f"Payment received: ${amount:.2f} {currency.upper()}."
                + (f" Reference: {payment_id}." if payment_id else "")
                + " Thank you."
            ),
        )
    except Exception as exc:
        log_email_failure(exc, "payment_confirmation", to_email)
        return {"status": "error", "error": str(exc)}
