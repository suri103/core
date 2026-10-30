"""
Payment Processing Service
Handles Stripe and Razorpay payment processing
"""

from typing import Optional, Dict, Any
from uuid import UUID
from decimal import Decimal, ROUND_HALF_UP
import asyncio
import logging
import hmac
import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import stripe as stripe_lib
import razorpay

# Explicit client timeout and retries for Stripe (M32)
stripe_lib.max_network_retries = 2
try:
    from stripe import RequestsClient
    stripe_lib.default_http_client = RequestsClient(timeout=30.0)
except Exception:
    pass

from app.core.config_simple import settings
from app.models.billing import (
    InvoiceStatus, Payment, PaymentMethod, PaymentStatus,
)
from app.models.user import User
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

_CENT = Decimal("0.01")

# Map provider method strings onto the PaymentMethod enum; anything unknown
# degrades to OTHER instead of raising an enum DataError mid-transaction.
_RAZORPAY_METHODS = {
    "card": PaymentMethod.CARD,
    "upi": PaymentMethod.UPI,
    "netbanking": PaymentMethod.OTHER,
    "wallet": PaymentMethod.OTHER,
    "emi": PaymentMethod.OTHER,
    "paylater": PaymentMethod.OTHER,
}


def _to_cents(amount: Any) -> int:
    """Convert a currency amount to cents/paise without float truncation.

    int(10.10 * 100) == 1009 due to float representation; Decimal arithmetic
    with ROUND_HALF_UP gives the correct 1010.
    """
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _from_cents(amount: Any) -> Decimal:
    """Convert provider cents/paise to a currency amount (no float hop)."""
    return (Decimal(str(amount)) / 100).quantize(_CENT)


