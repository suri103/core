"""
Tests for Stripe payment processing integration.

we test the webhook handler functions directly as unit tests and verify
the core payment/subscription lifecycle logic.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import UUID
from types import SimpleNamespace
from fastapi import HTTPException
from app.schemas.payment import PaymentIntentCreate


def _async_db(*scalar_results):
    """Build an AsyncSession-shaped mock with ordered scalar query results."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    results = []
    for value in scalar_results:
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
    db.execute.side_effect = results
    return db

class TestStripeWebhookHandlers:
    """Test Stripe webhook handler functions directly."""

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded(self):
        """Test that a successful payment intent updates the local Payment record."""
        from app.api.v1.endpoints.stripe import handle_payment_succeeded

        mock_payment = MagicMock()
        mock_payment.status = "pending"
        mock_payment.processed_at = None

        mock_db = _async_db(mock_payment)

        payment_intent = {
            "id": "pi_test_12345",
            "amount": 15000,  # $150.00
            "currency": "usd",
            "customer_email": "patient@example.com",
            "description": "Crown Prep - Tooth #14",
        }

        with patch("app.api.v1.endpoints.stripe.send_payment_confirmation_email", new_callable=AsyncMock):
            await handle_payment_succeeded(mock_db, payment_intent)

        # Verify the payment record was updated
        assert mock_payment.status == "completed"
        assert mock_payment.processed_at is not None
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded_no_record(self):
        """C-01: an unattributable payment is quarantined, never silently dropped."""
        from app.api.v1.endpoints.stripe import handle_payment_succeeded, _current_event_id
        from app.models.processor_event import ProcessorEventStatus

        # No local ledger row, and no routing metadata to reconstruct one.
        mock_db = _async_db(None, None)

        payment_intent = {
            "id": "pi_nonexistent_99999",
            "amount": 5000,
            "currency": "usd",
        }

        token = _current_event_id.set("evt_unattributable_1")
        try:
            await handle_payment_succeeded(mock_db, payment_intent)
        finally:
            _current_event_id.reset(token)

        # The event must be durably recorded as UNRECONCILED and committed.
        # Previously this path logged and returned, so the webhook answered
        # 200 for money that was never recorded anywhere.
        assert mock_db.add.call_count == 1
        recorded = mock_db.add.call_args[0][0]
        assert recorded.event_id == "evt_unattributable_1"
        assert recorded.status == ProcessorEventStatus.UNRECONCILED
        assert recorded.processor_object_id == "pi_nonexistent_99999"
        assert recorded.amount_minor == 5000
        assert recorded.payment_transaction_id is None
        assert recorded.error_message
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded_reconstructs_from_metadata(self):
        """C-01: a missing ledger row is rebuilt when metadata identifies the tenant."""
        from app.services.processor_events import resolve_payment_transaction

        practice_id = "11111111-1111-4111-8111-111111111111"
        patient_id = "22222222-2222-4222-8222-222222222222"

        patient = MagicMock()
        patient.id = UUID(patient_id)
        patient.practice_id = UUID(practice_id)

        # 1st execute: no existing PaymentTransaction. 2nd: patient lookup.
        # 3rd: M5 ledger link (no invoice-ledger Payment row -> no-op).
        mock_db = _async_db(None, patient, None)

        payment_intent = {
            "id": "pi_reconstruct_1",
            "amount": 12345,
            "currency": "usd",
            "metadata": {"practice_id": practice_id, "patient_id": patient_id},
        }

        transaction, reason = await resolve_payment_transaction(mock_db, payment_intent)

        assert reason is None
        assert transaction is not None
        assert transaction.processor_transaction_id == "pi_reconstruct_1"
        assert str(transaction.practice_id) == practice_id
        assert str(transaction.patient_id) == patient_id
        assert str(transaction.amount) == "123.45"

    @pytest.mark.asyncio
    async def test_resolve_rejects_cross_tenant_metadata(self):
        """C-01: metadata claiming a patient from another practice is refused."""
        from app.services.processor_events import resolve_payment_transaction

        # 1st execute: no existing row. 2nd: patient lookup returns None because
        # the practice_id/patient_id pair does not match.
        mock_db = _async_db(None, None)

        payment_intent = {
            "id": "pi_cross_tenant_1",
            "amount": 5000,
            "currency": "usd",
            "metadata": {
                "practice_id": "11111111-1111-4111-8111-111111111111",
                "patient_id": "33333333-3333-4333-8333-333333333333",
            },
        }

        transaction, reason = await resolve_payment_transaction(mock_db, payment_intent)

        assert transaction is None
        assert "does not belong to practice" in reason
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_decimal_currency_not_divided(self):
        """JPY is reported in whole units; dividing by 100 under-records 100x."""
        from app.services.processor_events import minor_units_to_decimal

        assert str(minor_units_to_decimal(5000, "usd")) == "50.00"
        assert str(minor_units_to_decimal(5000, "jpy")) == "5000"
        assert str(minor_units_to_decimal(None, "usd")) == "0.00"

    @pytest.mark.asyncio
    async def test_summary_excludes_phi(self):
        """M-22: the stored event summary must not carry free-text or PHI."""
        from app.services.processor_events import summarize_event

        summary = summarize_event(
            {
                "id": "pi_1",
                "amount": 100,
                "currency": "usd",
                "description": "Crown Prep - Tooth #14 for Jane Doe",
                "receipt_email": "jane@example.com",
                "metadata": {
                    "practice_id": "p1",
                    "patient_id": "pat1",
                    "chief_complaint": "toothache",
                },
            }
        )

        assert "description" not in summary
        assert "receipt_email" not in summary
        assert summary["routing_metadata"] == {"practice_id": "p1", "patient_id": "pat1"}
        assert "chief_complaint" not in summary["routing_metadata"]

    @pytest.mark.asyncio
    async def test_handle_payment_failed(self):
        """Test that a failed payment intent marks the record as failed."""
        from app.api.v1.endpoints.stripe import handle_payment_failed

        mock_payment = MagicMock()
        mock_payment.status = "pending"

        mock_db = _async_db(mock_payment)

        payment_intent = {
            "id": "pi_test_failed_001",
            "last_payment_error": {
                "message": "Your card was declined."
            },
        }

        await handle_payment_failed(mock_db, payment_intent)

        assert mock_payment.status == "failed"
        assert mock_payment.error_message == "Your card was declined."
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_subscription_created(self):
        """Legacy webhook entry delegates to the ownership-gated handler."""
        from app.api.v1.endpoints.stripe import handle_subscription_created

        mock_db = _async_db()
        subscription = {
            "id": "sub_test_001",
            "metadata": {
                "coredent_subscription_id": "11111111-1111-4111-8111-111111111111",
                "practice_id": "22222222-2222-4222-8222-222222222222",
                "coredent_plan_id": "33333333-3333-4333-8333-333333333333",
            },
        }
        with patch(
            "app.services.subscription_webhooks.SubscriptionWebhookHandler.handle_subscription_created",
            new=AsyncMock(),
        ) as gated_handler:
            await handle_subscription_created(mock_db, subscription)

        gated_handler.assert_awaited_once_with(mock_db, subscription)

    @pytest.mark.asyncio
    async def test_handle_subscription_created_no_user_id(self):
        """Test that subscriptions without user_id metadata are skipped."""
        from app.api.v1.endpoints.stripe import handle_subscription_created

        mock_db = MagicMock()

        subscription = {
            "id": "sub_orphan_001",
            "customer": "cus_test_002",
            "status": "active",
            "metadata": {},  # No user_id
        }

        await handle_subscription_created(mock_db, subscription)

        # Should not add any record
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_subscription_updated(self):
        """Test that subscription updates propagate to the local record."""
        from app.api.v1.endpoints.stripe import handle_subscription_updated

        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.cancel_at_period_end = False

        mock_db = _async_db(mock_sub)

        subscription = {
            "id": "sub_test_001",
            "status": "past_due",
            "cancel_at_period_end": True,
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }

        await handle_subscription_updated(mock_db, subscription)

        assert mock_sub.status == "past_due"
        assert mock_sub.cancel_at_period_end is True
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_subscription_deleted(self):
        """Test that subscription deletion marks the record as canceled."""
        from app.api.v1.endpoints.stripe import handle_subscription_deleted

        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.canceled_at = None

        mock_db = _async_db(mock_sub)

        subscription = {"id": "sub_test_001"}

        await handle_subscription_deleted(mock_db, subscription)

        assert mock_sub.status == "canceled"
        assert mock_sub.canceled_at is not None
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_invoice_paid(self):
        """Test that a paid invoice updates the subscription billing dates."""
        from app.api.v1.endpoints.stripe import handle_invoice_paid

        mock_sub = MagicMock()
        mock_sub.next_billing_date = None

        mock_db = _async_db(mock_sub)

        invoice = {
            "id": "in_test_001",
            "subscription": "sub_test_001",
            "lines": {
                "data": [
                    {
                        "period": {
                            "start": 1700000000,
                            "end": 1702592000,
                        }
                    }
                ]
            },
        }

        await handle_invoice_paid(mock_db, invoice)

        assert mock_sub.next_billing_date is not None
        mock_db.commit.assert_awaited_once()


