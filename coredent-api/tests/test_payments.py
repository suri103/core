"""Tests for the Razorpay payment gateway endpoints (/payments/...)."""
import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config_simple import settings
from app.models.billing import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from app.models.processor_event import ProcessorEventStatus, ProcessorWebhookEvent

pytestmark = pytest.mark.asyncio

WEBHOOK_SECRET = "whsec_test_razorpay"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _refund_event(refund_id: str, payment_id: str, amount_paise: int) -> bytes:
    return json.dumps({
        "event": "refund.processed",
        "payload": {
            "refund": {
                "entity": {
                    "id": refund_id,
                    "payment_id": payment_id,
                    "amount": amount_paise,
                    "currency": "INR",
                    "status": "processed",
                }
            }
        },
    }).encode()


async def _create_paid_invoice(db_session, practice, patient, txn_id: str):
    invoice = Invoice(
        id=uuid.uuid4(),
        practice_id=practice.id,
        patient_id=patient.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        status=InvoiceStatus.PAID,
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        line_items=[],
    )
    db_session.add(invoice)
    await db_session.flush()
    payment = Payment(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        patient_id=patient.id,
        practice_id=practice.id,
        amount=Decimal("100.00"),
        refunded_amount=Decimal("0.00"),
        payment_method=PaymentMethod.UPI,
        transaction_id=txn_id,
        status=PaymentStatus.COMPLETED,
    )
    db_session.add(payment)
    await db_session.flush()
    return invoice, payment


class TestRazorpayAuth:
    async def test_order_requires_auth(self, client):
        response = await client.post(
            "/api/v1/payments/razorpay/order",
            json={"invoice_id": str(uuid.uuid4())},
        )
        assert response.status_code == 401

    async def test_verify_requires_auth(self, client):
        response = await client.post(
            "/api/v1/payments/razorpay/verify",
            json={
                "invoice_id": str(uuid.uuid4()),
                "razorpay_order_id": "order_x",
                "razorpay_payment_id": "pay_x",
                "razorpay_signature": "sig",
            },
        )
        assert response.status_code == 401

    async def test_order_fails_closed_without_credentials(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "")
        monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
        response = await client.post(
            "/api/v1/payments/razorpay/order",
            json={"invoice_id": str(uuid.uuid4())},
            headers=auth_headers,
        )
        assert response.status_code == 503


class TestRazorpayRefundWebhook:
    @pytest.fixture(autouse=True)
    def _webhook_secret(self, monkeypatch):
        monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)

    async def test_rejects_bad_signature(self, client):
        payload = _refund_event("rfnd_1", "pay_1", 10000)
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": "0" * 64},
        )
        assert response.status_code == 400

    async def test_fails_closed_without_secret(self, client, monkeypatch):
        monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
        payload = _refund_event("rfnd_1", "pay_1", 10000)
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert response.status_code == 400

    async def test_reconciles_full_refund(
        self, client, db_session, test_practice, test_patient
    ):
        invoice, payment = await _create_paid_invoice(
            db_session, test_practice, test_patient, "pay_reconcile_1"
        )

        payload = _refund_event("rfnd_full_1", "pay_reconcile_1", 10000)
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert response.status_code == 200, response.text

        await db_session.refresh(payment)
        await db_session.refresh(invoice)
        assert Decimal(str(payment.refunded_amount)) == Decimal("100.00")
        assert payment.status == PaymentStatus.REFUNDED

        event_row = (
            await db_session.execute(
                select(ProcessorWebhookEvent).where(
                    ProcessorWebhookEvent.event_id == "rfnd_full_1"
                )
            )
        ).scalar_one_or_none()
        assert event_row is not None
        assert event_row.status == ProcessorEventStatus.PROCESSED
        assert event_row.practice_id == test_practice.id
        assert invoice.status != InvoiceStatus.PAID

    async def test_duplicate_delivery_not_reapplied(
        self, client, db_session, test_practice, test_patient
    ):
        _, payment = await _create_paid_invoice(
            db_session, test_practice, test_patient, "pay_reconcile_2"
        )

        # A partial refund first...
        payload = _refund_event("rfnd_part_1", "pay_reconcile_2", 4000)
        first = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert first.status_code == 200

        # ...delivered twice must not double-apply.
        second = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert second.status_code == 200
        assert second.json().get("duplicate") is True

        await db_session.refresh(payment)
        # The point of this test is idempotency: the second delivery must not
        # double-apply. The status is the partial-refund state of the ledger row
        # (the handler sets PARTIALLY_REFUNDED for a partial refund).
        assert Decimal(str(payment.refunded_amount)) == Decimal("40.00")
        assert payment.status == PaymentStatus.PARTIALLY_REFUNDED

    async def test_unknown_payment_quarantined(self, client, db_session):
        payload = _refund_event("rfnd_orphan_1", "pay_never_seen", 10000)
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert response.status_code == 200

        event_row = (
            await db_session.execute(
                select(ProcessorWebhookEvent).where(
                    ProcessorWebhookEvent.event_id == "rfnd_orphan_1"
                )
            )
        ).scalar_one_or_none()
        assert event_row is not None
        assert event_row.status == ProcessorEventStatus.UNRECONCILED

    async def test_overrefund_quarantined(
        self, client, db_session, test_practice, test_patient
    ):
        _, payment = await _create_paid_invoice(
            db_session, test_practice, test_patient, "pay_reconcile_3"
        )

        payload = _refund_event("rfnd_over_1", "pay_reconcile_3", 15000)  # 150 > 100
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert response.status_code == 200

        await db_session.refresh(payment)
        assert Decimal(str(payment.refunded_amount)) == Decimal("0.00")
        event_row = (
            await db_session.execute(
                select(ProcessorWebhookEvent).where(
                    ProcessorWebhookEvent.event_id == "rfnd_over_1"
                )
            )
        ).scalar_one_or_none()
        assert event_row is not None
        assert event_row.status == ProcessorEventStatus.UNRECONCILED

    async def test_non_refund_events_recorded_ignored(self, client, db_session):
        payload = json.dumps({
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"id": "pay_ignored_1"}}},
        }).encode()
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": _sign(payload)},
        )
        assert response.status_code == 200
        assert response.json().get("ignored") is True
