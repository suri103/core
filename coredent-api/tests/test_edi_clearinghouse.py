"""
Tests for ANSI ASC X12 837D Generator and 835 Remittance Auto-Reconciliation
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.edi_x12 import (
    X12835Parser,
    X12837DGenerator,
    X12ClaimServiceLine,
    X12DentalClaim,
)
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentStatus
from app.models.insurance import ClaimStatus, InsuranceCarrier, InsuranceClaim, PatientInsurance


class TestX12837DGenerator:
    def test_generates_valid_837d_structure(self):
        claim = X12DentalClaim(
            claim_id="CLM1001",
            payer_id="PAYER99",
            payer_name="Delta Dental",
            subscriber_id="SUB98765",
            subscriber_first_name="Jane",
            subscriber_last_name="Doe",
            subscriber_dob=date(1985, 4, 12),
            subscriber_gender="F",
            patient_first_name="Jane",
            patient_last_name="Doe",
            patient_dob=date(1985, 4, 12),
            patient_gender="F",
            billing_provider_npi="1234567890",
            billing_provider_name="Downtown Dental LLC",
            billing_provider_tax_id="123456789",
            service_facility_npi="1234567890",
            total_claim_charge=Decimal("250.00"),
            service_lines=[
                X12ClaimServiceLine(
                    line_number=1,
                    procedure_code="D0120",
                    fee=Decimal("75.00"),
                    date_of_service=date(2026, 10, 1),
                ),
                X12ClaimServiceLine(
                    line_number=2,
                    procedure_code="D2391",
                    fee=Decimal("175.00"),
                    date_of_service=date(2026, 10, 1),
                    tooth_number="14",
                    surface="MO",
                ),
            ],
            diagnosis_codes=["K02.9"],
        )

        x12 = X12837DGenerator.generate(claim)
        assert "ISA*00*" in x12
        assert "GS*HC*COREDENT*PAYER99*" in x12
        assert "ST*837*" in x12
        assert "BHT*0019*00*" in x12
        assert "NM1*40*2*Delta Dental" in x12
        assert "NM1*85*2*Downtown Dental LLC*****XX*1234567890" in x12
        assert "CLM*CLM1001*250.00" in x12
        assert "SV3*AD:D0120*75.00" in x12
        assert "SV3*AD:D2391*175.00**11*1*:14:MO" in x12
        assert "SE*" in x12


class TestX12835Parser:
    def test_parses_sample_835_remittance(self):
        sample_835 = (
            "ISA*00*          *00*          *ZZ*PAYER          *ZZ*COREDENT       *261019*1400*^*00501*000000001*0*P*:~"
            "GS*HP*PAYER*COREDENT*20261019*1400*1*X*005010X221A1~"
            "ST*835*0001~"
            "BPR*I*210.00*C*ACH*CCP*01*123456789*DA*987654321*1234567890**01*999999999*DA*111111*20261019~"
            "TRN*1*CHK99887766*1999999999~"
            "N1*PR*Delta Dental Insurance*XV*PAYER99~"
            "N1*PE*Downtown Dental*XX*1234567890~"
            "CLP*CLM1001*1*250.00*210.00*40.00*12*PAYERCTRL123~"
            "CAS*CO*45*40.00~"
            "SVC*AD:D0120*75.00*75.00~"
            "SVC*AD:D2391*175.00*135.00~"
            "CAS*CO*45*40.00~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )

        remit = X12835Parser.parse(sample_835)
        assert remit.check_number == "CHK99887766"
        assert remit.payment_method == "ACH"
        assert remit.payment_amount == Decimal("210.00")
        assert remit.payer_name == "Delta Dental Insurance"
        assert len(remit.claims) == 1

        clm = remit.claims[0]
        assert clm.claim_number == "CLM1001"
        assert clm.total_charge == Decimal("250.00")
        assert clm.total_paid == Decimal("210.00")
        assert clm.patient_responsibility == Decimal("40.00")
        assert len(clm.adjustments) == 1
        assert clm.adjustments[0].group_code == "CO"
        assert clm.adjustments[0].reason_code == "45"


@pytest.mark.asyncio
class TestEraReconciliationEndpoints:
    async def test_reconcile_era_text(
        self, async_client: AsyncClient, auth_headers: dict, db_session, test_patient, test_practice
    ):
        # 1. Create invoice
        invoice = Invoice(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            invoice_number="INV-EDI-01",
            subtotal=Decimal("250.00"),
            total=Decimal("250.00"),
            line_items=[{"description": "D0120 Periodic oral evaluation", "quantity": 1, "unit_price": 250.00, "total": 250.00}],
            status=InvoiceStatus.PENDING,
            due_date=date(2026, 11, 1),
        )
        db_session.add(invoice)
        await db_session.flush()

        # 2. Create Insurance Carrier & Patient Insurance
        carrier = InsuranceCarrier(
            practice_id=test_practice.id,
            name="MetLife Dental",
            payer_id="PAYER01",
        )
        db_session.add(carrier)
        await db_session.flush()

        patient_insurance = PatientInsurance(
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            subscriber_id="SUB12345",
        )
        db_session.add(patient_insurance)
        await db_session.flush()

        # 3. Create Insurance Claim
        claim = InsuranceClaim(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            patient_insurance_id=patient_insurance.id,
            carrier_id=carrier.id,
            claim_number="CLM-REC-001",
            status=ClaimStatus.SUBMITTED,
            billed_amount=Decimal("250.00"),
            service_date=date(2026, 10, 1),
            procedure_codes=[{"procedureCode": "D0120", "fee": 250.00}],
        )
        db_session.add(claim)
        await db_session.commit()

        # 4. Submit 835 text
        era_x12 = (
            "ST*835*0001~"
            "BPR*I*200.00*C*CHK*CCP*01*123*DA*987*123**01*999*DA*111*20261019~"
            "TRN*1*CHECK-ERA-4422~"
            "N1*PR*MetLife Dental~"
            "CLP*CLM-REC-001*1*250.00*200.00*50.00~"
            "CAS*PR*1*50.00~"
            "SE*7*0001~"
        )

        response = await async_client.post(
            "/api/v1/edi/era/reconcile-text",
            headers=auth_headers,
            json={"era_text": era_x12},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["remittance_check_number"] == "CHECK-ERA-4422"
        assert data["matched_count"] == 1
        assert data["total_posted_to_ledger"] == 200.00

        # Verify claim status in DB
        await db_session.refresh(claim)
        assert claim.status == ClaimStatus.PARTIALLY_APPROVED
        assert claim.paid_amount == Decimal("200.00")
        assert claim.patient_responsibility == Decimal("50.00")

        invoice_id = invoice.id

        # Verify invoice balance in DB
        inv_check = (
            await db_session.execute(
                select(Invoice)
                .options(selectinload(Invoice.payments))
                .execution_options(populate_existing=True)
                .where(Invoice.id == invoice_id)
            )
        ).scalar_one()
        assert inv_check.balance_due == Decimal("50.00")
        assert inv_check.status == InvoiceStatus.PARTIALLY_PAID
