"""
Imaging Service
Core business logic for imaging operations
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.imaging import PatientImage, ImageSeries, ImageTemplate, ImageType, ImageCategory

logger = logging.getLogger(__name__)

# M-12: columns a caller may never overwrite through a generic update. These
# are ownership/identity fields; changing them re-parents PHI.
_IMAGE_IMMUTABLE_FIELDS = frozenset(
    {"id", "practice_id", "patient_id", "created_at", "updated_at"}
)
_SERIES_IMMUTABLE_FIELDS = _IMAGE_IMMUTABLE_FIELDS


class ImagingService:
    """Service for imaging operations"""

    @staticmethod
    async def get_patient_images(
        db: AsyncSession,
        patient_id: UUID,
        practice_id: UUID,
        image_type: Optional[ImageType] = None,
        category: Optional[ImageCategory] = None,
        tooth_number: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[PatientImage]:
        """Get patient images with filtering"""
        query = select(PatientImage).where(
            PatientImage.patient_id == patient_id,
            PatientImage.practice_id == practice_id,
            PatientImage.is_deleted.is_(False),
        )

        if image_type:
            query = query.where(PatientImage.image_type == image_type)

        if category:
            query = query.where(PatientImage.category == category)

        if tooth_number:
            query = query.where(PatientImage.tooth_number == tooth_number)

        if start_date:
            query = query.where(PatientImage.acquisition_date >= start_date)

        if end_date:
            query = query.where(PatientImage.acquisition_date <= end_date)

        query = query.order_by(PatientImage.acquisition_date.desc())

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_image(
        db: AsyncSession,
        image_id: UUID,
        practice_id: UUID,
    ) -> Optional[PatientImage]:
        """Get an image"""
        result = await db.execute(
            select(PatientImage).where(
                PatientImage.id == image_id,
                PatientImage.practice_id == practice_id,
                PatientImage.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_public_image(
        db: AsyncSession,
        image_id: UUID,
        token: str,
    ) -> Optional[PatientImage]:
        """Get image by public share token.

        L1 FIX: enforce the 30-day expiry the share email promises.
        ``share_expires_at IS NULL`` is a legacy (pre-enforcement) share and
        stays valid — grandfathered deliberately so existing links don't
        break; every newly created share always carries an expiry.
        """
        result = await db.execute(
            select(PatientImage).where(
                PatientImage.id == image_id,
                PatientImage.share_token == token,
                PatientImage.is_deleted.is_(False),
            )
        )
        image = result.scalar_one_or_none()
        if image is None:
            return None

        expires_at = image.share_expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                from datetime import timezone as _tz
                expires_at = expires_at.replace(tzinfo=_tz.utc)
            from datetime import datetime as _dt, timezone as _tz
            if expires_at < _dt.now(_tz.utc):
                return None
        return image

    @staticmethod
    async def create_image(
        db: AsyncSession,
        practice_id: UUID,
        patient_id: UUID,
        provider_id: UUID,
        image_type: ImageType,
        file_path: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        **kwargs
    ) -> PatientImage:
        """Create an image record"""
        image = PatientImage(
            practice_id=practice_id,
            patient_id=patient_id,
            provider_id=provider_id,
            image_type=image_type,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            acquisition_date=datetime.now(timezone.utc),
            **kwargs
        )
        db.add(image)
        await db.commit()
        await db.refresh(image)
        logger.info(f"Created image record: {image.id}")
        return image

    @staticmethod
    async def update_image(
        db: AsyncSession,
        image_id: UUID,
        practice_id: UUID,
        **kwargs
    ) -> Optional[PatientImage]:
        """Update image metadata.

        M-12 FIX: ``practice_id`` is required and applied as a predicate. This
        method used to look the image up by id alone; the current routes happen
        to pre-check ownership, but that made the service an unsafe reusable
        primitive -- any future call site that trusted it would have a
        cross-tenant write. Identity columns are also no longer settable.
        """
        stmt = select(PatientImage).where(
            PatientImage.id == image_id,
            PatientImage.practice_id == practice_id,
        )
        image = (await db.execute(stmt)).scalar_one_or_none()

        if not image:
            return None

        for key, value in kwargs.items():
            if key in _IMAGE_IMMUTABLE_FIELDS:
                continue
            if hasattr(image, key):
                setattr(image, key, value)

        await db.commit()
        await db.refresh(image)
        logger.info(f"Updated image: {image_id}")
        return image

    @staticmethod
    async def delete_image(
        db: AsyncSession,
        image_id: UUID,
        practice_id: UUID,
    ) -> bool:
        """Soft delete an image.

        M-12 FIX: practice_id is now mandatory rather than an optional
        opt-in — an omitted tenant scope silently deleted across tenants.
        """
        stmt = select(PatientImage).where(
            PatientImage.id == image_id,
            PatientImage.practice_id == practice_id,
        )
        result = await db.execute(stmt)
        image = result.scalar_one_or_none()

        if not image:
            return False

        image.is_deleted = True
        image.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Deleted image: {image_id}")
        return True

    @staticmethod
    async def add_annotations(
        db: AsyncSession,
        image_id: UUID,
        annotations: List[Dict[str, Any]],
        practice_id: UUID,
    ) -> Optional[PatientImage]:
        """Add annotations to image (M-12: tenant-scoped)."""
        result = await db.execute(
            select(PatientImage).where(
                PatientImage.id == image_id,
                PatientImage.practice_id == practice_id,
            )
        )
        image = result.scalar_one_or_none()

        if not image:
            return None

        # Convert annotations to JSON string
        annotations_json = json.dumps(annotations)
        image.annotations = annotations_json

        await db.commit()
        await db.refresh(image)
        logger.info(f"Added annotations to image: {image_id}")
        return image

    @staticmethod
    async def get_image_series(
        db: AsyncSession,
        patient_id: UUID,
        practice_id: UUID,
    ) -> List[ImageSeries]:
        """Get image series for patient"""
        query = select(ImageSeries).where(
            ImageSeries.patient_id == patient_id,
            ImageSeries.practice_id == practice_id,
        ).order_by(ImageSeries.acquisition_date.desc())

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_series(
        db: AsyncSession,
        series_id: UUID,
        practice_id: UUID,
    ) -> Optional[ImageSeries]:
        """Get a series"""
        result = await db.execute(
            select(ImageSeries).where(
                ImageSeries.id == series_id,
                ImageSeries.practice_id == practice_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_series(
        db: AsyncSession,
        practice_id: UUID,
        patient_id: UUID,
        provider_id: UUID,
        **kwargs
    ) -> ImageSeries:
        """Create an image series"""
        series = ImageSeries(
            practice_id=practice_id,
            patient_id=patient_id,
            provider_id=provider_id,
            **kwargs
        )
        db.add(series)
        await db.commit()
        await db.refresh(series)
        logger.info(f"Created image series: {series.id}")
        return series

    @staticmethod
    async def update_series(
        db: AsyncSession,
        series_id: UUID,
        practice_id: UUID,
        **kwargs
    ) -> Optional[ImageSeries]:
        """Update image series (M-12: tenant-scoped, identity fields frozen)."""
        result = await db.execute(
            select(ImageSeries).where(
                ImageSeries.id == series_id,
                ImageSeries.practice_id == practice_id,
            )
        )
        series = result.scalar_one_or_none()

        if not series:
            return None

        for key, value in kwargs.items():
            if key in _SERIES_IMMUTABLE_FIELDS:
                continue
            if hasattr(series, key):
                setattr(series, key, value)

        await db.commit()
        await db.refresh(series)
        logger.info(f"Updated image series: {series_id}")
        return series

    @staticmethod
    async def get_templates(
        db: AsyncSession,
        practice_id: UUID,
        is_active: Optional[bool] = None,
    ) -> List[ImageTemplate]:
        """Get image templates"""
        query = select(ImageTemplate).where(
            ImageTemplate.practice_id == practice_id
        )

        if is_active is not None:
            query = query.where(ImageTemplate.is_active == is_active)

        query = query.order_by(ImageTemplate.name)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_template(
        db: AsyncSession,
        template_id: UUID,
        practice_id: UUID,
    ) -> Optional[ImageTemplate]:
        """Get a template"""
        result = await db.execute(
            select(ImageTemplate).where(
                ImageTemplate.id == template_id,
                ImageTemplate.practice_id == practice_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_template(
        db: AsyncSession,
        practice_id: UUID,
        name: str,
        configuration: List[Dict[str, Any]],
        **kwargs
    ) -> ImageTemplate:
        """Create an image template"""
        # Convert configuration to JSON string
        configuration_json = json.dumps(configuration)

        template = ImageTemplate(
            practice_id=practice_id,
            name=name,
            configuration=configuration_json,
            **kwargs
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        logger.info(f"Created image template: {template.id}")
        return template

    @staticmethod
    async def update_template(
        db: AsyncSession,
        template_id: UUID,
        practice_id: UUID | None = None,
        **kwargs
    ) -> Optional[ImageTemplate]:
        """Update image template (L-10 FIX: scope by practice_id like siblings)."""
        stmt = select(ImageTemplate).where(ImageTemplate.id == template_id)
        if practice_id is not None:
            stmt = stmt.where(ImageTemplate.practice_id == practice_id)
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            return None

        # Handle configuration conversion
        if 'configuration' in kwargs and kwargs['configuration']:
            configuration_json = json.dumps(kwargs['configuration'])
            kwargs['configuration'] = configuration_json

        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)

        await db.commit()
        await db.refresh(template)
        logger.info(f"Updated image template: {template_id}")
        return template
