"""
Clearinghouse & EDI 835/837 Remittance Reconciliation Service
Automates EDI 837D Dental Claim Generation, 835 Remittance Parsing,
and ledger auto-posting for DentalXChange and Change Healthcare.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_audit_event
from app.core.edi_x12 import (
    X12835Parser,
    X12837DGenerator,
    X12ClaimServiceLine,
    X12DentalClaim,
    X12EraRemittance,
)
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod, PaymentStatus
from app.models.insurance import ClaimStatus, InsuranceCarrier, InsuranceClaim, PatientInsurance
from app.models.patient import Patient
from app.models.practice import Practice
from app.models.user import User

logger = logging.getLogger(__name__)

CARC_DESCRIPTIONS: Dict[str, str] = {
    "1": "Deductible Amount",
    "2": "Coinsurance Amount",
    "3": "Co-payment Amount",
    "45": "Charge exceeds maximum allowable fee schedule amount (Contractual Adjustment)",
    "96": "Non-covered charge(s). At least one remark code must be provided",
    "97": "The benefit for this service is included in the payment/allowance for another service/procedure",
    "18": "Exact duplicate claim/service",
    "29": "Time limit for filing has expired",
    "204": "This service/equipment/drug is not covered under the patient's current benefit plan",
}


class ClearinghouseService:
    """Manages EDI claims lifecycle and ERA payment posting."""

    @staticmethod
    async def export_claim_837d(
        db: AsyncSession,
        claim_id: UUID,
        practice_id: UUID,
    ) -> str:
        """Generate ANSI ASC X12 837D payload for a dental claim."""
        stmt = (
            select(InsuranceClaim, Patient, PatientInsurance, Practice, InsuranceCarrier)
            .join(Patient, InsuranceClaim.patient_id == Patient.id)
            .join(PatientInsurance, InsuranceClaim.patient_insurance_id == PatientInsurance.id)
            .join(InsuranceCarrier, InsuranceClaim.carrier_id == InsuranceCarrier.id)
            .join(Practice, InsuranceClaim.practice_id == Practice.id)
            .where(
                InsuranceClaim.id == claim_id,
                InsuranceClaim.practice_id == practice_id,
            )
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise ValueError("Claim not found in this practice")

        claim, patient, insurance, practice, carrier = row

        # Extract provider
        provider_name = practice.name
        provider_npi = getattr(practice, "npi", "") or "1999999999"
        tax_id = getattr(practice, "tax_id", "") or "000000000"

        # Build service lines from JSON procedure_codes
        service_lines: List[X12ClaimServiceLine] = []
        raw_procs = claim.procedure_codes or []
        for idx, p in enumerate(raw_procs, start=1):
            fee = Decimal(str(p.get("fee") or p.get("cost") or 0))
            code = str(p.get("procedureCode") or p.get("code") or "D0120")
            dos = claim.service_date
            service_lines.append(
                X12ClaimServiceLine(
                    line_number=idx,
                    procedure_code=code,
                    fee=fee,
                    date_of_service=dos,
                    tooth_number=p.get("tooth"),
                    surface=p.get("surface"),
                )
            )

        if not service_lines:
            service_lines.append(
                X12ClaimServiceLine(
                    line_number=1,
                    procedure_code="D0150",
                    fee=Decimal(str(claim.billed_amount or "0.00")),
                    date_of_service=claim.service_date,
                )
            )

        x12_claim = X12DentalClaim(
            claim_id=claim.claim_number or str(claim.id),
            payer_id=carrier.payer_id or "PAYER01",
            payer_name=carrier.name or "Dental Payer",
            subscriber_id=insurance.subscriber_id or "SUB12345",
            subscriber_first_name=patient.first_name,
            subscriber_last_name=patient.last_name,
            subscriber_dob=patient.date_of_birth or claim.service_date,
            subscriber_gender=getattr(patient, "gender", "U") or "U",
            patient_first_name=patient.first_name,
            patient_last_name=patient.last_name,
            patient_dob=patient.date_of_birth or claim.service_date,
            patient_gender=getattr(patient, "gender", "U") or "U",
            billing_provider_npi=provider_npi,
            billing_provider_name=provider_name,
            billing_provider_tax_id=tax_id,
            service_facility_npi=provider_npi,
            total_claim_charge=Decimal(str(claim.billed_amount or 0)),
            service_lines=service_lines,
            diagnosis_codes=claim.diagnosis_codes or [],
        )

        return X12837DGenerator.generate(x12_claim)

    @staticmethod
    async def process_era_835(
        db: AsyncSession,
        era_text: str,
        practice_id: UUID,
        current_user: User,
        request: Any = None,
    ) -> Dict[str, Any]:
        """
        Ingest and reconcile ANSI ASC X12 835 Remittance Advice against practice claims.
        Updates claim statuses, writes payment transactions to the invoice ledger,
        and logs audit trail.
        """
        remittance: X12EraRemittance = X12835Parser.parse(era_text)

        reconciled_claims: List[Dict[str, Any]] = []
        unmatched_claims: List[Dict[str, Any]] = []
        total_posted = Decimal("0.00")

        for era_claim in remittance.claims:
            claim_ident = era_claim.claim_number.strip()
            # Match claim by claim_number or external ID
            claim_stmt = select(InsuranceClaim).where(
                InsuranceClaim.practice_id == practice_id,
                (InsuranceClaim.claim_number == claim_ident)
                | (InsuranceClaim.confirmation_number == claim_ident),
            )
            claim_res = await db.execute(claim_stmt)
            claim = claim_res.scalar_one_or_none()

            # If not matched directly, check if claim_ident is a UUID
            if not claim:
                try:
                    c_uuid = UUID(claim_ident)
                    claim_res = await db.execute(
                        select(InsuranceClaim).where(
                            InsuranceClaim.id == c_uuid,
                            InsuranceClaim.practice_id == practice_id,
                        )
                    )
                    claim = claim_res.scalar_one_or_none()
                except (ValueError, TypeError):
                    pass

            if not claim:
                unmatched_claims.append({
                    "claim_number": claim_ident,
                    "total_charge": float(era_claim.total_charge),
                    "total_paid": float(era_claim.total_paid),
                    "status_code": era_claim.claim_status_code,
                    "reason": "No matching active claim found in practice",
                })
                continue

            # Interpret CARC adjustment codes
            carc_details = []
            contractual_adj = Decimal("0.00")
            for adj in era_claim.adjustments:
                desc = CARC_DESCRIPTIONS.get(adj.reason_code, f"Adjustment Code {adj.reason_code}")
                carc_details.append(f"{adj.group_code}-{adj.reason_code}: {desc} (${adj.amount:.2f})")
                if adj.group_code == "CO":
                    contractual_adj += adj.amount

            # Update InsuranceClaim record
            claim.paid_amount = era_claim.total_paid
            claim.patient_responsibility = era_claim.patient_responsibility
            claim.paid_date = remittance.payment_date or datetime.now(timezone.utc).date()

            # Adjudicate status
            if era_claim.claim_status_code == "4" or era_claim.total_paid == 0:
                claim.status = ClaimStatus.DENIED
                claim.denial_reason = "; ".join(carc_details) or "Payer denied coverage"
            elif era_claim.total_paid >= Decimal(str(claim.billed_amount or 0)):
                claim.status = ClaimStatus.PAID
                claim.denial_reason = None
            else:
                claim.status = ClaimStatus.PARTIALLY_APPROVED
                claim.denial_reason = "; ".join(carc_details) if carc_details else None

            # Auto-post payment to patient invoice ledger if open invoice exists
            posted_payment_id = None
            if era_claim.total_paid > 0:
                inv_res = await db.execute(
                    select(Invoice)
                    .options(selectinload(Invoice.payments))
                    .where(
                        Invoice.practice_id == practice_id,
                        Invoice.patient_id == claim.patient_id,
                        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]),
                    ).order_by(Invoice.created_at.desc())
                )
                invoice = inv_res.scalars().first()
                if invoice:
                    payment = Payment(
                        practice_id=practice_id,
                        invoice_id=invoice.id,
                        patient_id=claim.patient_id,
                        amount=era_claim.total_paid,
                        payment_method=PaymentMethod.INSURANCE,
                        status=PaymentStatus.COMPLETED,
                        transaction_id=f"ERA-{remittance.check_number or 'EFT'}-{claim.claim_number}",
                        notes=f"Auto-posted from 835 ERA (Check #{remittance.check_number or 'EFT'}, Payer: {remittance.payer_name})",
                    )
                    db.add(payment)
                    invoice.payments.append(payment)
                    await db.flush()
                    posted_payment_id = str(payment.id)
                    total_posted += era_claim.total_paid

                    # Re-calculate invoice status using dynamic balance_due property
                    if invoice.balance_due <= Decimal("0.00"):
                        invoice.status = InvoiceStatus.PAID
                    else:
                        invoice.status = InvoiceStatus.PARTIALLY_PAID

            reconciled_claims.append({
                "claim_id": str(claim.id),
                "claim_number": claim.claim_number,
                "adjudicated_status": claim.status.value,
                "billed_amount": float(claim.billed_amount or 0),
                "paid_amount": float(era_claim.total_paid),
                "patient_responsibility": float(era_claim.patient_responsibility),
                "contractual_adjustment": float(contractual_adj),
                "carc_codes": carc_details,
                "posted_payment_id": posted_payment_id,
            })

            await log_audit_event(
                db,
                current_user,
                "era_claim_reconciled",
                "insurance_claim",
                claim.id,
                request,
                {
                    "check_number": remittance.check_number,
                    "paid_amount": float(era_claim.total_paid),
                    "status": claim.status.value,
                },
            )

        await db.commit()

        return {
            "success": True,
            "remittance_check_number": remittance.check_number,
            "payment_method": remittance.payment_method,
            "payment_date": remittance.payment_date.isoformat() if remittance.payment_date else None,
            "payer_name": remittance.payer_name,
            "total_remittance_amount": float(remittance.payment_amount),
            "total_posted_to_ledger": float(total_posted),
            "matched_count": len(reconciled_claims),
            "unmatched_count": len(unmatched_claims),
            "reconciled_claims": reconciled_claims,
            "unmatched_claims": unmatched_claims,
        }
