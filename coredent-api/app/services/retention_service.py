"""
Retention service: eligibility + hard purge for anonymized patients.

Implements the "hard purge (scheduled)" step of docs/DATA_RETENTION_POLICY.md:
once every billing disposition for a fully-anonymized patient is older than the
configured retention window (R2 default 7 years), the orphaned rows are deleted
and the anonymized placeholder row is removed. Each purge writes a write-once
audit row so destruction has a paper trail.

Markers:
  - An anonymized patient = first_name "[deleted]" AND last_name "[deleted]"
    AND status INACTIVE (exactly what POST /patients/{id}/anonymize writes).
  - "Last billing disposition" = latest of invoice.created_at, payment.created_at,
    payment-plan updated_at, insurance-claim created_at; patient.updated_at as
    fallback when there is no billing history at all.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy import CursorResult, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.billing import Invoice, Payment, PaymentPlan
from app.models.insurance import InsuranceClaim
from app.models.patient import Patient, PatientPortalAccessCode, PatientPortalSession, PatientStatus
from app.models.payment import PaymentCard, PaymentTransaction, RecurringBilling
from app.models.subscription import Subscription
from app.models.imaging import ImageSeries
from app.models.marketing import MarketingEmail

logger = logging.getLogger(__name__)

ANONYMIZED_FIRST_NAME = "[deleted]"
ANONYMIZED_LAST_NAME = "[deleted]"

# Tables with a patient_id FK that have NO cascade collection on Patient, so
# db.delete(patient) would try to NULL them (violating NOT NULL) instead of
# deleting them. They are deleted explicitly before the cascade delete runs.
_EXPLICIT_DELETE_MODELS = (
    PaymentCard,
    RecurringBilling,
    PaymentTransaction,
    PaymentPlan,
    Subscription,
    PatientPortalSession,
    PatientPortalAccessCode,
    ImageSeries,
    MarketingEmail,
)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """Best-effort tz-normalization (SQLite returns naive datetimes)."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _years_delta(years: int) -> timedelta:
    """Calendar-year delta without third-party deps (leap-day safe)."""
    return timedelta(days=365 * years + years // 4)


class RetentionService:
    """Eligibility + hard purge for fully-anonymized patients."""

    # ----------------------------------------------------------------------
    # Eligibility
    # ----------------------------------------------------------------------

    @staticmethod
    async def billing_anchor_async(
        db: AsyncSession, patient: Patient
    ) -> Optional[datetime]:
        """Latest billing disposition instant for a patient (UTC-aware)."""
        candidates: List[Optional[datetime]] = []
        for model, column in (
            (Invoice, Invoice.created_at),
            (Payment, Payment.created_at),
            (PaymentPlan, PaymentPlan.updated_at),
            (InsuranceClaim, InsuranceClaim.created_at),
        ):
            row = await db.execute(
                select(func.max(column)).where(model.patient_id == patient.id)
            )
            value = row.scalar_one_or_none()
            if value is not None:
                candidates.append(_as_aware(value))
        aware = [c for c in candidates if c is not None]
        if aware:
            return max(aware)
        return _as_aware(patient.updated_at)

    @staticmethod
    def is_eligible_for_purge(
        anchor: Optional[datetime],
        *,
        now: datetime,
        retention_years: int,
        purge_eligible_at: Optional[datetime] = None,
    ) -> bool:
        """True when the last billing disposition is past the retention window.

        AND semantics with the minor-record ceiling: when ``purge_eligible_at``
        is set (a minor record's snapshot from anonymize time), it must also
        have elapsed — a record of a patient who was a minor must never be
        purged before ``DOB + majority_age + minor_retention_years`` even if
        the adult billing window has already passed.

        Date granularity mirrors the backend snapshot (midnight UTC), so naive
        DB datetimes normalize to midnight UTC too.
        """
        if anchor is None:
            return False
        cutoff = anchor + _years_delta(retention_years)
        # Normalize day precision: the snapshot floors to the day (NaiveDates
        # legitimately surface midnight), so a same-day ceiling is NOT
        # elapsed until the next UTC day per GDPR "past the window" practice.
        adult_ok = now >= cutoff
        if not adult_ok:
            return False
        if purge_eligible_at is not None:
            return now >= _as_aware(purge_eligible_at) + timedelta(days=1)
        return True

    @staticmethod
    async def find_anonymized_candidates(
        db: AsyncSession, *, limit: int = 50
    ) -> List[Patient]:
        """Fetch fully-anonymized patients (marker rows) for purge evaluation.

        NOTE: first_name/last_name are Fernet-encrypted TypeDecorators, so DB
        equality matching is impossible (each envelope has a random IV). Fetch
        the full candidate set and match the markers in Python after decrypt
        (TypeDecorator decrypts transparently on attribute access).
        """
        rows = await db.execute(
            select(Patient)
            .where(Patient.status == PatientStatus.INACTIVE)
            .order_by(Patient.updated_at.asc().nullslast())
            .limit(limit * 10)
        )
        matched: List[Patient] = []
        for candidate in rows.scalars().all():
            if (
                candidate.first_name == ANONYMIZED_FIRST_NAME
                and candidate.last_name == ANONYMIZED_LAST_NAME
            ):
                matched.append(candidate)
            if len(matched) >= limit:
                break
        return matched

    @staticmethod
    async def eligible_anonymized_patients(
        db: AsyncSession,
        *,
        now: Optional[datetime] = None,
        retention_years: int = 7,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Anonymized patients whose billing history is past the window.

        Per-practice override: a practice's ``retention_years`` (when set) is
        combined with the platform default via ``max()`` — a practice can only
        EXTEND retention beyond the platform floor, never shorten it below.
        """
        moment = now or datetime.now(timezone.utc)
        out: List[Dict[str, Any]] = []
        for patient in await RetentionService.find_anonymized_candidates(db, limit=limit):
            anchor = await RetentionService.billing_anchor_async(db, patient)
            effective_years = await RetentionService.effective_retention_years(
                db, patient.practice_id, platform_default=retention_years
            )
            # Minor-record ceiling snapshot from anonymize time (AND condition).
            minor_ceiling = _as_aware(getattr(patient, "purge_eligible_at", None))
            if RetentionService.is_eligible_for_purge(
                anchor,
                now=moment,
                retention_years=effective_years,
                purge_eligible_at=minor_ceiling,
            ):
                out.append(
                    {
                        "patient_id": patient.id,
                        "practice_id": patient.practice_id,
                        "anchor": anchor,
                        "retention_years": effective_years,
                        "purge_eligible_at": minor_ceiling,
                    }
                )
        return out

    @staticmethod
    async def effective_retention_years(
        db: AsyncSession, practice_id: Any, *, platform_default: int = 7
    ) -> int:
        """max(practice.retention_years, platform_default); NULL practice = default.

        The floor is the platform default so a misconfigured practice can never
        shorten retention below the statutory safe harbor.
        """
        from app.models.practice import Practice

        row = await db.execute(
            select(Practice.retention_years).where(Practice.id == practice_id)
        )
        value = row.scalar_one_or_none()
        if value is None:
            return platform_default
        return max(int(value), int(platform_default))


    # ----------------------------------------------------------------------
    # Hard purge (async + sync variants share the same ordering)
    # ----------------------------------------------------------------------

    @staticmethod
    async def purge_patient_hard_async(
        db: AsyncSession, patient: Patient
    ) -> Dict[str, Any]:
        """Delete an anonymized patient's orphaned rows + placeholder, async flavor."""
        counts: Dict[str, int] = {}
        # 1) Explicit deletes for patient_id tables with no Patient cascade.
        for model in _EXPLICIT_DELETE_MODELS:
            rows = await db.execute(
                model.__table__.delete().where(
                    model.__table__.c.patient_id == patient.id
                )
            )
            # DML returns a CursorResult, which is where rowcount lives;
            # db.execute() is annotated as Result and has no such attribute.
            counts[model.__tablename__] = cast(CursorResult, rows).rowcount or 0
        if getattr(patient, "email", None):
            from app.models.portal_lockout import PortalIdentityLockout
            lockout_del = await db.execute(
                PortalIdentityLockout.__table__.delete().where(
                    PortalIdentityLockout.email == str(patient.email).lower()
                )
            )
            lockout_rowcount = cast(CursorResult, lockout_del).rowcount
            if lockout_rowcount:
                counts["portal_identity_lockouts"] = lockout_rowcount
        # 2) ORM cascade handles invoices/payments/notes/appointments/etc.
        await db.delete(patient)
        await db.flush()
        counts["patients"] = 1
        return {
            "patient_id": str(patient.id),
            "practice_id": str(patient.practice_id),
            "deleted": counts,
        }

    @staticmethod
    def purge_patient_hard(db: Session, patient) -> Dict[str, Any]:
        """Delete an anonymized patient's orphaned rows + placeholder (sync)."""
        counts: Dict[str, int] = {}
        for model in _EXPLICIT_DELETE_MODELS:
            rows = (
                db.query(model)
                .filter(model.patient_id == patient.id)
                .delete(synchronize_session=False)
            )
            counts[model.__tablename__] = rows or 0
        if getattr(patient, "email", None):
            from app.models.portal_lockout import PortalIdentityLockout
            lockout_rows = (
                db.query(PortalIdentityLockout)
                .filter(PortalIdentityLockout.email == str(patient.email).lower())
                .delete(synchronize_session=False)
            )
            if lockout_rows:
                counts["portal_identity_lockouts"] = lockout_rows
        db.delete(patient)
        db.flush()
        counts["patients"] = 1
        return {
            "patient_id": str(patient.id),
            "practice_id": str(patient.practice_id),
            "deleted": counts,
        }
