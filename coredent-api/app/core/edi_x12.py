"""
ANSI ASC X12 EDI 837D (Dental Claim) Generator and 835 (ERA) Parser
Compliant with HIPAA ANSI ASC X12N 005010X224A2 (837D) and 005010X221A1 (835).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class X12ClaimServiceLine:
    line_number: int
    procedure_code: str  # CDT code e.g. "D0120", "D2391"
    fee: Decimal
    date_of_service: date
    tooth_number: Optional[str] = None
    surface: Optional[str] = None
    quantity: int = 1


@dataclass
class X12DentalClaim:
    claim_id: str
    payer_id: str
    payer_name: str
    subscriber_id: str
    subscriber_first_name: str
    subscriber_last_name: str
    subscriber_dob: date
    subscriber_gender: str  # "M", "F", "U"
    patient_first_name: str
    patient_last_name: str
    patient_dob: date
    patient_gender: str
    billing_provider_npi: str
    billing_provider_name: str
    billing_provider_tax_id: str
    service_facility_npi: Optional[str]
    total_claim_charge: Decimal
    service_lines: List[X12ClaimServiceLine] = field(default_factory=list)
    diagnosis_codes: List[str] = field(default_factory=list)


@dataclass
class X12EraServiceAdjustment:
    group_code: str  # CO (Contractual), PR (Patient Resp), OA (Other)
    reason_code: str  # CARC code (1=Deductible, 2=Coinsurance, 45=Exceeds Fee Sched, 96=Non-covered)
    amount: Decimal


@dataclass
class X12EraServiceLine:
    line_number: int
    procedure_code: str
    line_charge: Decimal
    line_paid: Decimal
    adjustments: List[X12EraServiceAdjustment] = field(default_factory=list)


@dataclass
class X12EraClaim:
    claim_number: str
    claim_status_code: str  # 1=Processed Primary, 2=Processed Secondary, 4=Denied, 22=Reversal
    total_charge: Decimal
    total_paid: Decimal
    patient_responsibility: Decimal
    payer_claim_control_number: Optional[str] = None
    adjustments: List[X12EraServiceAdjustment] = field(default_factory=list)
    service_lines: List[X12EraServiceLine] = field(default_factory=list)


@dataclass
class X12EraRemittance:
    check_number: str
    payment_method: str  # ACH, CHK, NON
    payment_amount: Decimal
    payment_date: Optional[date]
    payer_name: str
    payer_id: str
    payee_name: str
    payee_npi: str
    claims: List[X12EraClaim] = field(default_factory=list)


class X12837DGenerator:
    """Generates standard ANSI ASC X12 005010X224A2 Dental Claim documents."""

    @staticmethod
    def generate(claim: X12DentalClaim, control_num: int = 1) -> str:
        ctrl = f"{control_num:09d}"
        now = datetime.now(timezone.utc)
        ymd = now.strftime("%y%m%d")
        ymd_full = now.strftime("%Y%m%d")
        hm = now.strftime("%H%M")

        segments = []

        # ISA: Interchange Control Header
        segments.append(
            f"ISA*00*          *00*          *ZZ*COREDENT       *ZZ*{claim.payer_id.ljust(15)[:15]}*{ymd}*{hm}*^*00501*{ctrl}*0*P*:~"
        )
        # GS: Functional Group Header
        segments.append(
            f"GS*HC*COREDENT*{claim.payer_id}*{ymd_full}*{hm}*1*X*005010X224A2~"
        )
        # ST: Transaction Set Header
        segments.append(f"ST*837*{ctrl}*005010X224A2~")
        segments.append(f"BHT*0019*00*{ctrl}*{ymd_full}*{hm}*CH~")

        # 1000A: Submitter
        segments.append("NM1*41*2*COREDENT HEALTH*****46*COREDENT01~")
        segments.append("PER*IC*EDI SUPPORT*TE*8005550199~")

        # 1000B: Receiver / Payer
        segments.append(f"NM1*40*2*{claim.payer_name}*****46*{claim.payer_id}~")

        # 2000A: Billing Provider Hierarchical Level
        segments.append("HL*1**20*1~")
        segments.append("PRV*BI*PXC*122300000X~")
        segments.append(f"NM1*85*2*{claim.billing_provider_name}*****XX*{claim.billing_provider_npi}~")
        segments.append(f"N3*100 HEALTHCARE WAY~")
        segments.append("N4*SAN FRANCISCO*CA*94105~")
        segments.append(f"REF*EI*{claim.billing_provider_tax_id}~")

        # 2000B: Subscriber Hierarchical Level
        segments.append("HL*2*1*22*0~")
        segments.append("SBR*P*18*******CI~")
        gender_code = "M" if claim.subscriber_gender.upper().startswith("M") else "F"
        segments.append(
            f"NM1*IL*1*{claim.subscriber_last_name}*{claim.subscriber_first_name}****MI*{claim.subscriber_id}~"
        )
        segments.append(f"DMG*D8*{claim.subscriber_dob.strftime('%Y%m%d')}*{gender_code}~")

        # 2300: Claim Information
        total_str = f"{claim.total_claim_charge:.2f}"
        segments.append(f"CLM*{claim.claim_id}*{total_str}***11:B:1*Y*A*Y*Y~")
        if claim.diagnosis_codes:
            dx = claim.diagnosis_codes[0]
            segments.append(f"HI*BK:{dx}~")

        # 2400: Service Lines
        for idx, line in enumerate(claim.service_lines, start=1):
            line_fee = f"{line.fee:.2f}"
            segments.append(f"LX*{idx}~")
            # SV3: Dental Service Line (ADA Procedure Code, Fee, Facility Code, Tooth, Surface)
            tooth_part = f":{line.tooth_number}" if line.tooth_number else ""
            surface_part = f":{line.surface}" if line.surface else ""
            segments.append(
                f"SV3*AD:{line.procedure_code}*{line_fee}**11*{line.quantity}*{tooth_part}{surface_part}~"
            )
            segments.append(f"DTP*472*D8*{line.date_of_service.strftime('%Y%m%d')}~")

        # SE: Transaction Set Trailer (count includes ST and SE)
        seg_count = len(segments) - 2 + 1  # excluding ISA, GS, but including SE
        segments.append(f"SE*{seg_count + 1}*{ctrl}~")

        # GE & IEA
        segments.append(f"GE*1*1~")
        segments.append(f"IEA*1*{ctrl}~")

        return "\n".join(segments)


class X12835Parser:
    """Parses standard ANSI ASC X12 005010X221A1 835 Remittance Advice documents."""

    @classmethod
    def parse(cls, x12_text: str) -> X12EraRemittance:
        clean = x12_text.replace("\r", "").replace("\n", "")
        # Detect segment delimiter (typically '~')
        delimiters = ["~", ";", "\n"]
        active_delim = "~"
        for d in delimiters:
            if d in clean[:150]:
                active_delim = d
                break

        raw_segments = [s.strip() for s in clean.split(active_delim) if s.strip()]

        remittance = X12EraRemittance(
            check_number="",
            payment_method="CHK",
            payment_amount=Decimal("0.00"),
            payment_date=None,
            payer_name="",
            payer_id="",
            payee_name="",
            payee_npi="",
            claims=[],
        )

        current_claim: Optional[X12EraClaim] = None
        current_service: Optional[X12EraServiceLine] = None

        for seg_str in raw_segments:
            parts = seg_str.split("*")
            tag = parts[0].upper()

            if tag == "BPR":
                # Financial Information: BPR*I*TotalAmt*C*PaymentMethod*...*PaymentDate
                try:
                    if len(parts) > 2 and parts[2]:
                        remittance.payment_amount = Decimal(parts[2])
                    if len(parts) > 4 and parts[4]:
                        remittance.payment_method = parts[4]
                    if len(parts) > 16 and parts[16]:
                        remittance.payment_date = datetime.strptime(parts[16][:8], "%Y%m%d").date()
                except Exception:
                    pass

            elif tag == "TRN":
                # Trace Number: TRN*1*CheckOrEftTraceNumber
                if len(parts) > 2:
                    remittance.check_number = parts[2]

            elif tag == "N1":
                # Entity Name: N1*PR*PayerName (or N1*PE*Payee)
                if len(parts) > 2:
                    entity_type = parts[1].upper()
                    if entity_type == "PR":
                        remittance.payer_name = parts[2]
                        if len(parts) > 4 and parts[3] == "XV":
                            remittance.payer_id = parts[4]
                    elif entity_type == "PE":
                        remittance.payee_name = parts[2]
                        if len(parts) > 4 and parts[3] == "XX":
                            remittance.payee_npi = parts[4]

            elif tag == "CLP":
                # Claim Payment: CLP*ClaimID*StatusCode*TotalCharge*TotalPaid*PatientResp*...
                if current_claim:
                    remittance.claims.append(current_claim)
                    current_claim = None
                    current_service = None

                claim_num = parts[1] if len(parts) > 1 else ""
                status_code = parts[2] if len(parts) > 2 else "1"
                charge = Decimal(parts[3]) if len(parts) > 3 and parts[3] else Decimal("0.00")
                paid = Decimal(parts[4]) if len(parts) > 4 and parts[4] else Decimal("0.00")
                pat_resp = Decimal(parts[5]) if len(parts) > 5 and parts[5] else Decimal("0.00")
                payer_ctrl = parts[7] if len(parts) > 7 else None

                current_claim = X12EraClaim(
                    claim_number=claim_num,
                    claim_status_code=status_code,
                    total_charge=charge,
                    total_paid=paid,
                    patient_responsibility=pat_resp,
                    payer_claim_control_number=payer_ctrl,
                    adjustments=[],
                    service_lines=[],
                )

            elif tag == "CAS":
                # Claim Adjustment: CAS*GroupCode*ReasonCode*Amount
                if len(parts) >= 4 and parts[2] and parts[3]:
                    grp = parts[1]
                    code = parts[2]
                    try:
                        amt = Decimal(parts[3])
                    except Exception:
                        amt = Decimal("0.00")
                    adj = X12EraServiceAdjustment(group_code=grp, reason_code=code, amount=amt)

                    if current_service:
                        current_service.adjustments.append(adj)
                    elif current_claim:
                        current_claim.adjustments.append(adj)

            elif tag == "SVC":
                # Service Line: SVC*AD:ProcedureCode*Charge*Paid
                proc = ""
                charge = Decimal("0.00")
                paid = Decimal("0.00")
                if len(parts) > 1 and parts[1]:
                    sub_parts = parts[1].split(":")
                    proc = sub_parts[-1]
                if len(parts) > 2 and parts[2]:
                    try:
                        charge = Decimal(parts[2])
                    except Exception:
                        pass
                if len(parts) > 3 and parts[3]:
                    try:
                        paid = Decimal(parts[3])
                    except Exception:
                        pass

                line_num = len(current_claim.service_lines) + 1 if current_claim else 1
                current_service = X12EraServiceLine(
                    line_number=line_num,
                    procedure_code=proc,
                    line_charge=charge,
                    line_paid=paid,
                    adjustments=[],
                )
                if current_claim:
                    current_claim.service_lines.append(current_service)

        if current_claim:
            remittance.claims.append(current_claim)

        return remittance
