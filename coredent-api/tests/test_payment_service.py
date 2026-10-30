"""Unit tests for payment service mocked async methods."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.billing import InvoiceStatus, PaymentMethod, PaymentStatus
from app.services.payment_service import PaymentService


@pytest.mark.asyncio
class TestPaymentService:
    async def test_get_invoice_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_invoice = MagicMock()
        mock_invoice.id = uuid4()
        mock_result.scalar_one_or_none.return_value = mock_invoice
        mock_db.execute.return_value = mock_result

        result = await PaymentService.get_invoice(mock_db, uuid4(), uuid4())
        assert result is mock_invoice

    async def test_get_invoice_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await PaymentService.get_invoice(mock_db, uuid4(), uuid4())
        assert result is None

    async def test_get_payment_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_payment = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_payment
        mock_db.execute.return_value = mock_result

        result = await PaymentService.get_payment(mock_db, "txn_123", uuid4())
        assert result is mock_payment

    async def test_create_payment_record(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        practice_id = uuid4()
        patient_id = uuid4()
        mock_invoice = MagicMock()
        mock_invoice.id = uuid4()
        mock_invoice.patient_id = patient_id
        mock_invoice.balance_due = Decimal("100.00")
        mock_invoice.status = InvoiceStatus.PENDING

        invoice_result = MagicMock()
        invoice_result.scalar_one_or_none.return_value = mock_invoice
        transaction_result = MagicMock()
        transaction_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [invoice_result, transaction_result]

        result = await PaymentService.create_payment_record(
            mock_db,
            mock_invoice.id,
            patient_id,
            practice_id,
            Decimal("50.00"),
            PaymentMethod.CARD,
            "txn_123",
            PaymentStatus.COMPLETED,
        )

        assert result.invoice_id == mock_invoice.id
        assert result.patient_id == patient_id
        assert result.amount == Decimal("50.00")
        assert result.status == PaymentStatus.COMPLETED
        mock_db.flush.assert_awaited_once()

    async def test_mark_invoice_paid(self):
        mock_db = AsyncMock()
        practice_id = uuid4()
        mock_invoice = MagicMock()
        mock_invoice.id = uuid4()
        mock_invoice.balance_due = Decimal("0.00")
        mock_invoice.status = InvoiceStatus.PENDING
        mock_invoice.total = Decimal("10.00")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_invoice
        mock_db.execute.return_value = mock_result

        # The amount-aware transition path needs a completed-payments sum.
        original_completed = PaymentService.completed_total
        PaymentService.completed_total = staticmethod(
            AsyncMock(return_value=Decimal("10.00"))
        )
        try:
            result = await PaymentService.mark_invoice_paid(
                mock_db, mock_invoice.id, practice_id
            )
            assert result is mock_invoice
            assert result.status == InvoiceStatus.PAID
        finally:
            PaymentService.completed_total = original_completed

    async def test_update_payment_status(self):
        mock_db = AsyncMock()
        practice_id = uuid4()
        mock_payment = MagicMock()
        mock_payment.id = uuid4()
        mock_payment.status = PaymentStatus.PENDING
        mock_payment.invoice_id = uuid4()

        mock_invoice = MagicMock()
        mock_invoice.id = mock_payment.invoice_id
        mock_invoice.status = InvoiceStatus.PENDING
        mock_invoice.total = Decimal("10.00")

        # First execute resolves the payment; subsequent ones (the invoice
        # refresh) resolve the invoice.
        mock_payment_result = MagicMock()
        mock_payment_result.scalar_one_or_none.return_value = mock_payment
        mock_invoice_result = MagicMock()
        mock_invoice_result.scalar_one_or_none.return_value = mock_invoice
        mock_db.execute.side_effect = [mock_payment_result, mock_invoice_result]

        original_completed = PaymentService.completed_total
        PaymentService.completed_total = staticmethod(
            AsyncMock(return_value=Decimal("10.00"))
        )
        try:
            result = await PaymentService.update_payment_status(
                mock_db,
                mock_payment.id,
                PaymentStatus.COMPLETED,
                practice_id,
            )
            assert result is mock_payment
            assert result.status == PaymentStatus.COMPLETED
            # Invoice recomputed from the new completed total.
            assert mock_invoice.status == InvoiceStatus.PAID
        finally:
            PaymentService.completed_total = original_completed

    async def test_list_payments(self):
        mock_db = AsyncMock()
        mock_payments = [MagicMock(), MagicMock()]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2  # func.count() aggregate

        mock_paginated_result = MagicMock()
        mock_paginated_result.scalars.return_value.all.return_value = mock_payments

        mock_db.execute.side_effect = [mock_count_result, mock_paginated_result]

        payments, total = await PaymentService.list_payments(mock_db, uuid4())
        assert payments == mock_payments
        assert total == 2
