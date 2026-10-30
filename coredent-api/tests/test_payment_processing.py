"""Tests for payment_processing service with external calls mocked."""
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core import config_simple
from app.models.billing import InvoiceStatus, PaymentStatus
from app.services import payment_processing
from app.services.payment_processing import StripePaymentProcessor, WebhookProcessor
from app.services.payment_service import PaymentService


@pytest.mark.asyncio
async def test_create_payment_intent_success(monkeypatch):
    invoice = MagicMock()
    invoice.id = uuid4()
    invoice.patient_id = uuid4()
    invoice.practice_id = uuid4()
    invoice.balance_due = Decimal("123.45")
    invoice.status = InvoiceStatus.PENDING
    invoice.invoice_number = "INV-1"

    monkeypatch.setattr(config_simple.settings, "STRIPE_API_KEY", "sk_test")
    monkeypatch.setattr(PaymentService, "get_invoice", AsyncMock(return_value=invoice))

    mock_intent = MagicMock(id="pi_123", client_secret="secret_123")
    monkeypatch.setattr(
        payment_processing.stripe_lib.PaymentIntent,
        "create",
        MagicMock(return_value=mock_intent),
    )

    result = await StripePaymentProcessor.create_payment_intent(
        db=AsyncMock(),
        current_user=MagicMock(practice_id=invoice.practice_id),
        invoice_id=invoice.id,
    )
    assert result["payment_intent_id"] == "pi_123"
    assert result["amount"] == invoice.balance_due


@pytest.mark.asyncio
async def test_create_payment_intent_invoice_missing(monkeypatch):
    monkeypatch.setattr(config_simple.settings, "STRIPE_API_KEY", "sk_test")
    monkeypatch.setattr(PaymentService, "get_invoice", AsyncMock(return_value=None))

    with pytest.raises(ValueError):
        await StripePaymentProcessor.create_payment_intent(
            db=AsyncMock(),
            current_user=MagicMock(practice_id=uuid4()),
            invoice_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_handle_payment_succeeded(monkeypatch):
    invoice = MagicMock()
    invoice.id = uuid4()
    invoice.patient_id = uuid4()
    invoice.practice_id = uuid4()
    invoice.status = InvoiceStatus.PENDING
    invoice.balance_due = Decimal("10.00")

    payment = MagicMock()

    # The handler now performs scoped invoice and idempotency lookups, plus
    # an amount-aware invoice transition that commits atomically with the
    # payment record.
    monkeypatch.setattr(PaymentService, "get_invoice", AsyncMock(return_value=invoice))
    monkeypatch.setattr(PaymentService, "get_payment", AsyncMock(return_value=None))
    monkeypatch.setattr(
        PaymentService,
        "apply_payment_transition",
        AsyncMock(return_value=invoice),
    )
    monkeypatch.setattr(
        PaymentService,
        "create_payment_record",
        AsyncMock(return_value=payment),
    )

    payment_intent = {
        "id": "pi_123",
        "amount": 1000,
        "metadata": {
            "invoice_id": str(invoice.id),
            "practice_id": str(invoice.practice_id),
        },
    }

    result = await StripePaymentProcessor.handle_payment_succeeded(
        AsyncMock(), payment_intent
    )
    assert result is payment
    PaymentService.create_payment_record.assert_called_once()
    PaymentService.apply_payment_transition.assert_called_once()


@pytest.mark.asyncio
async def test_handle_payment_failed(monkeypatch):
    invoice = MagicMock()
    invoice.id = uuid4()
    invoice.patient_id = uuid4()
    invoice.practice_id = uuid4()

    payment = MagicMock()

    monkeypatch.setattr(PaymentService, "get_invoice", AsyncMock(return_value=invoice))
    # No prior record for this transaction id -> a FAILED row is created.
    monkeypatch.setattr(PaymentService, "get_payment", AsyncMock(return_value=None))
    monkeypatch.setattr(
        PaymentService,
        "create_payment_record",
        AsyncMock(return_value=payment),
    )

    payment_intent = {
        "id": "pi_123",
        "amount": 500,
        "metadata": {
            "invoice_id": str(invoice.id),
            "practice_id": str(invoice.practice_id),
        },
        "last_payment_error": {"message": "Declined"},
    }

    result = await StripePaymentProcessor.handle_payment_failed(
        AsyncMock(), payment_intent
    )
    assert result is payment
    PaymentService.create_payment_record.assert_called_once()


def test_process_refund(monkeypatch):
    monkeypatch.setattr(config_simple.settings, "STRIPE_API_KEY", "sk_test")

    # H5: refunds are ledger-driven — a COMPLETED local payment record with
    # refundable balance must exist before the gateway call.
    practice_id = uuid4()
    local_payment = MagicMock()
    local_payment.id = uuid4()
    local_payment.status = PaymentStatus.COMPLETED
    local_payment.amount = Decimal("10.00")
    local_payment.refunded_amount = Decimal("0")
    local_payment.invoice_id = uuid4()
    monkeypatch.setattr(
        PaymentService,
        "get_payment",
        AsyncMock(return_value=local_payment),
    )
    monkeypatch.setattr(
        PaymentService,
        "refresh_invoice_status",
        AsyncMock(return_value=None),
    )

    mock_refund = MagicMock(id="re_1", amount=500, status="succeeded")
    monkeypatch.setattr(
        payment_processing.stripe_lib,
        "Refund",
        MagicMock(create=MagicMock(return_value=mock_refund)),
    )

    result = asyncio.run(
        StripePaymentProcessor.process_refund(
            AsyncMock(), "pi_123", practice_id, amount=5.0
        )
    )
    assert result["refund_id"] == "re_1"
    assert local_payment.refunded_amount == Decimal("5.00")
    # process_refund marks a partial refund PARTIALLY_REFUNDED (see the H5 block
    # in payment_processing.process_refund). The previous expectation of
    # COMPLETED predated that ledger member.
    assert local_payment.status == PaymentStatus.PARTIALLY_REFUNDED


def test_verify_stripe_signature(monkeypatch):
    monkeypatch.setattr(config_simple.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    mock_event = {"id": "evt_1"}
    monkeypatch.setattr(
        payment_processing.stripe_lib.Webhook,
        "construct_event",
        MagicMock(return_value=mock_event),
    )

    result = WebhookProcessor.verify_stripe_signature(b"payload", "sig")
    assert result == mock_event


def test_verify_stripe_signature_invalid(monkeypatch):
    monkeypatch.setattr(config_simple.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    def _raise(*args, **kwargs):
        raise payment_processing.stripe_lib.error.SignatureVerificationError(
            message="bad", http_body=b"", sig_header="sig"
        )

    monkeypatch.setattr(
        payment_processing.stripe_lib.Webhook,
        "construct_event",
        MagicMock(side_effect=_raise),
    )
    with pytest.raises(ValueError):
        WebhookProcessor.verify_stripe_signature(b"payload", "sig")