class TestStripeWebhookEndpoint:
    """Test the Stripe webhook endpoint signature verification logic."""

    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_signature(self):
        """Verify that webhooks with invalid signatures are rejected."""
        import stripe

        # Simulate an invalid payload/signature combination
        with pytest.raises(stripe.error.SignatureVerificationError):
            stripe.Webhook.construct_event(
                payload=b'{"type": "payment_intent.succeeded"}',
                sig_header="invalid_signature",
                secret="whsec_test_secret",
            )

    @pytest.mark.asyncio
    async def test_webhook_construct_event_with_valid_signature(self):
        """Verify that stripe.Webhook.construct_event works when mocked."""
        import stripe

        mock_event = {
            "id": "evt_test_001",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_12345",
                    "amount": 15000,
                    "currency": "usd",
                }
            },
        }

        with patch.object(stripe.Webhook, "construct_event", return_value=mock_event) as mock_construct:
            event = stripe.Webhook.construct_event(
                payload=b"test_payload",
                sig_header="test_sig",
                secret="whsec_test_secret",
            )

            assert event["type"] == "payment_intent.succeeded"
            assert event["data"]["object"]["id"] == "pi_test_12345"
            mock_construct.assert_called_once()

@pytest.mark.asyncio
async def test_create_payment_intent_is_fail_closed():
    from app.api.v1.endpoints import stripe as stripe_endpoint
    db = _async_db()
    provider = MagicMock()
    with patch.object(stripe_endpoint.stripe.PaymentIntent, "create", provider):
        with pytest.raises(HTTPException) as exc_info:
            await stripe_endpoint.create_payment_intent(
                PaymentIntentCreate(invoice_id=UUID("00000000-0000-0000-0000-000000000001"), amount=100.0),
                db=db,
                current_user=SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000002")),
            )
    assert exc_info.value.status_code == 503
    provider.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_payment_webhook_reconciliation_error_propagates_for_retry():
    from app.api.v1.endpoints.stripe import handle_payment_succeeded
    db = _async_db()
    db.execute.side_effect = ValueError("database unavailable")
    with pytest.raises(ValueError, match="database unavailable"):
        await handle_payment_succeeded(db, {"id": "pi_retry"})
    db.rollback.assert_awaited_once()
