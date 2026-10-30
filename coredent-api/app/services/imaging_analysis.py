"""
Imaging Analysis Service
Handles imaging statistics, analysis, and reporting
"""

from typing import Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.imaging import PatientImage
from app.models.patient import Patient

logger = logging.getLogger(__name__)


class ImagingAnalysisService:
    """Service for imaging analysis and statistics"""

    @staticmethod
    async def get_imaging_statistics(
        db: AsyncSession,
        practice_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get imaging statistics for practice"""
        try:
            # Default to last 30 days if not specified
            if not start_date:
                start_date = datetime.now(timezone.utc) - timedelta(days=30)
            if not end_date:
                end_date = datetime.now(timezone.utc)

            # Total images
            total_result = await db.execute(
                select(func.count(PatientImage.id)).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                )
            )
            total_images = total_result.scalar() or 0

            # Images in date range
            recent_result = await db.execute(
                select(func.count(PatientImage.id)).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                    PatientImage.acquisition_date >= start_date,
                    PatientImage.acquisition_date <= end_date,
                )
            )
            recent_images = recent_result.scalar() or 0

            # Total storage used
            storage_result = await db.execute(
                select(func.sum(PatientImage.file_size)).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                )
            )
            total_storage = storage_result.scalar() or 0

            # Images by type
            type_result = await db.execute(
                select(
                    PatientImage.image_type,
                    func.count(PatientImage.id).label('count')
                ).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                ).group_by(PatientImage.image_type)
            )
            images_by_type = {
                str(row[0]): row[1] for row in type_result.fetchall()
            }

            # Images by category
            category_result = await db.execute(
                select(
                    PatientImage.category,
                    func.count(PatientImage.id).label('count')
                ).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                ).group_by(PatientImage.category)
            )
            images_by_category = {
                str(row[0]): row[1] for row in category_result.fetchall()
            }

            # Shared images
            shared_result = await db.execute(
                select(func.count(PatientImage.id)).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                    PatientImage.is_shared_with_patient.is_(True),
                )
            )
            shared_images = shared_result.scalar() or 0

            logger.info(f"Generated imaging statistics for practice: {practice_id}")

            return {
                "total_images": total_images,
                "recent_images": recent_images,
                "total_storage_bytes": total_storage,
                "total_storage_mb": round(total_storage / (1024 * 1024), 2),
                "images_by_type": images_by_type,
                "images_by_category": images_by_category,
                "shared_images": shared_images,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error generating imaging statistics: {str(e)}")
            return {
                "total_images": 0,
                "recent_images": 0,
                "total_storage_bytes": 0,
                "total_storage_mb": 0,
                "images_by_type": {},
                "images_by_category": {},
                "shared_images": 0,
            }

    @staticmethod
    async def get_patient_imaging_summary(
        db: AsyncSession,
        patient_id: UUID,
        practice_id: UUID,
    ) -> Dict[str, Any]:
        """Get imaging summary for a patient"""
        try:
            # Get patient
            patient_result = await db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.practice_id == practice_id,
                )
            )
            patient = patient_result.scalar_one_or_none()

            if not patient:
                return {}

            # Total images
            total_result = await db.execute(
                select(func.count(PatientImage.id)).where(
                    PatientImage.patient_id == patient_id,
                    PatientImage.is_deleted.is_(False),
                )
            )
            total_images = total_result.scalar() or 0

            # Latest image
            latest_result = await db.execute(
                select(PatientImage).where(
                    PatientImage.patient_id == patient_id,
                    PatientImage.is_deleted.is_(False),
                ).order_by(PatientImage.acquisition_date.desc()).limit(1)
            )
            latest_image = latest_result.scalar_one_or_none()

            # Images by type
            type_result = await db.execute(
                select(
                    PatientImage.image_type,
                    func.count(PatientImage.id).label('count')
                ).where(
                    PatientImage.patient_id == patient_id,
                    PatientImage.is_deleted.is_(False),
                ).group_by(PatientImage.image_type)
            )
            images_by_type = {
                str(row[0]): row[1] for row in type_result.fetchall()
            }

            # Total storage
            storage_result = await db.execute(
                select(func.sum(PatientImage.file_size)).where(
                    PatientImage.patient_id == patient_id,
                    PatientImage.is_deleted.is_(False),
                )
            )
            total_storage = storage_result.scalar() or 0

            logger.info(f"Generated imaging summary for patient: {patient_id}")

            return {
                "patient_id": str(patient_id),
                "total_images": total_images,
                "latest_image": {
                    "id": str(latest_image.id),
                    "type": str(latest_image.image_type),
                    "date": latest_image.acquisition_date.isoformat(),
                } if latest_image else None,
                "images_by_type": images_by_type,
                "total_storage_bytes": total_storage,
                "total_storage_mb": round(total_storage / (1024 * 1024), 2),
            }

        except Exception as e:
            logger.error(f"Error generating patient imaging summary: {str(e)}")
            return {}

    @staticmethod
    async def get_imaging_trends(
        db: AsyncSession,
        practice_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get imaging trends over time (M-5 FIX: bucket by practice-local day)."""
        try:
            from app.core.business_time import day_expr, get_practice_timezone_name

            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            tz_name = await get_practice_timezone_name(db, practice_id)
            # Predicates stay UTC (index-friendly); GROUP BY uses the
            # practice-local date like reports.py so non-UTC practices do not
            # see off-by-one days around midnight/DST.
            day_col = day_expr(PatientImage.acquisition_date, tz_name)

            # Get daily image counts
            result = await db.execute(
                select(
                    day_col.label('date'),
                    func.count(PatientImage.id).label('count')
                ).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                    PatientImage.acquisition_date >= start_date,
                ).group_by(day_col)
                .order_by(day_col)
            )

            daily_counts = [
                {
                    "date": str(row[0]),
                    "count": row[1],
                } for row in result.fetchall()
            ]

            logger.info(f"Generated imaging trends for practice: {practice_id}")

            return {
                "period_days": days,
                "daily_counts": daily_counts,
                "total_images": sum(item["count"] for item in daily_counts),
            }

        except Exception as e:
            logger.error(f"Error generating imaging trends: {str(e)}")
            return {
                "period_days": days,
                "daily_counts": [],
                "total_images": 0,
            }

    @staticmethod
    async def get_storage_breakdown(
        db: AsyncSession,
        practice_id: UUID,
    ) -> Dict[str, Any]:
        """Get storage breakdown by image type"""
        try:
            result = await db.execute(
                select(
                    PatientImage.image_type,
                    func.count(PatientImage.id).label('count'),
                    func.sum(PatientImage.file_size).label('total_size')
                ).where(
                    PatientImage.practice_id == practice_id,
                    PatientImage.is_deleted.is_(False),
                ).group_by(PatientImage.image_type)
            )

            breakdown = []
            total_size = 0

            for row in result.fetchall():
                size = row[2] or 0
                total_size += size
                breakdown.append({
                    "type": str(row[0]),
                    "count": row[1],
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                })

            logger.info(f"Generated storage breakdown for practice: {practice_id}")

            return {
                "breakdown": breakdown,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            }

        except Exception as e:
            logger.error(f"Error generating storage breakdown: {str(e)}")
            return {
                "breakdown": [],
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "total_size_gb": 0,
            }
