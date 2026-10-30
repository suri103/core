"""
Legacy Migration Importers Service
Automated ETL converters for ingesting patient records, procedure logs,
appointments, and balances from Open Dental, Dentrix, and Eaglesoft.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.search_index import hmac_index, update_patient_search_indexes
from app.models.appointment import AppointmentStatus, AppointmentTypeEnum
from app.models.clinical import ClinicalNote, NoteType
from app.models.patient import Gender, Patient, PatientStatus
from app.models.user import User

logger = logging.getLogger(__name__)


def parse_date(raw: Any) -> Optional[date]:
    """Parse multiple common date formats into datetime.date."""
    if not raw:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()

    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", "0001-01-01", "0000-00-00"):
        return None

    # Strip time part if present
    if " " in s:
        s = s.split(" ")[0]
    elif "T" in s:
        s = s.split("T")[0]

    formats = (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%Y%m%d",
        "%Y/%m/%d",
        "%m-%d-%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def parse_gender(raw: Any, is_opendental_num: bool = False) -> Gender:
    """Normalize gender representation from various EHRs."""
    if raw is None:
        return Gender.OTHER
    s = str(raw).strip().lower()
    if is_opendental_num:
        if s == "0":
            return Gender.MALE
        elif s == "1":
            return Gender.FEMALE
        return Gender.OTHER

    if s in ("m", "male", "man"):
        return Gender.MALE
    elif s in ("f", "female", "woman"):
        return Gender.FEMALE
    return Gender.OTHER


def clean_phone(raw: Any) -> Optional[str]:
    """Normalize phone string."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    cleaned = str(raw).strip()
    return cleaned if cleaned else None