class StripePaymentProcessor:
    """Handles Stripe payment processing"""

    @staticmethod
    async def create_payment_intent(
        db: AsyncSession,
        current_user: User,
        invoice_id: UUID,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent"""
        if not settings.STRIPE_API_KEY:
            raise ValueError("Stripe API key not configured")

        stripe_lib.api_key = settings.STRIPE_API_KEY

        # Get invoice
        invoice = await PaymentService.get_invoice(db, invoice_id, current_user.practice_id)
        if not invoice:
            raise ValueError("Invoice not found")

        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT):
            raise ValueError(f"Invoice is not payable (status: {invoice.status})")

        try:
            # Never allow the client to charge more than the invoice balance.
            balance_due = Decimal(str(invoice.balance_due))
            payment_amount = balance_due if amount is None else Decimal(str(amount))
            if payment_amount <= 0 or payment_amount > balance_due:
                raise ValueError("Payment amount must be greater than zero and no more than the invoice balance")

            # stripe-python is synchronous; offload to a thread so the event
            # loop is not blocked for the duration of the API call.
            intent = await asyncio.to_thread(
                stripe_lib.PaymentIntent.create,
                amount=_to_cents(payment_amount),  # Stripe uses cents
                currency="usd",
                metadata={
                    "invoice_id": str(invoice.id),
                    "patient_id": str(invoice.patient_id),
                    "practice_id": str(current_user.practice_id),
                },
                automatic_payment_methods={"enabled": True},
                description=f"Invoice #{invoice.invoice_number}",
            )

            logger.info(f"Created Stripe PaymentIntent: {intent.id}")

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": payment_amount,
                "currency": "usd",
            }

        except stripe_lib.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise

    @staticmethod
    async def handle_payment_succeeded(
        db: AsyncSession,
        payment_intent: Dict[str, Any],
    ) -> Optional[Payment]:
        """Handle successful Stripe payment"""
        invoice_id = payment_intent.get("metadata", {}).get("invoice_id")

        if not invoice_id:
            logger.warning("No invoice_id in payment intent metadata")
            return None

        try:
            invoice_uuid = UUID(invoice_id)

            # Idempotency: Stripe retries webhooks. A transaction_id row is
            # unique, and one row per transaction doubles as the race guard
            # (the loser hits the unique constraint below).
            metadata = payment_intent.get("metadata", {})
            practice_id = metadata.get("practice_id")
            if not practice_id:
                raise ValueError("Payment intent is missing practice metadata")

            existing = await PaymentService.get_payment(
                db, payment_intent["id"], UUID(practice_id)
            )
            if existing is not None:
                if existing.status == PaymentStatus.COMPLETED:
                    logger.info(f"Duplicate Stripe webhook ignored: {payment_intent['id']}")
                    return existing
                # A FAILED/PENDING record for this intent (e.g. earlier
                # payment_failed event) transitions instead of duplicating.
                return await PaymentService.update_payment_status(
                    db, existing.id, PaymentStatus.COMPLETED, UUID(practice_id)
                )

            invoice = await PaymentService.get_invoice(db, invoice_uuid, UUID(practice_id))
            if not invoice:
                raise ValueError("Invoice not found for payment practice")
            if invoice.status not in (InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE):
                raise ValueError(f"Invoice is not payable (status: {invoice.status})")

            paid_amount = _from_cents(payment_intent["amount"])
            balance_due = Decimal(str(invoice.balance_due))
            if paid_amount > balance_due:
                raise ValueError(
                    f"Payment {paid_amount} exceeds invoice balance {balance_due}"
                )

            # C2 FIX: payment record + amount-aware invoice transition commit
            # together — the old two-commit sequence could leave a PAID
            # invoice with no payment record (or vice versa) on a crash.
            payment = await PaymentService.create_payment_record(
                db=db,
                invoice_id=invoice.id,
                patient_id=invoice.patient_id,
                practice_id=UUID(practice_id),
                amount=paid_amount,
                payment_method=PaymentMethod.CARD,
                transaction_id=payment_intent["id"],
                status=PaymentStatus.COMPLETED,
                notes=f"Stripe payment: {payment_intent['id']}",
            )
            await PaymentService.apply_payment_transition(db, invoice.id, UUID(practice_id))
            try:
                await db.commit()
            except IntegrityError:
                # Concurrent webhook delivery won the insert race.
                await db.rollback()
                winner = await PaymentService.get_payment(
                    db, payment_intent["id"], UUID(practice_id)
                )
                if winner is not None:
                    logger.info(f"Concurrent Stripe webhook race lost, using winner: {payment_intent['id']}")
                    return winner
                raise

            await db.refresh(payment)
            logger.info(f"Processed successful Stripe payment: {payment_intent['id']}")
            return payment

        except Exception as e:
            logger.error(f"Error handling payment succeeded: {str(e)}")
            raise

    @staticmethod
    async def handle_payment_failed(
        db: AsyncSession,
        payment_intent: Dict[str, Any],
    ) -> Optional[Payment]:
        """Handle failed Stripe payment"""
        invoice_id = payment_intent.get("metadata", {}).get("invoice_id")

        if not invoice_id:
            logger.warning("No invoice_id in payment intent metadata")
            return None

        try:
            invoice_uuid = UUID(invoice_id)
            # F18 FIX: Pass practice_id from metadata to scope the invoice
            # lookup to the correct tenant. Previously this called
            # get_invoice without practice_id, allowing cross-tenant
            # failed-payment records on another practice's invoice.
            fail_metadata = payment_intent.get("metadata", {})
            fail_practice_id = fail_metadata.get("practice_id")
            if not fail_practice_id:
                raise ValueError("Failed payment is missing practice metadata")
            fail_practice_uuid = UUID(fail_practice_id)
            invoice = await PaymentService.get_invoice(
                db, invoice_uuid, fail_practice_uuid
            )

            if not invoice:
                logger.warning(f"Invoice not found: {invoice_id}")
                return None

            # One row per transaction: a succeeded-then-failed retry updates
            # the existing record's notes rather than inserting a duplicate.
            existing = await PaymentService.get_payment(
                db, payment_intent["id"], fail_practice_uuid
            )
            if existing is not None:
                logger.info(f"Transaction {payment_intent['id']} already recorded; skipping failed record")
                return existing

            # Create failed payment record (no invoice transition on failure)
            payment = await PaymentService.create_payment_record(
                db=db,
                invoice_id=invoice.id,
                patient_id=invoice.patient_id,
                practice_id=fail_practice_uuid,
                amount=_from_cents(payment_intent["amount"]),
                payment_method=PaymentMethod.CARD,
                transaction_id=payment_intent["id"],
                status=PaymentStatus.FAILED,
                notes=f"Failed: {payment_intent.get('last_payment_error', {}).get('message', 'Unknown error')}",
            )
            await db.commit()

            logger.info(f"Recorded failed Stripe payment: {payment_intent['id']}")
            return payment

        except Exception as e:
            logger.error(f"Error handling payment failed: {str(e)}")
            raise

    @staticmethod
    async def process_refund(
        db: AsyncSession,
        transaction_id: str,
        practice_id: UUID,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Process a Stripe refund (gateway + local ledger stay in sync)."""
        if not settings.STRIPE_API_KEY:
            raise ValueError("Stripe API key not configured")

        stripe_lib.api_key = settings.STRIPE_API_KEY

        try:
            # H5 FIX: the local ledger drives refund limits. Previously the
            # Stripe-side refund never touched local data at all.
            # H2 FIX: lock the payment row so two concurrent refunds serialize
            # (read-modify-write on refunded_amount was last-writer-wins).
            payment = await PaymentService.get_payment(
                db, transaction_id, practice_id, for_update=True
            )
            if not payment:
                raise ValueError("Payment not found")
            if payment.status not in (PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED):
                raise ValueError(f"Payment is not refundable (status: {payment.status})")

            already_refunded = Decimal(str(payment.refunded_amount or 0))
            refundable = Decimal(str(payment.amount)) - already_refunded
            refund_amount = refundable if amount is None else Decimal(str(amount)).quantize(_CENT)
            if refund_amount <= 0 or refund_amount > refundable:
                raise ValueError(
                    f"Refund amount must be > 0 and <= remaining refundable {refundable}"
                )

            refund_params = {"payment_intent": transaction_id}
            if amount:
                refund_params["amount"] = _to_cents(refund_amount)

            refund = await asyncio.to_thread(stripe_lib.Refund.create, **refund_params)

            payment.refunded_amount = already_refunded + refund_amount
            if refund_amount >= refundable:
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED
            await db.flush()
            # Re-open the invoice balance when the refund un-settles it.
            await PaymentService.refresh_invoice_status(
                db, payment.invoice_id, practice_id
            )
            await db.commit()

            logger.info(f"Processed Stripe refund: {refund.id}")

            return {
                "refund_id": refund.id,
                "amount": _from_cents(refund.amount),
                "status": refund.status,
            }

        except stripe_lib.error.StripeError as e:
            logger.error(f"Stripe refund error: {str(e)}")
            raise


class RazorpayPaymentProcessor:
    """Handles Razorpay payment processing"""

    @staticmethod
    def _get_client() -> razorpay.Client:
        """Get Razorpay client with explicit socket timeout."""
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise ValueError("Razorpay credentials not configured")

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        # Ensure underlying requests session enforces timeout (M32)
        orig_request = client.session.request

        def request_with_timeout(*args, **kwargs):
            kwargs.setdefault("timeout", 15.0)
            return orig_request(*args, **kwargs)

        client.session.request = request_with_timeout
        return client

    @staticmethod
    async def create_order(
        db: AsyncSession,
        current_user: User,
        invoice_id: UUID,
        amount: Optional[Decimal] = None,
        currency: str = "INR",
        receipt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Razorpay order"""
        client = RazorpayPaymentProcessor._get_client()

        # Get invoice
        invoice = await PaymentService.get_invoice(db, invoice_id, current_user.practice_id)
        if not invoice:
            raise ValueError("Invoice not found")

        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT):
            raise ValueError(f"Invoice is not payable (status: {invoice.status})")

        try:
            # F17 FIX: Cap the client-supplied amount at the invoice balance,
            # matching the Stripe path's validation. Previously a client could
            # pass an arbitrary amount for the Razorpay order (overpayment
            # accepted silently).
            balance_due = Decimal(str(invoice.balance_due))
            if amount is not None:
                payment_amount = Decimal(str(amount))
                if payment_amount <= 0 or payment_amount > balance_due:
                    raise ValueError(
                        "Payment amount must be greater than zero and no more than the invoice balance"
                    )
                order_amount = payment_amount
            else:
                order_amount = balance_due
            amount_paise = _to_cents(order_amount)

            # Create Razorpay order (sync SDK — offload to a thread)
            order = await asyncio.to_thread(client.order.create, {
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt or f"invoice_{invoice.id}",
                "payment_capture": 1,  # Auto-capture
                "notes": {
                    "invoice_id": str(invoice.id),
                    "patient_id": str(invoice.patient_id),
                    "practice_id": str(current_user.practice_id),
                },
            })

            logger.info(f"Created Razorpay order: {order['id']}")

            return {
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "receipt": order["receipt"],
                "key_id": settings.RAZORPAY_KEY_ID,
                "status": order["status"],
            }

        except Exception as e:
            logger.error(f"Razorpay order creation error: {str(e)}")
            raise

    @staticmethod
    async def verify_payment(
        db: AsyncSession,
        invoice_id: UUID,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        practice_id: UUID,
    ) -> Dict[str, Any]:
        """Verify a Razorpay payment signature"""
        client = RazorpayPaymentProcessor._get_client()

        try:
            # Verify payment signature
            params = f"{razorpay_order_id}|{razorpay_payment_id}"
            expected_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                params.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(expected_signature, razorpay_signature):
                raise ValueError("Invalid payment signature")

            # Idempotency: retries must not insert duplicate COMPLETED
            # payments for the same Razorpay transaction (unique
            # transaction_id backs this under concurrency).
            existing = await PaymentService.get_payment(
                db, razorpay_payment_id, practice_id
            )
            if existing and existing.status == PaymentStatus.COMPLETED:
                logger.info(f"Duplicate Razorpay payment ignored: {razorpay_payment_id}")
                return {
                    "payment_id": razorpay_payment_id,
                    "order_id": razorpay_order_id,
                    "amount": float(existing.amount),
                    "status": "captured",
                    "duplicate": True,
                }

            # Fetch payment details from Razorpay (sync SDK — offload)
            payment = await asyncio.to_thread(client.payment.fetch, razorpay_payment_id)

            # BUGFIX: validate the payment actually succeeded before marking
            # anything paid.
            if payment.get("status") not in ("authorized", "captured"):
                raise ValueError(f"Payment not successful (status: {payment.get('status')})")

            # Tenant scoping: when practice_id is supplied, refuse to touch
            # invoices belonging to another practice.
            invoice = await PaymentService.get_invoice(db, invoice_id, practice_id)
            if not invoice:
                raise ValueError("Invoice not found")
            if invoice.status not in (InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE):
                raise ValueError(f"Invoice is not payable (status: {invoice.status})")

            # M11 FIX: exact Decimal arithmetic on the recorded paise — the
            # old float `paid + 0.01 < balance` check absorbed a ₹0.99
            # shortfall as full settlement.
            paid_amount = _from_cents(payment["amount"])
            balance_due = Decimal(str(invoice.balance_due))
            if paid_amount > balance_due:
                raise ValueError(
                    f"Payment amount {paid_amount} exceeds invoice balance {balance_due}"
                )

            # Payment record + amount-aware invoice transition commit together.
            await PaymentService.create_payment_record(
                db=db,
                invoice_id=invoice.id,
                patient_id=invoice.patient_id,
                practice_id=practice_id,
                amount=paid_amount,
                payment_method=_RAZORPAY_METHODS.get(payment.get("method", "upi"), PaymentMethod.OTHER),
                transaction_id=razorpay_payment_id,
                status=PaymentStatus.COMPLETED,
                notes=f"Razorpay payment: {razorpay_payment_id}",
            )
            await PaymentService.apply_payment_transition(db, invoice.id, practice_id)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                logger.info(f"Concurrent Razorpay verification race lost: {razorpay_payment_id}")
                return {
                    "payment_id": razorpay_payment_id,
                    "order_id": razorpay_order_id,
                    "amount": paid_amount,
                    "status": "captured",
                    "duplicate": True,
                }

            logger.info(f"Verified Razorpay payment: {razorpay_payment_id}")

            return {
                "payment_id": razorpay_payment_id,
                "order_id": razorpay_order_id,
                "amount": paid_amount,
                "currency": payment.get("currency", "INR"),
                "status": "captured",
                "method": payment.get("method", "upi"),
            }

        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            raise

    @staticmethod
    async def process_refund(
        db: AsyncSession,
        payment_id: str,
        practice_id: UUID,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Process a Razorpay refund"""
        client = RazorpayPaymentProcessor._get_client()

        try:
            # Find the payment (H2 FIX: row lock for refund read-modify-write).
            payment = await PaymentService.get_payment(
                db, payment_id, practice_id, for_update=True
            )
            if not payment:
                raise ValueError("Payment not found")

            # H5 FIX: double-refund and partial-refund bookkeeping.
            if payment.status not in (PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED):
                raise ValueError(f"Payment is not refundable (status: {payment.status})")

            already_refunded = Decimal(str(payment.refunded_amount or 0))
            refundable = Decimal(str(payment.amount)) - already_refunded
            refund_amount = refundable if amount is None else Decimal(str(amount)).quantize(_CENT)
            if refund_amount <= 0 or refund_amount > refundable:
                raise ValueError(
                    f"Refund amount must be > 0 and <= remaining refundable {refundable}"
                )

            # Process refund
            refund_params = {"payment_id": payment_id, "amount": _to_cents(refund_amount)}
            refund = await asyncio.to_thread(client.refund.create, refund_params)

            # Record the refunded amount; only a FULL refund flips the status
            # (partial refunds previously erased the whole payment from
            # "collected" figures while the invoice stayed PAID).
            payment.refunded_amount = already_refunded + refund_amount
            if refund_amount >= refundable:
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED
            await db.flush()
            await PaymentService.refresh_invoice_status(
                db, payment.invoice_id, practice_id
            )
            await db.commit()

            logger.info(f"Processed Razorpay refund: {refund['id']}")

            return {
                "refund_id": refund["id"],
                "amount": _from_cents(refund["amount"]),
                "status": refund["status"],
            }

        except Exception as e:
            logger.error(f"Razorpay refund error: {str(e)}")
            raise


class WebhookProcessor:
    """Handles payment webhook processing"""

    @staticmethod
    def verify_stripe_signature(
        payload: bytes,
        sig_header: str,
    ) -> Dict[str, Any]:
        """Verify and parse Stripe webhook"""
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe webhook secret not configured")

        try:
            event = stripe_lib.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe_lib.error.SignatureVerificationError:
            raise ValueError("Invalid signature")

    @staticmethod
    def verify_razorpay_signature(
        body: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """Verify and parse Razorpay webhook"""
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            raise ValueError("Razorpay webhook secret not configured")

        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid webhook signature")

        payload = json.loads(body)
        return payload
