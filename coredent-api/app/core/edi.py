"""
EDI Clearinghouse Integration
Electronic claims submission to insurance clearinghouses
"""

import os
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Clearinghouse(str, Enum):
    CHANGE_HEALTHCARE = "change_healthcare"
    WAVE = "wave"
    TAVIS = "tavis"
    DENTAL_ANSWERS = "dental_answers"


class ClaimStatus(str, Enum):
    """X12 277 status codes"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PAID = "paid"
    DENIED = "denied"


class EDIService:
    """
    Electronic Data Interchange service for dental claims
    
    Supports:
    - 837D (Dental Claim) submission
    - 270 (Eligibility Request)
    - 276 (Claim Status Request)
    - 277 (Claim Status Response)
    - 835 (Payment/Remittance)
    """

    def __init__(self, clearinghouse: Optional[Clearinghouse] = None):
        self.clearinghouse = clearinghouse or Clearinghouse(
            os.getenv("CLEARINGHOUSE", "change_healthcare")
        )
        self.environment = os.getenv("EDI_ENV", "sandbox")
        self.sender_id = os.getenv("EDI_SENDER_ID", "")
        self.receiver_id = os.getenv("EDI_RECEIVER_ID", "")
        self.provider_npi = os.getenv("PROVIDER_NPI", "")

    def _generate_isa_segment(self) -> str:
        """Generate ISA segment for X12 envelope (UTC — M8)"""
        timestamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M")
        control_number = str(int(datetime.now(timezone.utc).timestamp()))[-9:]

        return f"ISA*00*          *00*          *ZZ*{self.sender_id:<15}*ZZ*{self.receiver_id:<15}*{timestamp}*U*00401*{control_number}*0*P*>~"

    def _generate_gs_segment(self) -> str:
        """Generate GS segment for X12 envelope (UTC — M8)"""
        now = datetime.now(timezone.utc)
        return f"GS*HC*{self.sender_id}*{self.receiver_id}*{now.strftime('%Y%m%d')}*{now.strftime('%H%M')}*1*X*004010~"

    def _generate_st_segment(self, transaction_code: str, control_number: int = 1) -> str:
        """Generate ST segment for transaction set"""
        return f"ST*{transaction_code}*{str(control_number).zfill(4)}~"

    def create_837d_claim(
        self,
        patient: Dict[str, Any],
        subscriber: Dict[str, Any],
        provider: Dict[str, Any],
        claim_lines: List[Dict[str, Any]],
        claim_number: str,
    ) -> str:
        """
        Create X12 837D dental claim transaction
        
        Returns EDI string ready for submission
        """
        segments = []

        # ISA & GS
        segments.append(self._generate_isa_segment())
        segments.append(self._generate_gs_segment())

        # ST Transaction Set Header
        segments.append(self._generate_st_segment("837D"))

        # BHT Beginning of Hierarchical Transaction
        segments.append(f"BHT*0010*00*{claim_number}*{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}*CH~")

        # Loop 1000A - Submitter Name
        segments.append(f"NM1*41*2*{provider['name']}*****46*{self.sender_id}~")
        segments.append(f"PER*IC*{provider['contact_name']}*TE*{provider['phone']}~")

        # Loop 1000B - Receiver Name
        segments.append(f"NM1*40*2*{self.clearinghouse.value.upper()}*****46*{self.receiver_id}~")

        # Loop 2000A - Billing Provider Hierarchical Level
        segments.append("HL*1**20*1~")
        segments.append(f"NM1*85*1*{provider['last_name']}*{provider['first_name']}****XX*{provider['npi']}~")
        segments.append(f"N3*{provider['address']}~")
        segments.append(f"N4*{provider['city']}*{provider['state']}*{provider['zip']}~")
        segments.append(f"REF*EI*{self.sender_id}~")

        # Loop 2000B - Subscriber Hierarchical Level
        segments.append("HL*2*1*22*0~")
        segments.append(f"SBR*P*{subscriber.get('relationship', 'self')}*******CI~")
        segments.append(f"NM1*IL*1*{subscriber['last_name']}*{subscriber['first_name']}****MI*{subscriber.get('member_id', '')}~")
        segments.append(f"N3*{subscriber.get('address', '')}~")
        segments.append(f"N4*{subscriber.get('city', '')}*{subscriber.get('state', '')}*{subscriber.get('zip', '')}~")

        # Loop 2000C - Patient Hierarchical Level
        if patient.get('is_subscriber', True) is False:
            segments.append("HL*3*2*22*0~")
            segments.append(f"NM1*QC*1*{patient['last_name']}*{patient['first_name']}~")
            segments.append(f"N3*{patient.get('address', '')}~")
            segments.append(f"N4*{patient.get('city', '')}*{patient.get('state', '')}*{patient.get('zip', '')}~")

        # Loop 2300 - Claim Information
        segments.append(f"CLM*{claim_number}*{claim_lines[0].get('charged_amount', '0')}**{claim_lines[0].get('service_code', 'D0120')}*1*Y*A*Y*I~")

        # DTP - Service Dates
        if claim_lines[0].get('service_date'):
            segments.append(f"DTP*431*D8*{claim_lines[0]['service_date']}~")

        # Loop 2400 - Service Lines
        for idx, line in enumerate(claim_lines, 1):
            segments.append(f"LX*{idx}~")
            segments.append(f"SOA*{line.get('service_code', 'D0120')}**{line.get('charged_amount', '0')}*1*1~")
            segments.append(f"DTP*472*D8*{line.get('service_date', datetime.now(timezone.utc).strftime('%Y%m%d'))}~")

            # Tooth code if present
            if line.get('tooth_code'):
                segments.append(f"TOO*JP*{line['tooth_code']}~")

            # Surface codes if present
            if line.get('surface_codes'):
                segments.append(f"TOO*JF*{line['surface_codes']}~")

        # SE Transaction Set Trailer
        segment_count = len(segments) - 2  # Exclude ISA and GS
        segments.append(f"SE*{segment_count}*0001~")

        # GE Functional Group Trailer
        segments.append("GE*1*1~")

        # IEA Interchange Control Trailer
        segments.append("IEA*1*000000001~")

        return "".join(segments)

    async def submit_claim(self, edi_claim: str) -> Dict[str, Any]:
        """Reject use of unimplemented generic clearinghouse adapters.

        Production claim submission is implemented by the DentalXChange API
        endpoints. Returning synthetic acceptance here would corrupt claim
        state, so this legacy adapter intentionally fails closed.
        """
        raise RuntimeError(
            "Generic EDI clearinghouse submission is not configured; use DentalXChange"
        )

    async def check_claim_status(self, confirmation_number: str) -> Dict[str, Any]:
        """Fail closed until a real generic status adapter is implemented."""
        raise RuntimeError(
            "Generic EDI claim status is not configured; use DentalXChange"
        )

    async def download_era(self, era_id: str) -> Dict[str, Any]:
        """Fail closed until a real ERA/835 adapter is implemented."""
        raise RuntimeError(
            "Generic EDI ERA download is not configured; use DentalXChange"
        )


# Singleton instance
edi_service = EDIService()


# Convenience functions

async def submit_dental_claim(
    patient_data: Dict[str, Any],
    subscriber_data: Dict[str, Any],
    provider_data: Dict[str, Any],
    claim_lines: List[Dict[str, Any]],
    claim_number: str,
) -> Dict[str, Any]:
    """Submit a dental claim via EDI"""
    edi_claim = edi_service.create_837d_claim(
        patient=patient_data,
        subscriber=subscriber_data,
        provider=provider_data,
        claim_lines=claim_lines,
        claim_number=claim_number,
    )

    return await edi_service.submit_claim(edi_claim)


async def check_claim_status(confirmation_number: str) -> Dict[str, Any]:
    """Check status of a submitted claim"""
    return await edi_service.check_claim_status(confirmation_number)
