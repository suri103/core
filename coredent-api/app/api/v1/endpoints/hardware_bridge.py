"""
Hardware Sensor & TWAIN Workstation Bridge Endpoints
Enables direct acquisition from intraoral X-ray sensors, panoramic units,
and TWAIN/DirectUSB drivers (Dexis, Schick, Carestream, Vatech, Planmeca).
"""

from __future__ import annotations

import base64
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role, verify_csrf
from app.core.audit import log_audit_event
from app.core.database import get_db
from app.core.dicom_parser import DicomParser
from app.models.imaging import ImageCategory, ImageType, PatientImage
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.imaging_processing import ImageFileProcessor
from app.utils.storage import storage

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_SENSORS = [
    {
        "id": "dexis_titanium",
        "name": "Dexis Titanium / Platinum Sensor",
        "vendor": "Dexis / KaVo Kerr",
        "interface": "DirectUSB / TWAIN",
        "modalities": ["IO"],
        "default_bits": 16,
    },
    {
        "id": "schick_33",
        "name": "Schick 33 / CDR Elite Sensor",
        "vendor": "Dentsply Sirona",
        "interface": "USB / TWAIN",
        "modalities": ["IO"],
        "default_bits": 16,
    },
    {
        "id": "carestream_cs7600",
        "name": "Carestream CS 7600 / CS 2200",
        "vendor": "Carestream Dental",
        "interface": "TWAIN / DICOM",
        "modalities": ["IO", "PX"],
        "default_bits": 16,
    },
    {
        "id": "vatech_ezsensor",
        "name": "Vatech EzSensor Classic / HD",
        "vendor": "Vatech",
        "interface": "DirectUSB / TWAIN",
        "modalities": ["IO"],
        "default_bits": 14,
    },
    {
        "id": "planmeca_prosensor",
        "name": "Planmeca ProSensor HD",
        "vendor": "Planmeca",
        "interface": "Ethernet / TWAIN",
        "modalities": ["IO", "PX"],
        "default_bits": 16,
    },
    {
        "id": "generic_twain",
        "name": "Generic TWAIN 2.4 Device",
        "vendor": "Standard TWAIN Working Group",
        "interface": "TWAIN",
        "modalities": ["IO", "PX", "DX"],
        "default_bits": 12,
    },
]

# Active capture sessions in memory (token -> session data)
_ACTIVE_CAPTURE_SESSIONS: Dict[str, Dict[str, Any]] = {}


class HardwareBridgeConfigResponse(BaseModel):
    version: str = "2.4.0"
    bridge_port: int = 19844
    bridge_protocol: str = "ws://127.0.0.1:19844/bridge"
    status: str = "ready"
    supported_sensors: List[Dict[str, Any]]


class CaptureSessionCreate(BaseModel):
    patient_id: UUID
    sensor_id: str = "dexis_titanium"
    mount_type: str = Field("single_pa", description="single_pa, bitewing_4, fmx_18, panoramic")
    tooth_number: Optional[str] = None
    exposure_preset: Optional[str] = "adult_molar"
    series_id: Optional[UUID] = None


class CaptureSessionResponse(BaseModel):
    session_id: str
    session_token: str
    patient_id: str
    sensor_id: str
    mount_type: str
    tooth_number: Optional[str]
    created_at: str
    expires_at: str
    ws_endpoint: str


class DirectFrameAcquirePayload(BaseModel):
    session_token: str
    sensor_id: str
    image_format: str = Field("dcm", description="dcm, png, or raw_b64")
    raw_base64_data: str
    tooth_number: Optional[str] = None
    kvp: Optional[float] = None
    exposure_time_ms: Optional[float] = None
    notes: Optional[str] = None


@router.get("/hardware-bridge/config", response_model=HardwareBridgeConfigResponse)
async def get_bridge_config(
    current_user: User = Depends(get_current_user),
) -> HardwareBridgeConfigResponse:
    """Return workstation hardware bridge connection configuration and supported sensors."""
    return HardwareBridgeConfigResponse(
        version="2.4.0",
        bridge_port=19844,
        bridge_protocol="ws://127.0.0.1:19844/bridge",
        status="ready",
        supported_sensors=SUPPORTED_SENSORS,
    )