def clean_email(raw: Any) -> Optional[str]:
    """Validate and lower-case email."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    if "@" in s and "." in s and not s.startswith("@") and not s.endswith("."):
        return s
    return None


def normalize_cdt_code(raw: Any) -> str:
    """Ensure CDT code follows D0000-D9999 dental nomenclature."""
    if not raw:
        return ""
    code = str(raw).strip().upper()
    if not code.startswith("D") and code.isdigit() and len(code) == 4:
        return f"D{code}"
    return code


@dataclass
class NormalizedProcedure:
    procedure_code: str
    description: str
    fee: Decimal
    procedure_date: date
    tooth_number: Optional[str] = None
    surface: Optional[str] = None


@dataclass
class NormalizedAppointment:
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: AppointmentStatus
    appointment_type: AppointmentTypeEnum
    notes: Optional[str] = None


@dataclass
class NormalizedPatientRecord:
    row_num: int
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Gender = Gender.OTHER
    email: Optional[str] = None
    phone: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    external_id: Optional[str] = None
    procedures: List[NormalizedProcedure] = field(default_factory=list)
    appointments: List[NormalizedAppointment] = field(default_factory=list)


class OpenDentalAdapter:
    """Adapter for Open Dental exports (PatNum, LName, FName, etc.)."""

    @staticmethod
    def identify(headers: List[str]) -> bool:
        lower_headers = [h.lower() for h in headers]
        return "patnum" in lower_headers or ("fname" in lower_headers and "lname" in lower_headers)

    @classmethod
    def transform_row(cls, row: Dict[str, Any], idx: int) -> Tuple[Optional[NormalizedPatientRecord], Optional[str]]:
        fn = str(row.get("FName") or row.get("fname") or "").strip()
        ln = str(row.get("LName") or row.get("lname") or "").strip()
        raw_dob = row.get("Birthdate") or row.get("birthdate") or row.get("DOB") or row.get("dob")
        dob = parse_date(raw_dob)

        if not fn or not ln:
            return None, f"Row {idx}: Missing patient first or last name"
        if not dob:
            return None, f"Row {idx}: Missing or invalid Birthdate ({raw_dob})"

        gender = parse_gender(row.get("Gender") or row.get("gender"), is_opendental_num=True)
        phone = clean_phone(row.get("WirelessPhone") or row.get("wirelessphone") or row.get("HmPhone") or row.get("hmphone"))
        email = clean_email(row.get("Email") or row.get("email"))

        record = NormalizedPatientRecord(
            row_num=idx,
            first_name=fn,
            last_name=ln,
            date_of_birth=dob,
            gender=gender,
            email=email,
            phone=phone,
            address_street=str(row.get("Address") or row.get("address") or "").strip() or None,
            address_city=str(row.get("City") or row.get("city") or "").strip() or None,
            address_state=str(row.get("State") or row.get("state") or "").strip() or None,
            address_zip=str(row.get("Zip") or row.get("zip") or "").strip() or None,
            external_id=str(row.get("PatNum") or row.get("patnum") or "").strip() or None,
        )

        # Parse inline procedure if procedurelog columns are joined
        proc_code = normalize_cdt_code(row.get("CodeNum") or row.get("ADACode") or row.get("adacode") or row.get("ProcCode"))
        if proc_code:
            proc_fee = Decimal(str(row.get("ProcFee") or row.get("fee") or "0.00"))
            proc_date = parse_date(row.get("ProcDate") or row.get("procdate")) or dob
            record.procedures.append(
                NormalizedProcedure(
                    procedure_code=proc_code,
                    description=str(row.get("ProcDescript") or row.get("description") or "Dental Procedure"),
                    fee=proc_fee,
                    procedure_date=proc_date,
                    tooth_number=str(row.get("ToothNum") or "").strip() or None,
                    surface=str(row.get("Surf") or "").strip() or None,
                )
            )

        return record, None


class DentrixAdapter:
    """Adapter for Dentrix G4-G7 exports (ChartNumber, FirstName, etc.)."""

    @staticmethod
    def identify(headers: List[str]) -> bool:
        lower_headers = [h.lower() for h in headers]
        return "chartnumber" in lower_headers or (
            "firstname" in lower_headers
            and "lastname" in lower_headers
            and "patientid" not in lower_headers
            and "patnum" not in lower_headers
        )

    @classmethod
    def transform_row(cls, row: Dict[str, Any], idx: int) -> Tuple[Optional[NormalizedPatientRecord], Optional[str]]:
        fn = str(row.get("FirstName") or row.get("firstname") or "").strip()
        ln = str(row.get("LastName") or row.get("lastname") or "").strip()
        raw_dob = row.get("BirthDate") or row.get("birthdate") or row.get("DOB")
        dob = parse_date(raw_dob)

        if not fn or not ln:
            return None, f"Row {idx}: Missing patient first or last name"
        if not dob:
            return None, f"Row {idx}: Missing or invalid BirthDate ({raw_dob})"

        gender = parse_gender(row.get("Gender") or row.get("gender"))
        phone = clean_phone(row.get("CellPhone") or row.get("HomePhone") or row.get("phone"))
        email = clean_email(row.get("EmailAddress") or row.get("Email") or row.get("email"))

        record = NormalizedPatientRecord(
            row_num=idx,
            first_name=fn,
            last_name=ln,
            date_of_birth=dob,
            gender=gender,
            email=email,
            phone=phone,
            address_street=str(row.get("Address1") or row.get("address") or "").strip() or None,
            address_city=str(row.get("City") or row.get("city") or "").strip() or None,
            address_state=str(row.get("State") or row.get("state") or "").strip() or None,
            address_zip=str(row.get("PostalCode") or row.get("zip") or "").strip() or None,
            external_id=str(row.get("ChartNumber") or row.get("chartnumber") or "").strip() or None,
        )

        proc_code = normalize_cdt_code(row.get("ProcCode") or row.get("Code"))
        if proc_code:
            amount = Decimal(str(row.get("Amount") or row.get("Fee") or "0.00"))
            proc_date = parse_date(row.get("ProcDate") or row.get("Date")) or dob
            record.procedures.append(
                NormalizedProcedure(
                    procedure_code=proc_code,
                    description=str(row.get("Description") or "Dentrix Clinical Procedure"),
                    fee=amount,
                    procedure_date=proc_date,
                    tooth_number=str(row.get("Tooth") or "").strip() or None,
                    surface=str(row.get("Surface") or "").strip() or None,
                )
            )

        return record, None


class EaglesoftAdapter:
    """Adapter for Patterson Eaglesoft exports (PatientID, ServiceCode, etc.)."""

    @staticmethod
    def identify(headers: List[str]) -> bool:
        lower_headers = [h.lower() for h in headers]
        return "patientid" in lower_headers or ("servicecode" in lower_headers and "sex" in lower_headers)

    @classmethod
    def transform_row(cls, row: Dict[str, Any], idx: int) -> Tuple[Optional[NormalizedPatientRecord], Optional[str]]:
        fn = str(row.get("FirstName") or row.get("first_name") or "").strip()
        ln = str(row.get("LastName") or row.get("last_name") or "").strip()
        raw_dob = row.get("Birthdate") or row.get("birthdate") or row.get("DOB")
        dob = parse_date(raw_dob)

        if not fn or not ln:
            return None, f"Row {idx}: Missing patient first or last name"
        if not dob:
            return None, f"Row {idx}: Missing or invalid Birthdate ({raw_dob})"

        gender = parse_gender(row.get("Sex") or row.get("sex") or row.get("Gender"))
        phone = clean_phone(row.get("CellPhone") or row.get("HomePhone") or row.get("Phone"))
        email = clean_email(row.get("Email") or row.get("email"))

        record = NormalizedPatientRecord(
            row_num=idx,
            first_name=fn,
            last_name=ln,
            date_of_birth=dob,
            gender=gender,
            email=email,
            phone=phone,
            address_street=str(row.get("Street") or row.get("address") or "").strip() or None,
            address_city=str(row.get("City") or row.get("city") or "").strip() or None,
            address_state=str(row.get("State") or row.get("state") or "").strip() or None,
            address_zip=str(row.get("Zip") or row.get("zip") or "").strip() or None,
            external_id=str(row.get("PatientID") or row.get("patientid") or "").strip() or None,
        )

        service_code = normalize_cdt_code(row.get("ServiceCode") or row.get("service_code"))
        if service_code:
            fee = Decimal(str(row.get("Fee") or row.get("fee") or "0.00"))
            service_date = parse_date(row.get("ServiceDate") or row.get("service_date")) or dob
            record.procedures.append(
                NormalizedProcedure(
                    procedure_code=service_code,
                    description=str(row.get("Description") or "Eaglesoft Service"),
                    fee=fee,
                    procedure_date=service_date,
                    tooth_number=str(row.get("ToothID") or "").strip() or None,
                    surface=str(row.get("Surface") or "").strip() or None,
                )
            )

        return record, None


class GenericAdapter:
    """Generic fallback for standard CSV columns."""

    @classmethod
    def transform_row(cls, row: Dict[str, Any], idx: int) -> Tuple[Optional[NormalizedPatientRecord], Optional[str]]:
        fn = str(row.get("first_name") or row.get("firstName") or row.get("first") or "").strip()
        ln = str(row.get("last_name") or row.get("lastName") or row.get("last") or "").strip()
        raw_dob = row.get("date_of_birth") or row.get("dob") or row.get("birth_date")
        dob = parse_date(raw_dob)

        if not fn or not ln:
            return None, f"Row {idx}: First and last name are required"
        if not dob:
            return None, f"Row {idx}: Missing or invalid date_of_birth"

        gender = parse_gender(row.get("gender") or row.get("sex"))
        phone = clean_phone(row.get("phone") or row.get("mobile"))
        email = clean_email(row.get("email"))

        return NormalizedPatientRecord(
            row_num=idx,
            first_name=fn,
            last_name=ln,
            date_of_birth=dob,
            gender=gender,
            email=email,
            phone=phone,
            address_street=str(row.get("address_street") or row.get("address") or "").strip() or None,
            address_city=str(row.get("address_city") or row.get("city") or "").strip() or None,
            address_state=str(row.get("address_state") or row.get("state") or "").strip() or None,
            address_zip=str(row.get("address_zip") or row.get("zip") or "").strip() or None,
            external_id=str(row.get("external_id") or row.get("id") or "").strip() or None,
        ), None


class MigrationImportersService:
    """Orchestrates ETL analysis and transactional execution for EHR migrations."""

    @classmethod
    def detect_ehr_system(cls, headers: List[str], requested_system: Optional[str] = None) -> str:
        """Identify which EHR schema is represented by the headers."""
        if requested_system:
            req = requested_system.lower()
            if "open" in req or "dental" in req:
                return "opendental"
            if "dentrix" in req:
                return "dentrix"
            if "eagle" in req:
                return "eaglesoft"
            return "generic"

        if OpenDentalAdapter.identify(headers):
            return "opendental"
        if EaglesoftAdapter.identify(headers):
            return "eaglesoft"
        if DentrixAdapter.identify(headers):
            return "dentrix"
        return "generic"

    @classmethod
    def parse_rows_from_text(cls, csv_text: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Parse raw CSV text into header list and list of row dicts."""
        reader = csv.reader(io.StringIO(csv_text.strip()))
        rows_raw = list(reader)
        if not rows_raw:
            return [], []

        headers = [h.strip() for h in rows_raw[0]]
        dict_rows = []
        for line in rows_raw[1:]:
            if not line or all(not cell.strip() for cell in line):
                continue
            row_dict = {}
            for i, h in enumerate(headers):
                row_dict[h] = line[i].strip() if i < len(line) else ""
            dict_rows.append(row_dict)

        return headers, dict_rows

    @classmethod
    async def analyze_migration(
        cls,
        db: AsyncSession,
        rows: List[Dict[str, Any]],
        practice_id: UUID,
        source_system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stage 1: Pre-flight dry run validation.
        Detects EHR format, validates rows, checks duplicates against practice index,
        and computes financial balances.
        """
        if not rows:
            return {
                "detected_ehr": "generic",
                "total_rows": 0,
                "valid_count": 0,
                "duplicate_count": 0,
                "error_count": 0,
                "total_fees": 0.0,
                "errors": ["Uploaded dataset contains no data rows."],
                "duplicates": [],
                "preview": [],
            }

        headers = list(rows[0].keys())
        detected_ehr = cls.detect_ehr_system(headers, requested_system=source_system)

        if detected_ehr == "opendental":
            adapter = OpenDentalAdapter
        elif detected_ehr == "dentrix":
            adapter = DentrixAdapter
        elif detected_ehr == "eaglesoft":
            adapter = EaglesoftAdapter
        else:
            adapter = GenericAdapter

        valid_records: List[NormalizedPatientRecord] = []
        errors: List[str] = []
        duplicates: List[str] = []
        total_fees = Decimal("0.00")

        for idx, r in enumerate(rows, start=1):
            record, err = adapter.transform_row(r, idx)
            if err or not record:
                errors.append(err or f"Row {idx}: Invalid patient format")
                continue

            # Check existing duplicate in practice
            dup_filters = []
            if record.email:
                em_h = hmac_index(record.email)
                if em_h:
                    dup_filters.append(Patient.search_index_email == em_h)
            if record.phone:
                ph_h = hmac_index(record.phone)
                if ph_h:
                    dup_filters.append(Patient.search_index_phone == ph_h)

            is_dup = False
            if dup_filters:
                dup_stmt = select(Patient.id).where(
                    Patient.practice_id == practice_id,
                    Patient.status != PatientStatus.INACTIVE,
                    or_(*dup_filters),
                ).limit(1)
                dup_res = await db.execute(dup_stmt)
                if dup_res.scalar_one_or_none():
                    is_dup = True
                    duplicates.append(f"Row {idx}: {record.first_name} {record.last_name} matches existing email/phone.")

            if not is_dup:
                valid_records.append(record)
                for proc in record.procedures:
                    total_fees += proc.fee

        preview = []
        for rec in valid_records[:10]:
            preview.append({
                "first_name": rec.first_name,
                "last_name": rec.last_name,
                "date_of_birth": rec.date_of_birth.isoformat(),
                "gender": rec.gender.value,
                "email": rec.email,
                "phone": rec.phone,
                "external_id": rec.external_id,
                "procedure_count": len(rec.procedures),
            })

        return {
            "detected_ehr": detected_ehr,
            "total_rows": len(rows),
            "valid_count": len(valid_records),
            "duplicate_count": len(duplicates),
            "error_count": len(errors),
            "total_fees": float(total_fees),
            "errors": errors[:50],
            "duplicates": duplicates[:50],
            "preview": preview,
        }

    @classmethod
    async def execute_migration(
        cls,
        db: AsyncSession,
        rows: List[Dict[str, Any]],
        practice_id: UUID,
        current_user: User,
        source_system: Optional[str] = None,
        request: Any = None,
    ) -> Dict[str, Any]:
        """
        Stage 2: Transactional commit.
        Transforms and persists patients, appointments, and procedures into the practice database.
        """
        if not rows:
            return {"success": False, "imported_count": 0, "message": "No rows provided"}

        headers = list(rows[0].keys())
        detected_ehr = cls.detect_ehr_system(headers, requested_system=source_system)

        if detected_ehr == "opendental":
            adapter = OpenDentalAdapter
        elif detected_ehr == "dentrix":
            adapter = DentrixAdapter
        elif detected_ehr == "eaglesoft":
            adapter = EaglesoftAdapter
        else:
            adapter = GenericAdapter

        imported_patients: List[Patient] = []
        imported_notes_count = 0

        for idx, r in enumerate(rows, start=1):
            record, err = adapter.transform_row(r, idx)
            if err or not record:
                continue

            patient = Patient(
                practice_id=practice_id,
                first_name=record.first_name,
                last_name=record.last_name,
                date_of_birth=record.date_of_birth,
                gender=record.gender,
                email=record.email,
                phone=record.phone,
                address_street=record.address_street,
                address_city=record.address_city,
                address_state=record.address_state,
                address_zip=record.address_zip,
                status=PatientStatus.ACTIVE,
            )
            update_patient_search_indexes(patient, "email", "phone", "last_name")
            db.add(patient)
            await db.flush()
            imported_patients.append(patient)

            # Ingest procedures as clinical historical records if present
            if record.procedures:
                proc_items = []
                for p in record.procedures:
                    proc_items.append(f"• {p.procedure_code} - {p.description} (${p.fee:.2f}) [Tooth {p.tooth_number or 'N/A'}]")

                note_body = f"Migrated from {detected_ehr.upper()} (External ID: {record.external_id or 'N/A'}):\n" + "\n".join(proc_items)
                note = ClinicalNote(
                    patient_id=patient.id,
                    provider_id=current_user.id,
                    note_type=NoteType.PROCEDURE,
                    content=note_body,
                    subjective="Legacy system procedure history",
                    plan="Historical record migrated into CoreDent.",
                )
                db.add(note)
                imported_notes_count += 1

        await db.commit()

        await log_audit_event(
            db,
            current_user,
            "data_migration_executed",
            "practice",
            practice_id,
            request,
            {
                "source_system": detected_ehr,
                "patient_count": len(imported_patients),
                "clinical_notes_count": imported_notes_count,
            },
        )

        return {
            "success": True,
            "source_system": detected_ehr,
            "imported_patients_count": len(imported_patients),
            "imported_clinical_records_count": imported_notes_count,
            "patient_ids": [str(p.id) for p in imported_patients[:50]],
            "message": f"Successfully migrated {len(imported_patients)} patient records from {detected_ehr.upper()}.",
        }
