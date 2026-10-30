"""Phase 2 regression tests.

Covers the security and money fixes from the 2026-08 production-readiness
engagement:

- H1  /treatment/estimate cross-tenant insurance read (IDOR)
- H2  global subscription plan edit by tenant admin
- H3  SSRF guard + CSRF/role gate on POST /automations/test
- M2  POST /automations/trigger actually dispatches webhooks
- H4  mass-assignment allowlists (labs, inventory, referrals)
- M3  payment-plan installment payment endpoint (idempotent)
- M10 cancel_invoice audit records the true previous status
- M11 lab case numbers survive concurrent allocation (existence check)
- M12 one reminder per appointment (unique index)
- L1  image share expiry enforced
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.billing import (
    Invoice,
    Payment,
    PaymentPlan,
    PaymentPlanInstallment,
    PaymentPlanStatus,
    PaymentStatus,
    InvoiceStatus,
)
from app.models.imaging import PatientImage, ImageType
from app.models.insurance import InsuranceCarrier, PatientInsurance
from app.models.reminder import Reminder, ReminderStatus
from app.models.subscription import SubscriptionInterval, SubscriptionPlan


# ---------------------------------------------------------------------------
# H1 — treatment estimate must not leak other tenants' insurance policies
# ---------------------------------------------------------------------------

async def _make_insurance(db, patient, carrier_name="OtherCo"):
    carrier = InsuranceCarrier(name=carrier_name)
    db.add(carrier)
    await db.flush()
    policy = PatientInsurance(
        patient_id=patient.id,
        carrier_id=carrier.id,
        subscriber_id="SUB-001",
        annual_maximum=Decimal("2000.00"),
        deductible_met=Decimal("150.00"),
    )
    db.add(policy)
    await db.flush()
    return policy


class TestTreatmentEstimateTenantScope:
    async def test_estimate_rejects_cross_tenant_policy(
        self, db_session, test_user, other_patient
    ):
        from app.services.treatment_costing import TreatmentCostingService

        policy = await _make_insurance(db_session, other_patient)

        result = await TreatmentCostingService.estimate_insurance_coverage(
            db_session,
            policy.id,
            [{"fee": 100.0}],
            practice_id=test_user.practice_id,
        )
        # The service fails closed: no policy details are returned.
        # Money crosses the wire as exact decimal strings (same contract as
        # the reports API), never binary floats.
        assert "insurance_details" not in result
        assert result["total_fee"] == "0.0"
        assert result["procedure_estimates"] == []

    async def test_estimate_allows_own_tenant_policy(
        self, db_session, test_user, test_patient
    ):
        from app.services.treatment_costing import TreatmentCostingService

        policy = await _make_insurance(db_session, test_patient)

        result = await TreatmentCostingService.estimate_insurance_coverage(
            db_session,
            policy.id,
            [{"fee": 100.0}],
            practice_id=test_user.practice_id,
        )
        assert result["insurance_details"]["carrier_name"] == "OtherCo"
        assert result["total_fee"] == "100.00"


# ---------------------------------------------------------------------------
# H2 — tenant admins cannot edit platform-global plans
# ---------------------------------------------------------------------------

class TestGlobalPlanEdit:
    async def test_update_global_plan_forbidden(self, async_client, auth_headers, db_session):
        plan = SubscriptionPlan(
            name="Platform Pro",
            amount=Decimal("99.00"),
            interval=SubscriptionInterval.MONTHLY,
            practice_id=None,  # global
        )
        db_session.add(plan)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/subscriptions/plans/{plan.id}",
            headers=auth_headers,
            json={"amount": 1.00},
        )
        assert response.status_code == 404

        await db_session.refresh(plan)
        assert plan.amount == Decimal("99.00")

    async def test_update_own_plan_allowed(self, async_client, auth_headers, db_session, test_practice):
        plan = SubscriptionPlan(
            name="Practice Basic",
            amount=Decimal("49.00"),
            interval=SubscriptionInterval.MONTHLY,
            practice_id=test_practice.id,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/subscriptions/plans/{plan.id}",
            headers=auth_headers,
            json={"amount": 59.00},
        )
        assert response.status_code == 200
        assert Decimal(str(response.json()["amount"])) == Decimal("59.00")


# ---------------------------------------------------------------------------
# H3 — SSRF guard on webhook test endpoint
# ---------------------------------------------------------------------------

class TestWebhookTestSsrfGuard:
    async def test_requires_authentication(self, async_client):
        response = await async_client.post(
            "/api/v1/automations/test",
            json={"webhookUrl": "https://example.com/hook"},
        )
        assert response.status_code in (401, 403)

    async def test_requires_csrf(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/v1/automations/test",
            headers={"Authorization": auth_headers["Authorization"]},
            json={"webhookUrl": "https://example.com/hook"},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("bad_url", [
        "http://127.0.0.1:9/hook",
        "http://localhost/hook",
        "http://192.168.1.1/hook",
        "http://169.254.169.254/latest/meta-data",
        "ftp://example.com/hook",
        "not-a-url",
    ])
    async def test_rejects_private_and_invalid_targets(self, bad_url):
        from app.api.v1.endpoints.automations import _validate_webhook_url_sync

        with pytest.raises(HTTPException) as exc_info:
            _validate_webhook_url_sync(bad_url)
        assert exc_info.value.status_code == 400

    def test_public_ip_allowed_without_dns(self):
        from app.api.v1.endpoints.automations import _validate_webhook_url_sync

        # Literal public IP: getaddrinfo does not hit the network.
        _validate_webhook_url_sync("http://93.184.216.34/hook")


# ---------------------------------------------------------------------------
# M2 — trigger dispatches to configured webhooks
# ---------------------------------------------------------------------------

class TestTriggerDispatches:
    async def test_trigger_posts_to_matching_webhooks(
        self, async_client, auth_headers, db_session, test_practice, monkeypatch
    ):
        from app.api.v1.endpoints import automations as automations_module

        practice = await db_session.get(type(test_practice), test_practice.id)
        practice.settings = {
            "webhooks": [
                {"id": "w1", "url": "https://hooks.example.com/a", "event": "invoice_created",
                 "isActive": True, "secretToken": "s3cret"},
                {"id": "w2", "url": "https://hooks.example.com/b", "event": "payment_received",
                 "isActive": True},
                {"id": "w3", "url": "https://hooks.example.com/c", "event": "invoice_created",
                 "isActive": False},
            ]
        }
        await db_session.commit()

        posted = []

        class FakeResponse:
            is_success = True

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None, headers=None):
                posted.append((url, json, headers))
                return FakeResponse()

        async def _no_validate(url):
            return None

        monkeypatch.setattr(automations_module.httpx, "AsyncClient", FakeClient)
        monkeypatch.setattr(automations_module, "validate_webhook_url", _no_validate)

        response = await async_client.post(
            "/api/v1/automations/trigger",
            headers=auth_headers,
            json={"event": "invoice_created", "data": {"invoiceId": "inv-1"}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["triggeredCount"] == 1
        assert body["deliveredCount"] == 1

        assert len(posted) == 1
        url, payload, headers = posted[0]
        assert url == "https://hooks.example.com/a"
        assert payload["event"] == "invoice_created"
        assert payload["data"] == {"invoiceId": "inv-1"}
        assert headers.get("X-Webhook-Secret") == "s3cret"


# ---------------------------------------------------------------------------
# H4 — mass assignment is ignored on labs / inventory / referrals updates
# ---------------------------------------------------------------------------

class TestMassAssignmentAllowlists:
    async def test_lab_case_update_ignores_protected_columns(
        self, async_client, auth_headers, db_session, test_practice, test_patient, test_user
    ):
        from app.models.lab import Lab, LabCase, LabCaseType

        lab = Lab(practice_id=test_practice.id, name="Acme Dental Lab")
        db_session.add(lab)
        await db_session.flush()
        case = LabCase(
            practice_id=test_practice.id,
            lab_id=lab.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            case_number="CASE-20260821-0001",
            case_type=LabCaseType.CROWN,
        )
        db_session.add(case)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/labs/cases/{case.id}",
            headers=auth_headers,
            json={
                "description": "Updated shade",
                "case_number": "HACKED-0001",
                "is_deleted": True,
                "provider_id": str(uuid4()),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated shade"
        assert data["case_number"] == "CASE-20260821-0001"
        assert data["is_deleted"] is False

    async def test_inventory_item_update_ignores_protected_columns(
        self, async_client, auth_headers, db_session, test_practice
    ):
        from app.models.inventory import InventoryItem

        item = InventoryItem(
            practice_id=test_practice.id,
            name="Nitrile Gloves",
            current_quantity=10,
        )
        db_session.add(item)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/inventory/items/{item.id}",
            headers=auth_headers,
            json={
                "name": "Nitrile Gloves L",
                "current_quantity": 25,
                "id": str(uuid4()),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Nitrile Gloves L"
        assert data["current_quantity"] == 25
        assert data["id"] == str(item.id)

    async def test_referral_update_cannot_soft_delete_or_renumber(
        self, async_client, auth_headers, db_session, test_patient, test_user
    ):
        from app.models.referral import Referral, ReferralStatus, ReferralType

        referral = Referral(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            referring_provider_id=test_user.id,
            referral_type=ReferralType.ORTHODONTICS,
            status=ReferralStatus.PENDING,
            reason="Impacted canine",
        )
        db_session.add(referral)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/referrals/{referral.id}",
            headers=auth_headers,
            json={"is_deleted": True, "status": "sent"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"

        # The soft-delete flag is not client-writable: verify in the DB.
        from sqlalchemy import select as _select
        row = (await db_session.execute(
            _select(Referral).where(Referral.id == referral.id)
        )).scalar_one()
        assert row.is_deleted is not True


# ---------------------------------------------------------------------------
# M3 — installment payments
# ---------------------------------------------------------------------------

async def _make_invoice_with_plan(db, practice, patient, total="300.00"):
    invoice = Invoice(
        practice_id=practice.id,
        patient_id=patient.id,
        invoice_number=f"INV-{uuid4().hex[:8]}",
        status=InvoiceStatus.PENDING,
        subtotal=Decimal(total),
        tax=Decimal("0"),
        total=Decimal(total),
        tax_rate=Decimal("0"),
        line_items=[{"description": "Treatment", "quantity": 1, "unit_price": float(total), "total": float(total)}],
    )
    db.add(invoice)
    await db.flush()

    plan = PaymentPlan(
        practice_id=practice.id,
        patient_id=patient.id,
        invoice_id=invoice.id,
        status=PaymentPlanStatus.ACTIVE,
        total_amount=Decimal(total),
        initial_deposit=Decimal("0"),
        start_date=datetime.now(timezone.utc).date(),
    )
    db.add(plan)
    await db.flush()

    installments = []
    per = (Decimal(total) / 3).quantize(Decimal("0.01"))
    for i in range(3):
        inst = PaymentPlanInstallment(
            plan_id=plan.id,
            amount=per,
            due_date=datetime.now(timezone.utc).date() + timedelta(days=30 * (i + 1)),
            status="scheduled",
        )
        db.add(inst)
        installments.append(inst)
    await db.commit()
    return invoice, plan, installments


class TestInstallmentPayment:
    async def test_pay_installment_posts_payment_and_updates_invoice(
        self, async_client, auth_headers, db_session, test_practice, test_patient
    ):
        invoice, plan, installments = await _make_invoice_with_plan(
            db_session, test_practice, test_patient
        )

        response = await async_client.post(
            f"/api/v1/billing/payment-plans/{plan.id}/installments/{installments[0].id}/pay",
            headers=auth_headers,
            json={"payment_method": "cash"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        paid = [i for i in body["installments"] if i["status"] == "paid"]
        assert len(paid) == 1

        await db_session.refresh(invoice)
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID

        payments = (await db_session.execute(
            select(Payment).where(Payment.invoice_id == invoice.id)
        )).scalars().all()
        assert len(payments) == 1
        assert payments[0].transaction_id == f"PLAN-{installments[0].id}"

    async def test_pay_installment_is_idempotent(
        self, async_client, auth_headers, db_session, test_practice, test_patient
    ):
        invoice, plan, installments = await _make_invoice_with_plan(
            db_session, test_practice, test_patient
        )

        first = await async_client.post(
            f"/api/v1/billing/payment-plans/{plan.id}/installments/{installments[0].id}/pay",
            headers=auth_headers,
            json={"payment_method": "cash"},
        )
        assert first.status_code == 200

        retry = await async_client.post(
            f"/api/v1/billing/payment-plans/{plan.id}/installments/{installments[0].id}/pay",
            headers=auth_headers,
            json={"payment_method": "cash"},
        )
        assert retry.status_code == 409

        payments = (await db_session.execute(
            select(Payment).where(Payment.invoice_id == invoice.id)
        )).scalars().all()
        assert len(payments) == 1

    async def test_final_installment_completes_plan_and_invoice(
        self, async_client, auth_headers, db_session, test_practice, test_patient
    ):
        invoice, plan, installments = await _make_invoice_with_plan(
            db_session, test_practice, test_patient
        )

        for inst in installments:
            resp = await async_client.post(
                f"/api/v1/billing/payment-plans/{plan.id}/installments/{inst.id}/pay",
                headers=auth_headers,
                json={"payment_method": "card"},
            )
            assert resp.status_code == 200

        await db_session.refresh(plan)
        await db_session.refresh(invoice)
        assert plan.status == PaymentPlanStatus.COMPLETED
        assert invoice.status == InvoiceStatus.PAID


# ---------------------------------------------------------------------------
# M10 — cancel_invoice audit records the true previous status
# ---------------------------------------------------------------------------

class TestCancelInvoiceAudit:
    async def test_previous_status_recorded_before_mutation(
        self, async_client, auth_headers, db_session, test_practice, test_patient
    ):
        from sqlalchemy import select
        from app.models.audit import AuditLog

        invoice = Invoice(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            invoice_number=f"INV-{uuid4().hex[:8]}",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("80.00"),
            tax=Decimal("0"),
            total=Decimal("80.00"),
            tax_rate=Decimal("0"),
            line_items=[],
        )
        db_session.add(invoice)
        await db_session.commit()

        response = await async_client.delete(
            f"/api/v1/billing/invoices/{invoice.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

        log = (await db_session.execute(
            select(AuditLog)
            .where(AuditLog.action == "cancel_invoice", AuditLog.entity_id == invoice.id)
            .order_by(AuditLog.created_at.desc())
        )).scalars().first()
        assert log is not None
        assert log.changes["previous_status"] == "pending"
        assert log.changes["new_status"] == "cancelled"


# ---------------------------------------------------------------------------
# M12 — one reminder per appointment
# ---------------------------------------------------------------------------

class TestReminderUniqueness:
    async def test_duplicate_appointment_reminder_rejected(
        self, db_session, test_appointment
    ):
        db_session.add(Reminder(
            appointment_id=test_appointment.id,
            reminder_type="email",
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
            status=ReminderStatus.PENDING,
        ))
        await db_session.commit()

        db_session.add(Reminder(
            appointment_id=test_appointment.id,
            reminder_type="sms",
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
            status=ReminderStatus.PENDING,
        ))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# L1 — image share expiry enforced
# ---------------------------------------------------------------------------

def _make_image(practice, patient, token, expires_at):
    return PatientImage(
        practice_id=practice.id,
        patient_id=patient.id,
        image_type=ImageType.XRAY,
        file_name="pa.png",
        file_path="uploads/pa.png",
        acquisition_date=datetime.now(timezone.utc),
        share_token=token,
        share_expires_at=expires_at,
    )


class TestShareExpiry:
    async def test_expired_share_token_returns_none(
        self, db_session, test_practice, test_patient
    ):
        from app.services.imaging_service import ImagingService

        image = _make_image(
            test_practice, test_patient, "tok-expired",
            datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(image)
        await db_session.commit()

        result = await ImagingService.get_public_image(db_session, image.id, "tok-expired")
        assert result is None

    async def test_active_share_token_still_works(
        self, db_session, test_practice, test_patient
    ):
        from app.services.imaging_service import ImagingService

        image = _make_image(
            test_practice, test_patient, "tok-live",
            datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(image)
        await db_session.commit()

        result = await ImagingService.get_public_image(db_session, image.id, "tok-live")
        assert result is not None
        assert result.id == image.id

    async def test_wrong_token_returns_none(self, db_session, test_practice, test_patient):
        from app.services.imaging_service import ImagingService

        image = _make_image(
            test_practice, test_patient, "tok-a",
            datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(image)
        await db_session.commit()

        result = await ImagingService.get_public_image(db_session, image.id, "tok-b")
        assert result is None


# ---------------------------------------------------------------------------
# M11 — lab case numbering skips numbers already in use
# ---------------------------------------------------------------------------

class TestLabCaseNumbering:
    async def test_create_skips_existing_case_numbers(
        self, async_client, auth_headers, db_session, test_practice, test_patient, test_user
    ):
        from app.models.lab import Lab, LabCase, LabCaseType

        lab = Lab(practice_id=test_practice.id, name="Numbering Lab")
        db_session.add(lab)
        await db_session.flush()

        today = datetime.now(timezone.utc)
        day_prefix = today.strftime("%Y%m%d")
        existing = LabCase(
            practice_id=test_practice.id,
            lab_id=lab.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            case_number=f"CASE-{day_prefix}-0001",
            case_type=LabCaseType.CROWN,
        )
        db_session.add(existing)
        await db_session.commit()

        response = await async_client.post(
            "/api/v1/labs/cases/",
            headers=auth_headers,
            json={
                "lab_id": str(lab.id),
                "patient_id": str(test_patient.id),
                "case_type": "bridge",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["case_number"] != f"CASE-{day_prefix}-0001"


# ---------------------------------------------------------------------------
# Module 3 — Gateway refunds, settlement, claims bounds, treatment splits
# ---------------------------------------------------------------------------

class TestGatewayRefundsAndSettlement:
    async def test_gateway_refund_stripe_success(
        self, async_client, auth_headers, db_session, test_practice, test_patient, monkeypatch
    ):
        """Processor payments call the gateway first before mutating ledger (C3)."""
        import app.api.v1.endpoints.billing as billing_ep
        monkeypatch.setattr(billing_ep.settings, "STRIPE_API_KEY", "sk_test_123")

        inv_res = await async_client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "line_items": [{"description": "Crown", "quantity": 1, "unit_price": 200.0, "total": 200.0}],
                "status": "pending",
            },
        )
        invoice = inv_res.json()

        pay_res = await async_client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": invoice["id"],
                "patient_id": str(test_patient.id),
                "amount": 200.0,
                "payment_method": "card",
                "transaction_id": "pi_test_stripe_gateway_refund_001",
                "status": "completed",
            },
        )
        payment = pay_res.json()

        mock_refund = MagicMock(id="re_stripe_gateway_999", amount=20000, status="succeeded")
        monkeypatch.setattr(
            billing_ep.stripe_lib.Refund,
            "create",
            MagicMock(return_value=mock_refund),
        )

        refund_res = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 200.0, "reason": "Customer requested refund"},
        )
        assert refund_res.status_code == 200, refund_res.text
        data = refund_res.json()
        assert data["payment_status"] == "refunded"
        assert Decimal(data["refunded_amount"]) == Decimal("200.00")

    async def test_gateway_refund_stripe_failure_409(
        self, async_client, auth_headers, db_session, test_practice, test_patient, monkeypatch
    ):
        """Failed gateway refund raises 409 and leaves ledger unmutated (C3)."""
        import app.api.v1.endpoints.billing as billing_ep
        monkeypatch.setattr(billing_ep.settings, "STRIPE_API_KEY", "sk_test_123")

        inv_res = await async_client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "line_items": [{"description": "Cleaning", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
                "status": "pending",
            },
        )
        invoice = inv_res.json()

        pay_res = await async_client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": invoice["id"],
                "patient_id": str(test_patient.id),
                "amount": 100.0,
                "payment_method": "card",
                "transaction_id": "pi_stripe_fail_002",
                "status": "completed",
            },
        )
        payment = pay_res.json()

        def _raise_stripe_error(*args, **kwargs):
            raise billing_ep.stripe_lib.error.StripeError("Card expired or declined")

        monkeypatch.setattr(billing_ep.stripe_lib.Refund, "create", _raise_stripe_error)

        refund_res = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 100.0},
        )
        assert refund_res.status_code == 409
        assert "gateway refund failed" in refund_res.json()["detail"].lower()

        # Ledger row must remain COMPLETED and refunded_amount == 0
        get_pay = (
            await db_session.execute(select(Payment).where(Payment.id == UUID(payment["id"])))
        ).scalar_one()
        assert get_pay.status == PaymentStatus.COMPLETED
        assert Decimal(str(get_pay.refunded_amount or 0)) == Decimal("0")

    async def test_settle_pending_payment(
        self, async_client, auth_headers, db_session, test_practice, test_patient
    ):
        """PUT /billing/payments/{id}/settle transitions PENDING to COMPLETED and updates invoice (H9)."""
        inv_res = await async_client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "line_items": [{"description": "Procedure", "quantity": 1, "unit_price": 150.0, "total": 150.0}],
                "status": "pending",
            },
        )
        invoice = inv_res.json()

        pay_res = await async_client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": invoice["id"],
                "patient_id": str(test_patient.id),
                "amount": 150.0,
                "payment_method": "check",
                "status": "pending",
            },
        )
        payment = pay_res.json()
        assert payment["status"] == "pending"

        # Settle the payment
        settle_res = await async_client.put(
            f"/api/v1/billing/payments/{payment['id']}/settle",
            headers=auth_headers,
        )
        assert settle_res.status_code == 200, settle_res.text
        settled_data = settle_res.json()
        assert settled_data["status"] == "completed"

        # Second settle call on already COMPLETED payment raises 409
        retry_res = await async_client.put(
            f"/api/v1/billing/payments/{payment['id']}/settle",
            headers=auth_headers,
        )
        assert retry_res.status_code == 409


class TestClaimsAndTreatmentIntegrity:
    async def test_claims_bounds_and_draft_immutability(
        self, async_client, auth_headers, db_session, test_practice, test_patient
    ):
        """Claims adjudication fields are frozen in DRAFT and bounded by billed amount (M4)."""
        from app.models.insurance import InsuranceCarrier, PatientInsurance, InsuranceClaim, ClaimStatus

        carrier = InsuranceCarrier(name="Claims Carrier", is_active=True, practice_id=test_practice.id)
        db_session.add(carrier)
        await db_session.flush()

        policy = PatientInsurance(
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            is_primary=True,
            subscriber_id="SUB-CLM-99",
            relationship_to_subscriber="self",
            is_active=True,
        )
        db_session.add(policy)
        await db_session.flush()

        claim = InsuranceClaim(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            patient_insurance_id=policy.id,
            carrier_id=carrier.id,
            claim_number="CLM-INTEG-001",
            status=ClaimStatus.DRAFT,
            service_date=datetime.now(timezone.utc).date(),
            billed_amount=Decimal("300.00"),
            procedure_codes=[{"code": "D0150", "description": "Exam", "fee": 300.00}],
        )
        db_session.add(claim)
        await db_session.commit()

        # Updating adjudication fields while DRAFT must fail with 400
        draft_update_fail = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"paid_amount": "200.00"},
        )
        assert draft_update_fail.status_code == 400

        # Transition to SUBMITTING -> SUBMISSION_FAILED -> DRAFT (M4 transitions)
        step1 = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"status": "submitting"},
        )
        assert step1.status_code == 200
        assert step1.json()["status"] == "submitting"

        step2 = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"status": "submission_failed"},
        )
        assert step2.status_code == 200
        assert step2.json()["status"] == "submission_failed"

        step3 = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"status": "draft"},
        )
        assert step3.status_code == 200
        assert step3.json()["status"] == "draft"

        # Now submit the claim so we can test adjudication amount bounds
        submit_step = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"status": "submitted"},
        )
        assert submit_step.status_code == 200

        # Allowed amount cannot exceed billed (300.00)
        over_allowed = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"allowed_amount": "400.00"},
        )
        assert over_allowed.status_code == 400

        # Patient responsibility cannot exceed allowed
        over_resp = await async_client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"allowed_amount": "200.00", "patient_responsibility": "250.00"},
        )
        assert over_resp.status_code == 400

    async def test_treatment_procedure_split_bounds(
        self, async_client, auth_headers, db_session, test_practice, test_patient, test_user
    ):
        """Treatment procedure splits cannot exceed fee at schema or endpoint (M5)."""
        from app.models.treatment import TreatmentPlan, TreatmentPlanStatus

        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Splits Test Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.commit()

        # Reject creating procedure where insurance_estimate + patient_responsibility > fee
        invalid_create = await async_client.post(
            f"/api/v1/treatment/plans/{plan.id}/procedures",
            headers=auth_headers,
            json={
                "procedure_type": "restorative",
                "ada_code": "D2740",
                "description": "Crown",
                "fee": 500.0,
                "insurance_estimate": 400.0,
                "patient_responsibility": 200.0,  # 400 + 200 = 600 > 500
            },
        )
        assert invalid_create.status_code == 422

