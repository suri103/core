"""
Clinical Endpoints
Operations for Perio Charting and clinical records
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
import uuid

from app.core.database import get_db
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role, verify_csrf
from app.models.clinical import PerioChart, PerioChartEntry
from app.models.patient import Patient
from app.schemas.clinical import (
    PerioChartCreate,
    PerioChartResponse,
    PerioChartListResponse,
)
from app.core.audit import log_audit_event

router = APIRouter()

@router.get("/perio/", response_model=PerioChartListResponse)
async def list_perio_charts(
    patient_id: Optional[uuid.UUID] = Query(None, description="Filter by patient ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> PerioChartListResponse:
    """
    List periodontal charts for the practice or a specific patient
    """
    # M1 FIX: tenant filter in SQL via a patient join (was: full-table scan
    # + per-row patient lookup in Python).
    query = (
        select(PerioChart)
        .join(Patient, PerioChart.patient_id == Patient.id)
        .where(Patient.practice_id == current_user.practice_id)
        .options(selectinload(PerioChart.entries))
    )
    if patient_id:
        query = query.where(PerioChart.patient_id == patient_id)

    result = await db.execute(query)
    charts = result.scalars().all()

    # HIPAA: Log full perio chart list fetching
    await log_audit_event(
        db, current_user, "list_perio_charts", "perio_chart", None, request
    )
    await db.commit()

    return PerioChartListResponse(
        perio_charts=charts,
        count=len(charts)
    )


@router.post("/perio/", response_model=PerioChartResponse)
async def create_perio_chart(
    request: Request,
    chart_data: PerioChartCreate,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PerioChartResponse:
    """
    Create a new periodontal chart with entries
    """
    # Verify patient
    result = await db.execute(
        select(Patient).where(Patient.id == chart_data.patient_id, Patient.practice_id == current_user.practice_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or access denied",
        )

    chart = PerioChart(
        patient_id=chart_data.patient_id,
        provider_id=current_user.id,
        overall_bleeding_index=chart_data.overall_bleeding_index,
        plaque_index=chart_data.plaque_index,
        calculus_index=chart_data.calculus_index,
        diagnosis=chart_data.diagnosis,
        notes=chart_data.notes,
    )
    db.add(chart)
    await db.flush()  # To get chart.id

    for entry_data in chart_data.entries:
        entry = PerioChartEntry(
            perio_chart_id=chart.id,
            **entry_data.model_dump()
        )
        db.add(entry)

    await db.flush()
    await log_audit_event(
        db,
        current_user,
        "perio_chart_created",
        "perio_chart",
        chart.id,
        request,
        changes={"entry_count": len(chart_data.entries)},
    )
    await db.commit()
    result = await db.execute(
        select(PerioChart)
        .where(PerioChart.id == chart.id)
        .options(selectinload(PerioChart.entries))
    )
    return result.scalar_one()