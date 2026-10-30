"""
Imaging Endpoints (Refactored)
CRUD operations for patient images and X-rays
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
import html as html_module
import logging

from app.core.database import get_db
from app.api.deps import get_current_user, verify_csrf, require_role
from app.core.audit import log_audit_event
from app.core.limiter import limiter
from app.models.user import User, UserRole
from app.models.imaging import ImageType, ImageCategory
from app.models.patient import Patient
from app.schemas.imaging import (
    PatientImageUpdate,
    PatientImageResponse,
    PatientImageListResponse,
    ImageAnnotationCreate,
    ImageAnnotationResponse,
    ImageSeriesCreate,
    ImageSeriesUpdate,
    ImageSeriesResponse,
    ImageSeriesListResponse,
    ImageTemplateCreate,
    ImageTemplateUpdate,
    ImageTemplateResponse,
    ImageTemplateListResponse,
    ImageShareRequest,
    ImageShareResponse,
)
from app.services.imaging_service import ImagingService
from app.services.tenant_refs import require_provider
from app.services.imaging_processing import (
    ImageFileProcessor,
    ImageSharingProcessor,
)
from app.core.email import email_service
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

router = APIRouter()

# M-12: roles that may be recorded as the acquiring/interpreting provider.
IMAGING_PROVIDER_ROLES = (UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)


# ============================================
# Patient Image Endpoints
# ============================================

@router.get("/patients/{patient_id}/images", response_model=PatientImageListResponse)
async def list_patient_images(
    patient_id: str,
    image_type: Optional[ImageType] = Query(None, description="Filter by image type"),
    category: Optional[ImageCategory] = Query(None, description="Filter by category"),
    tooth_number: Optional[str] = Query(None, description="Filter by tooth number"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> PatientImageListResponse:
    """
    List patient images
    """
    try:
        # Verify patient belongs to practice
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # Get images using service
        images = await ImagingService.get_patient_images(
            db, patient_id, current_user.practice_id,
            image_type, category, tooth_number, start_date, end_date
        )

        # Generate URLs for each image
        for image in images:
            image.url = ImageFileProcessor.get_file_url(image.file_path)

        # HIPAA: Log list images access
        await log_audit_event(
            db, current_user, "list_patient_images", "patient", patient_id, request
        )
        await db.commit()

        return PatientImageListResponse(
            images=images,
            count=len(images),
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing patient images: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving images",
        )


@router.post("/patients/{patient_id}/images", response_model=PatientImageResponse)
@limiter.limit("30/minute")
async def upload_image(
    patient_id: str,
    request: Request,
    file: UploadFile = File(...),
    image_type: ImageType = Query(...),
    category: Optional[ImageCategory] = Query(None),
    tooth_number: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    notes: Optional[str] = Query(None),
    device_name: Optional[str] = Query(None),
    device_serial: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PatientImageResponse:
    """
    Upload patient image
    SECURITY: File validation implemented
    """
    try:
        # Verify patient belongs to practice
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # Validate file
        content, file_extension = await ImageFileProcessor.validate_file(file)
        file_size = len(content)

        # Sanitize filename
        safe_filename = ImageFileProcessor.sanitize_filename(file.filename)

        # Generate unique filename partitioned by practice
        unique_filename = ImageFileProcessor.generate_unique_filename(
            patient_id, file_extension, practice_id=current_user.practice_id
        )

        # Upload file
        storage_path = await ImageFileProcessor.upload_file(
            content, unique_filename, file.content_type
        )

        # Create image record
        image = await ImagingService.create_image(
            db=db,
            practice_id=current_user.practice_id,
            patient_id=patient_id,
            provider_id=current_user.id,
            image_type=image_type,
            file_path=storage_path,
            file_name=safe_filename,
            file_size=file_size,
            mime_type=file.content_type,
            category=category,
            tooth_number=tooth_number,
            title=title,
            description=description,
            notes=notes,
            device_name=device_name,
            device_serial=device_serial,
        )

        # HIPAA: Log image upload
        await log_audit_event(
            db, current_user, "upload_image", "patient_image", image.id, request,
            {"file_size": file_size, "mime_type": file.content_type}
        )
        await db.commit()

        return image

    except ValueError as e:
        logger.warning(f"File validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "empty" in str(e).lower() else status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if "too large" in str(e).lower() else status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error uploading image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save image",
        )


@router.get("/images/{image_id}", response_model=PatientImageResponse)
async def get_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> PatientImageResponse:
    """
    Get image by ID
    """
    try:
        image = await ImagingService.get_image(db, image_id, current_user.practice_id)

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found",
            )

        # Generate URL
        image.url = ImageFileProcessor.get_file_url(image.file_path)

        # HIPAA: Log image access
        await log_audit_event(
            db, current_user, "view_image", "patient_image", image.id, request
        )
        await db.commit()

        return image

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error retrieving image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving image",
        )


@router.put("/images/{image_id}", response_model=PatientImageResponse)
async def update_image(
    image_id: str,
    image_data: PatientImageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PatientImageResponse:
    """
    Update image metadata
    """
    try:
        image = await ImagingService.get_image(db, image_id, current_user.practice_id)

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found",
            )

        # Update image
        update_data = image_data.dict(exclude_unset=True)
        image = await ImagingService.update_image(
            db, image_id, current_user.practice_id, **update_data
        )

        return image

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating image",
        )


@router.delete("/images/{image_id}")
async def delete_image(
    image_id: str,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Delete image (soft delete)
    """
    try:
        success = await ImagingService.delete_image(db, image_id, practice_id=current_user.practice_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found",
            )

        return {"message": "Image deleted successfully"}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error deleting image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting image",
        )