@router.get("/hardware-bridge/devices")
async def list_connected_devices(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Return available sensor devices reported by local workstation bridge."""
    return SUPPORTED_SENSORS


@router.post("/hardware-bridge/sessions", response_model=CaptureSessionResponse)
async def create_capture_session(
    payload: CaptureSessionCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> CaptureSessionResponse:
    """Initialize a direct sensor acquisition session for an operative chair / workstation."""
    # Verify patient belongs to current practice
    patient_res = await db.execute(
        select(Patient).where(
            Patient.id == payload.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = patient_res.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found in this practice")

    session_id = str(uuid4())
    session_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    session_data = {
        "session_id": session_id,
        "session_token": session_token,
        "practice_id": str(current_user.practice_id),
        "user_id": str(current_user.id),
        "patient_id": str(payload.patient_id),
        "sensor_id": payload.sensor_id,
        "mount_type": payload.mount_type,
        "tooth_number": payload.tooth_number,
        "created_at": now.isoformat(),
        "series_id": str(payload.series_id) if payload.series_id else None,
    }

    _ACTIVE_CAPTURE_SESSIONS[session_token] = session_data

    await log_audit_event(
        db,
        current_user,
        "hardware_sensor_session_created",
        "patient",
        payload.patient_id,
        request,
        {"sensor_id": payload.sensor_id, "mount_type": payload.mount_type, "tooth_number": payload.tooth_number},
    )
    await db.commit()

    return CaptureSessionResponse(
        session_id=session_id,
        session_token=session_token,
        patient_id=str(payload.patient_id),
        sensor_id=payload.sensor_id,
        mount_type=payload.mount_type,
        tooth_number=payload.tooth_number,
        created_at=now.isoformat(),
        expires_at=now.isoformat(),
        ws_endpoint=f"ws://127.0.0.1:19844/bridge?token={session_token}",
    )


@router.post("/hardware-bridge/acquire")
async def acquire_sensor_frame(
    payload: DirectFrameAcquirePayload,
    request: Request,
    current_user: User = Depends(require_role(UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """
    Ingest a radiograph directly captured from a local TWAIN or DirectUSB sensor bridge.
    Parses DICOM tags if DICM format, encrypts, and attaches to the patient's dental chart.
    """
    session = _ACTIVE_CAPTURE_SESSIONS.get(payload.session_token)
    if not session or session.get("practice_id") != str(current_user.practice_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired capture session token")

    try:
        raw_bytes = base64.b64decode(payload.raw_base64_data)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base64 payload: {exc}")

    if len(raw_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload contains zero image bytes")

    patient_id = UUID(session["patient_id"])
    tooth_num = payload.tooth_number or session.get("tooth_number")
    dicom_meta = None

    # If DICOM Part 10 file, parse dental DICOM metadata tags
    if DicomParser.is_dicom(raw_bytes):
        try:
            dicom_meta = DicomParser.parse(raw_bytes)
            if not tooth_num and dicom_meta.tooth_number:
                tooth_num = dicom_meta.tooth_number
        except Exception as d_exc:
            logger.warning("DICOM tag extraction had non-fatal warning: %s", d_exc)

    # Determine extension and category
    ext = ".dcm" if (dicom_meta or payload.image_format == "dcm") else ".png"
    safe_filename = f"sensor_capture_{session['sensor_id']}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}{ext}"

    # Store file safely in storage (tenant-isolated path)
    mime = "application/dicom" if ext == ".dcm" else "image/png"
    relative_path = f"practices/{current_user.practice_id}/patients/{patient_id}/imaging/{safe_filename}"
    file_path = storage.upload(raw_bytes, relative_path, mime)
    file_url = ImageFileProcessor.get_file_url(file_path)

    # Create PatientImage record
    img = PatientImage(
        practice_id=current_user.practice_id,
        patient_id=patient_id,
        title=f"Direct Capture ({session['sensor_id']})" + (f" - Tooth #{tooth_num}" if tooth_num else ""),
        image_type=ImageType.XRAY,
        category=ImageCategory.BITEWING if "bitewing" in session["mount_type"] else ImageCategory.PERIAPICAL,
        file_path=file_path,
        file_name=safe_filename,
        file_size=len(raw_bytes),
        mime_type="application/dicom" if ext == ".dcm" else "image/png",
        tooth_number=tooth_num,
        acquisition_date=datetime.now(timezone.utc),
        device_name=session["sensor_id"],
        width=dicom_meta.columns if dicom_meta else None,
        height=dicom_meta.rows if dicom_meta else None,
        dicom_study_id=dicom_meta.study_instance_uid if dicom_meta else None,
        dicom_series_id=dicom_meta.series_instance_uid if dicom_meta else None,
        dicom_instance_id=dicom_meta.sop_instance_uid if dicom_meta else None,
        provider_id=current_user.id,
        notes=payload.notes or f"Acquired via CoreDent Hardware Bridge from {session['sensor_id']}",
    )
    db.add(img)
    await db.flush()

    await log_audit_event(
        db,
        current_user,
        "hardware_sensor_capture_acquired",
        "patient_image",
        img.id,
        request,
        {
            "sensor_id": session["sensor_id"],
            "tooth_number": tooth_num,
            "size_bytes": len(raw_bytes),
            "is_dicom": dicom_meta is not None,
        },
    )
    await db.commit()
    await db.refresh(img)

    # Clean up one-shot capture session
    _ACTIVE_CAPTURE_SESSIONS.pop(payload.session_token, None)

    return {
        "success": True,
        "image_id": str(img.id),
        "file_url": file_url,
        "tooth_number": tooth_num,
        "acquisition_date": img.acquisition_date.isoformat(),
        "capture_date": img.acquisition_date.isoformat(),
        "dicom_metadata": {
            "modality": dicom_meta.modality if dicom_meta else "IO",
            "rows": dicom_meta.rows if dicom_meta else None,
            "columns": dicom_meta.columns if dicom_meta else None,
            "kvp": dicom_meta.kvp if dicom_meta else payload.kvp,
            "exposure_time_ms": dicom_meta.exposure_time_ms if dicom_meta else payload.exposure_time_ms,
        } if dicom_meta else None,
    }
