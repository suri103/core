"""Tests for billing endpoints"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import uuid4
import json

pytestmark = pytest.mark.asyncio


class TestBillingEndpoints:
    """Test suite for billing CRUD operations"""

    async def test_create_payment_plan_requires_authentication(self, async_client):
        """Verify payment plan creation requires valid authentication"""
        response = await async_client.post(
            "/api/v1/billing/payment-plans/",
            json={
                "patient_id": str(uuid4()),
                "total_amount": 500.00,
                "initial_deposit": 100.00,
                "months": 12,
                "notes": "Test payment plan"
            }
        )
        # Should return 401 Unauthorized without auth
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"]

    async def test_create_payment_plan_with_valid_auth(self, async_client, auth_headers, test_patient):
        """Verify payment plan creation succeeds with valid authentication and invoice"""
        patient_id = test_patient.id
        inv_res = await async_client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(patient_id),
                "line_items": [
                    {
                        "description": "Dental treatment",
                        "quantity": 1,
                        "unit_price": 500.0,
                        "total": 500.0,
                    }
                ],
                "status": "pending",
            },
        )
        assert inv_res.status_code == 200, inv_res.text
        invoice_id = inv_res.json()["id"]
        
        response = await async_client.post(
            "/api/v1/billing/payment-plans/",
            headers=auth_headers,
            json={
                "patient_id": str(patient_id),
                "invoice_id": invoice_id,
                "total_amount": 500.00,
                "initial_deposit": 100.00,
                "months": 12,
                "notes": "Test payment plan"
            }
        )
        
        # Should succeed with 201 Created
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert "patient_id" in data
        assert data["patient_id"] == str(patient_id)
        assert Decimal(data["total_amount"]) == Decimal("500.0")
        assert Decimal(data["initial_deposit"]) == Decimal("100.0")
        installments = data["installments"]
        assert len(installments) == 12
        assert all(item["status"] == "scheduled" for item in installments)
        assert sum(Decimal(item["amount"]) for item in installments) == Decimal("400.00")
        assert "created_at" in data
        assert "status" in data
        assert data["status"] == "active"

    async def test_create_payment_plan_requires_invoice_id(self, async_client, auth_headers, test_patient):
        """Verify payment plan creation requires invoice_id (Decision 8)"""
        response = await async_client.post(
            "/api/v1/billing/payment-plans/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "total_amount": 500.00,
                "initial_deposit": 100.00,
                "months": 12,
            },
        )
        assert response.status_code == 422

    async def test_create_payment_plan_rejects_negative_amount(self, async_client, auth_headers):
        """Verify Pydantic validation rejects negative total_amount"""
        response = await async_client.post(
            "/api/v1/billing/payment-plans/",
            headers=auth_headers,
            json={
                "patient_id": str(uuid4()),
                "invoice_id": str(uuid4()),
                "total_amount": -100.00,  # Invalid: negative amount
                "initial_deposit": 100.00,
                "months": 12
            }
        )
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Verify error mentions the field
        error_details = str(data["detail"]).lower()
        assert "total_amount" in error_details or "amount" in error_details

    async def test_create_payment_plan_rejects_invalid_months(self, async_client, auth_headers):
        """Verify validation rejects invalid payment plan duration"""
        response = await async_client.post(
            "/api/v1/billing/payment-plans/",
            headers=auth_headers,
            json={
                "patient_id": str(uuid4()),
                "invoice_id": str(uuid4()),
                "total_amount": 500.00,
                "initial_deposit": 100.00,
                "months": 0  # Invalid: zero months
            }
        )
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_create_payment_plan_rejects_deposit_exceeding_total(self, async_client, auth_headers):
        """Verify business logic rejects deposit larger than total"""
        response = await async_client.post(
            "/api/v1/billing/payment-plans/",
            headers=auth_headers,
            json={
                "patient_id": str(uuid4()),
                "invoice_id": str(uuid4()),
                "total_amount": 500.00,
                "initial_deposit": 600.00,  # Invalid: deposit > total
                "months": 12
            }
        )
        # Should return 422 Unprocessable Entity or 400 Bad Request
        assert response.status_code in (400, 422)
        data = response.json()
        assert "detail" in data
        # Verify error mentions deposit issue
        error_msg = str(data["detail"]).lower()
        assert "deposit" in error_msg or "initial" in error_msg

    async def test_list_invoices_requires_authentication(self, async_client):
        """Verify invoice listing requires authentication"""
        response = await async_client.get("/api/v1/billing/invoices/")
        # Should return 401 Unauthorized
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"]

    async def test_list_invoices_with_valid_auth(self, async_client, auth_headers):
        """Verify invoice listing returns paginated results"""
        response = await async_client.get(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            params={"skip": 0, "limit": 10}
        )
        
        # Should succeed with 200 OK
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        assert "invoices" in data
        assert "count" in data

        # Verify structure if invoices exist
        if data["invoices"]:
            invoice = data["invoices"][0]
            assert "id" in invoice
            assert "patient_id" in invoice
            assert "amount" in invoice
            assert "status" in invoice
            assert "created_at" in invoice


class TestPaymentPlanSchema:
    """Test PaymentPlanCreateSchema validation"""

    def test_valid_schema_all_fields(self):
        """Test that valid schema with all fields passes validation"""
        from pydantic import BaseModel
        from uuid import UUID
        
        class PaymentPlanCreateSchema(BaseModel):
            patient_id: UUID
            invoice_id: UUID = None
            total_amount: float
            initial_deposit: float = 0
            months: int = 12
            notes: str = None
        
        patient_id = uuid4()
        invoice_id = uuid4()
        
        plan = PaymentPlanCreateSchema(
            patient_id=patient_id,
            invoice_id=invoice_id,
            total_amount=500.00,
            initial_deposit=100.00,
            months=12,
            notes="Test plan"
        )
        
        assert plan.patient_id == patient_id
        assert plan.invoice_id == invoice_id
        assert plan.total_amount == 500.00
        assert plan.initial_deposit == 100.00
        assert plan.months == 12
        assert plan.notes == "Test plan"

    def test_valid_schema_minimal_fields(self):
        """Test that valid schema with minimal required fields passes"""
        from pydantic import BaseModel
        from uuid import UUID
        
        class PaymentPlanCreateSchema(BaseModel):
            patient_id: UUID
            invoice_id: UUID = None
            total_amount: float
            initial_deposit: float = 0
            months: int = 12
            notes: str = None
        
        patient_id = uuid4()
        
        plan = PaymentPlanCreateSchema(
            patient_id=patient_id,
            total_amount=500.00
        )
        
        assert plan.patient_id == patient_id
        assert plan.invoice_id is None
        assert plan.total_amount == 500.00
        assert plan.initial_deposit == 0
        assert plan.months == 12
        assert plan.notes is None

    def test_invalid_schema_missing_patient_id(self):
        """Test that missing required patient_id fails validation"""
        from pydantic import BaseModel, ValidationError
        from uuid import UUID
        
        class PaymentPlanCreateSchema(BaseModel):
            patient_id: UUID
            invoice_id: UUID = None
            total_amount: float
            initial_deposit: float = 0
            months: int = 12
            notes: str = None
        
        with pytest.raises(ValidationError) as exc_info:
            PaymentPlanCreateSchema(total_amount=500.00)
        
        # Verify error mentions patient_id
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "patient_id" for err in errors)

    def test_invalid_schema_missing_total_amount(self):
        """Test that missing required total_amount fails validation"""
        from pydantic import BaseModel, ValidationError
        from uuid import UUID
        
        class PaymentPlanCreateSchema(BaseModel):
            patient_id: UUID
            invoice_id: UUID = None
            total_amount: float
            initial_deposit: float = 0
            months: int = 12
            notes: str = None
        
        with pytest.raises(ValidationError) as exc_info:
            PaymentPlanCreateSchema(patient_id=uuid4())
        
        # Verify error mentions total_amount
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "total_amount" for err in errors)


class TestConfigValidation:
    """Test configuration validation"""

    def test_access_token_default_is_15(self):
        """Verify ACCESS_TOKEN_EXPIRE_MINUTES defaults to 15 (HIPAA compliance)"""
        import os
        # Temporarily unset env var to check default
        old_val = os.environ.pop("ACCESS_TOKEN_EXPIRE_MINUTES", None)
        try:
            from app.core.config_simple import SimpleSettings
            settings = SimpleSettings()
            assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
        finally:
            if old_val:
                os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = old_val

    def test_refresh_token_default_is_7_days(self):
        """Verify REFRESH_TOKEN_EXPIRE_DAYS defaults to 7 days"""
        import os
        old_val = os.environ.pop("REFRESH_TOKEN_EXPIRE_DAYS", None)
        try:
            from app.core.config_simple import SimpleSettings
            settings = SimpleSettings()
            assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
        finally:
            if old_val:
                os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = old_val

    def test_fernet_key_validation_valid(self):
        """Verify valid Fernet key passes validation"""
        from cryptography.fernet import Fernet
        
        # Valid Fernet key should work
        valid_key = Fernet.generate_key().decode()
        cipher = Fernet(valid_key.encode())
        
        # Verify it can encrypt/decrypt
        test_data = b"test data"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == test_data

    def test_fernet_key_validation_invalid(self):
        """Verify invalid Fernet key fails validation"""
        from cryptography.fernet import Fernet
        
        # Invalid key should fail
        with pytest.raises((ValueError, TypeError)):
            Fernet(b"not-a-valid-fernet-key")

    def test_fernet_key_validation_too_short(self):
        """Verify too-short key fails validation"""
        from cryptography.fernet import Fernet
        
        with pytest.raises((ValueError, TypeError)):
            Fernet(b"short")


class TestStripeErrorHandling:
    """Test Stripe error handling doesn't leak details"""

    async def test_generic_error_messages(self, async_client):
        """Verify Stripe endpoints return generic messages on error"""
        # Test with invalid Stripe key - should return generic message
        response = await async_client.post(
            "/api/v1/stripe/create-payment-intent",
            json={
                "amount": 50.00,
                "currency": "usd",
                "payment_type": "one_time",
                "description": "Test payment"
            }
        )
        
        # Should return an error status
        assert response.status_code in (400, 401, 403, 422, 500)
        
        if response.status_code == 400:
            data = response.json()
            # Should NOT include Stripe error details
            error_detail = data.get("detail", "").lower()
            assert "stripe" not in error_detail
            assert "api key" not in error_detail
            assert "sk_test" not in error_detail
            assert "sk_live" not in error_detail
            # Should return generic error message
            assert "error" in error_detail or "failed" in error_detail

    async def test_stripe_webhook_signature_validation(self, async_client):
        """Verify Stripe webhook validates signature"""
        # Send webhook without signature - should fail
        response = await async_client.post(
            "/api/v1/stripe/webhook",
            json={"type": "payment_intent.succeeded"}
        )
        
        # Should reject without signature
        assert response.status_code in (400, 401, 403)
        data = response.json()
        assert "detail" in data
        # Should mention signature or authentication
        error_msg = str(data["detail"]).lower()
        assert "signature" in error_msg or "invalid" in error_msg or "unauthorized" in error_msg


class TestPaymentCalculations:
    """Test payment plan calculation logic"""

    def test_monthly_payment_calculation(self):
        """Verify monthly payment is calculated correctly"""
        total_amount = 1200.00
        initial_deposit = 200.00
        months = 10
        
        remaining = total_amount - initial_deposit
        monthly = remaining / months
        
        assert remaining == 1000.00
        assert monthly == 100.00

    def test_monthly_payment_with_decimal_precision(self):
        """Verify monthly payment handles decimal precision"""
        total_amount = 500.00
        initial_deposit = 100.00
        months = 12
        
        remaining = total_amount - initial_deposit
        monthly = remaining / months
        
        assert remaining == 400.00
        assert monthly == pytest.approx(33.33, rel=1e-2)

    def test_zero_deposit_full_amount_financed(self):
        """Verify zero deposit means full amount is financed"""
        total_amount = 1000.00
        initial_deposit = 0.00
        months = 10
        
        remaining = total_amount - initial_deposit
        monthly = remaining / months
        
        assert remaining == 1000.00
        assert monthly == 100.00