@router.post("/images/{image_id}/annotations", response_model=ImageAnnotationResponse)
async def add_annotations(
    image_id: str,
    annotation_data: ImageAnnotationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ImageAnnotationResponse:
    """
    Add or update image annotations
    """
    try:
        image = await ImagingService.get_image(db, image_id, current_user.practice_id)

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found",
            )

        # Add annotations
        annotations_list = [ann.dict() for ann in annotation_data.annotations]
        image = await ImagingService.add_annotations(
            db, image_id, annotations_list, current_user.practice_id
        )

        return ImageAnnotationResponse(
            image_id=image.id,
            annotations=annotation_data.annotations,
            updated_at=image.updated_at,
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error adding annotations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error adding annotations",
        )


@router.post("/images/{image_id}/share", response_model=ImageShareResponse)
async def share_image(
    image_id: str,
    share_data: ImageShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    _csrf: bool = Depends(verify_csrf),
) -> ImageShareResponse:
    """
    Share image with patient or referral
    """
    try:
        image = await ImagingService.get_image(db, image_id, current_user.practice_id)

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found",
            )

        # Update sharing settings
        share_link, expires_at = await ImageSharingProcessor.update_sharing_settings(
            db, image, share_data.share_with_patient, share_data.share_with_referral
        )

        # HIPAA: Log image sharing
        await log_audit_event(
            db, current_user, "share_image", "patient_image", image.id, request,
            {
                "share_with_patient": share_data.share_with_patient,
                "share_with_referral": share_data.share_with_referral,
                "referral_email": share_data.referral_email
            }
        )
        await db.commit()

        message = "Image sharing settings updated"

        if share_data.share_with_referral and share_data.referral_email:
            try:
                # L-9 FIX: scope display-name lookup to this practice — the
                # image itself is scoped, but an orphaned/mis-linked patient_id
                # must not disclose another tenant's name in the referral email.
                result = await db.execute(
                    select(Patient).where(
                        Patient.id == image.patient_id,
                        Patient.practice_id == current_user.practice_id,
                    )
                )
                patient = result.scalar_one_or_none()

                safe_first = html_module.escape(patient.first_name if patient else '')
                safe_last = html_module.escape(patient.last_name if patient else '')
                safe_image_type = html_module.escape(
                    image.image_type.value if hasattr(image.image_type, 'value') else str(image.image_type)
                )
                safe_date = html_module.escape(
                    image.acquisition_date.strftime('%Y-%m-%d') if image.acquisition_date else 'N/A'
                )
                # share_link is a generated token URL — escape it anyway for safety
                safe_link = html_module.escape(share_link) if share_link else None

                await email_service.send_email(
                    to=share_data.referral_email,
                    subject=f"Dental Image Referral - {safe_first} {safe_last}",
                    html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>New Dental Image Referral</h1>
                    <p>You have received a dental image for review.</p>
                    <p><strong>Patient:</strong> {safe_first} {safe_last}</p>
                    <p><strong>Image Type:</strong> {safe_image_type}</p>
                    <p><strong>Date:</strong> {safe_date}</p>
                    {f'<p><strong>View Here:</strong> <a href="{safe_link}">{safe_link}</a></p>' if safe_link else ''}
                    <p><em>This link expires in 30 days.</em></p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        CoreDent Dental Practice Management
                    </p>
                </body>
            </html>
            """,
                )
                message = "Image shared and notification sent to referral"
            except Exception as e:
                from app.core.email import log_email_failure
                log_email_failure(e, "imaging_referral_notification", share_data.referral_email)

        return ImageShareResponse(
            image_id=image.id,
            share_link=share_link,
            expires_at=expires_at,
            message=message,
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error sharing image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sharing image",
        )


# ============================================
# Public Image Endpoints (Token-Gated)
# ============================================

@router.get("/public/images/{image_id}", response_model=PatientImageResponse)
@limiter.limit("30/minute")
async def get_public_image(
    request: Request,
    image_id: str,
    token: Optional[str] = Query(None, description="Secure share token"),
    db: AsyncSession = Depends(get_db),
) -> PatientImageResponse:
    """
    Get image metadata for external referral (Token-Gated)
    """
    try:
        resolved_token = token or (request.headers.get("X-Share-Token") if request else None)
        if not resolved_token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Valid sharing link not found or expired",
            )
        image = await ImagingService.get_public_image(db, image_id, resolved_token)

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Valid sharing link not found or expired",
            )

        # Generate URL
        image.url = ImageFileProcessor.get_file_url(image.file_path)

        # HIPAA: Log public access
        await log_audit_event(
            db, None, "public_image_viewed", "patient_image", image.id, request,
            {"source": "public_link", "token_used": resolved_token[:8] + "..."}
        )
        await db.commit()

        return image

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error retrieving public image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving image",
        )


# ============================================
# Image Series Endpoints
# ============================================

@router.get("/patients/{patient_id}/series", response_model=ImageSeriesListResponse)
async def list_image_series(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImageSeriesListResponse:
    """
    List image series for patient
    """
    try:
        # Verify patient belongs to practice
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # Get series using service
        series = await ImagingService.get_image_series(db, patient_id, current_user.practice_id)

        return ImageSeriesListResponse(
            series=series,
            count=len(series),
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing image series: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving series",
        )


@router.post("/patients/{patient_id}/series", response_model=ImageSeriesResponse)
async def create_image_series(
    patient_id: str,
    series_data: ImageSeriesCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ImageSeriesResponse:
    """
    Create image series
    """
    try:
        # Verify patient belongs to practice
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # M-12 FIX: the supplied provider was written unvalidated, so a series
        # could be attributed to another practice's clinician (and that name
        # then surfaced on every read of the series).
        if series_data.provider_id:
            await require_provider(
                db,
                series_data.provider_id,
                current_user.practice_id,
                field="Provider",
                roles=IMAGING_PROVIDER_ROLES,
            )

        # Create series
        series = await ImagingService.create_series(
            db=db,
            practice_id=current_user.practice_id,
            patient_id=patient_id,
            provider_id=series_data.provider_id or current_user.id,
            **series_data.dict(exclude={'provider_id'})
        )

        return series

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating image series: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating series",
        )


@router.get("/series/{series_id}", response_model=ImageSeriesResponse)
async def get_image_series(
    series_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImageSeriesResponse:
    """
    Get image series by ID
    """
    try:
        series = await ImagingService.get_series(db, series_id, current_user.practice_id)

        if not series:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image series not found",
            )

        return series

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error retrieving image series: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving series",
        )


@router.put("/series/{series_id}", response_model=ImageSeriesResponse)
async def update_image_series(
    series_id: str,
    series_data: ImageSeriesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ImageSeriesResponse:
    """
    Update image series
    """
    try:
        series = await ImagingService.get_series(db, series_id, current_user.practice_id)

        if not series:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image series not found",
            )

        # Update series (pass practice_id: the primitive requires it).
        update_data = series_data.dict(exclude_unset=True)
        series = await ImagingService.update_series(
            db, series_id, current_user.practice_id, **update_data
        )

        return series

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating image series: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating series",
        )


# ============================================
# Image Template Endpoints
# ============================================

@router.get("/templates/", response_model=ImageTemplateListResponse)
async def list_templates(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImageTemplateListResponse:
    """
    List image templates
    """
    try:
        templates = await ImagingService.get_templates(db, current_user.practice_id, is_active)

        return ImageTemplateListResponse(
            templates=templates,
            count=len(templates),
        )

    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving templates",
        )


@router.post("/templates/", response_model=ImageTemplateResponse)
async def create_template(
    template_data: ImageTemplateCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ImageTemplateResponse:
    """
    Create image template
    """
    try:
        # Create template
        template = await ImagingService.create_template(
            db=db,
            practice_id=current_user.practice_id,
            name=template_data.name,
            configuration=[conf.dict() for conf in template_data.configuration],
            description=template_data.description,
            is_active=template_data.is_active,
        )

        return template

    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating template",
        )


@router.put("/templates/{template_id}", response_model=ImageTemplateResponse)
async def update_template(
    template_id: str,
    template_data: ImageTemplateUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ImageTemplateResponse:
    """
    Update image template
    """
    try:
        template = await ImagingService.get_template(db, template_id, current_user.practice_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )

        # Update template
        update_data = template_data.dict(exclude_unset=True)
        if 'configuration' in update_data and update_data['configuration']:
            update_data['configuration'] = [conf.dict() for conf in update_data['configuration']]

        template = await ImagingService.update_template(
            db, template_id, current_user.practice_id, **update_data
        )

        return template

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating template",
        )
