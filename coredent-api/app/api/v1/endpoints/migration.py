"""
Legacy EHR Migration Endpoints
Supports Open Dental, Dentrix G4-G7, and Patterson Eaglesoft migration pipelines.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role, verify_csrf
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.migration_importers import MigrationImportersService

router = APIRouter()


class MigrationAnalyzePayload(BaseModel):
    rows: Optional[List[Dict[str, Any]]] = None
    source_system: Optional[str] = None  # "opendental", "dentrix", "eaglesoft", "generic"


class MigrationExecutePayload(BaseModel):
    rows: List[Dict[str, Any]] = Field(..., min_items=1)
    source_system: Optional[str] = None


@router.post("/analyze")
async def analyze_migration(
    request: Request,
    payload: MigrationAnalyzePayload,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Stage 1: Pre-flight validation and dry run report.
    Detects schema (Open Dental, Dentrix, Eaglesoft), maps CDT codes,
    identifies existing duplicate patients, and validates fields.
    """
    rows = payload.rows or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must include non-empty 'rows' list.",
        )

    return await MigrationImportersService.analyze_migration(
        db=db,
        rows=rows,
        practice_id=current_user.practice_id,
        source_system=payload.source_system,
    )


@router.post("/analyze-file")
async def analyze_migration_file(
    request: Request,
    file: UploadFile = File(...),
    source_system: Optional[str] = Form(None),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Stage 1 file upload: Parses uploaded CSV file from legacy EHR and runs dry run analysis.
    """
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode file as UTF-8 or Latin-1 text.",
            )

    headers, rows = MigrationImportersService.parse_rows_from_text(csv_text)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file contains no valid CSV data rows.",
        )

    report = await MigrationImportersService.analyze_migration(
        db=db,
        rows=rows,
        practice_id=current_user.practice_id,
        source_system=source_system,
    )
    report["parsed_rows"] = rows  # Pass parsed rows back for subsequent execution
    return report


@router.post("/execute")
async def execute_migration(
    request: Request,
    payload: MigrationExecutePayload,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """
    Stage 2: Commit verified legacy migration records into CoreDent.
    Imports patient records, builds search index HMACs, and records clinical history.
    """
    return await MigrationImportersService.execute_migration(
        db=db,
        rows=payload.rows,
        practice_id=current_user.practice_id,
        current_user=current_user,
        source_system=payload.source_system,
        request=request,
    )
