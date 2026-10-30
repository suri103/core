import pytest
import uuid
import json
from app.services.imaging_service import ImagingService
from app.models.imaging import ImageType, ImageCategory

@pytest.mark.asyncio
class TestImagingService:
    async def test_create_image(self, db_session, test_practice, test_patient, test_user):
        """Test creating an image record."""
        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/to/image.png",
            file_name="image.png",
            file_size=1024,
            mime_type="image/png",
            tooth_number="14",
            category=ImageCategory.INTRAORAL
        )
        assert image.id is not None
        assert image.image_type == ImageType.XRAY
        assert image.tooth_number == "14"
        assert image.practice_id == test_practice.id

    async def test_get_patient_images(self, db_session, test_practice, test_patient, test_user):
        """Test retrieving multiple patient images with filtering."""
        # Create images with different types
        await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/1.png",
            file_name="1.png",
            file_size=1024,
            mime_type="image/png",
            category=ImageCategory.INTRAORAL
        )
        await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.PHOTO,
            file_path="/path/2.png",
            file_name="2.png",
            file_size=2048,
            mime_type="image/png",
            category=ImageCategory.EXTRAORAL
        )
        
        # Test basic retrieval
        images = await ImagingService.get_patient_images(
            db=db_session,
            patient_id=test_patient.id,
            practice_id=test_practice.id
        )
        assert len(images) >= 2
        
        # Test filtering by type
        xrays = await ImagingService.get_patient_images(
            db=db_session,
            patient_id=test_patient.id,
            practice_id=test_practice.id,
            image_type=ImageType.XRAY
        )
        assert len(xrays) >= 1
        assert xrays[0].image_type == ImageType.XRAY

    async def test_get_image(self, db_session, test_practice, test_patient, test_user):
        """Test retrieving a single image by ID."""
        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/1.png",
            file_name="1.png",
            file_size=1024,
            mime_type="image/png"
        )
        
        fetched = await ImagingService.get_image(db_session, image.id, test_practice.id)
        assert fetched is not None
        assert fetched.id == image.id
        
        # Test non-existent ID
        none_image = await ImagingService.get_image(db_session, uuid.uuid4(), test_practice.id)
        assert none_image is None

    async def test_update_image(self, db_session, test_practice, test_patient, test_user):
        """Test updating image metadata."""
        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/1.png",
            file_name="1.png",
            file_size=1024,
            mime_type="image/png"
        )
        
        updated = await ImagingService.update_image(
            db=db_session,
            image_id=image.id,
            practice_id=test_practice.id,
            tooth_number="15",
            notes="Updated note"
        )
        assert updated.tooth_number == "15"
        assert updated.notes == "Updated note"

    async def test_update_image_rejects_other_practice(
        self, db_session, test_practice, test_patient, test_user
    ):
        """M-12: the service itself refuses a cross-tenant update."""
        from uuid import uuid4

        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/tenant.png",
            file_name="tenant.png",
            file_size=1024,
            mime_type="image/png",
        )

        result = await ImagingService.update_image(
            db=db_session,
            image_id=image.id,
            practice_id=uuid4(),
            notes="should not apply",
        )
        assert result is None

        await db_session.refresh(image)
        assert image.notes != "should not apply"

    async def test_update_image_ignores_identity_fields(
        self, db_session, test_practice, test_patient, test_user
    ):
        """M-12: patient_id cannot be re-parented through a generic update."""
        from uuid import uuid4

        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/identity.png",
            file_name="identity.png",
            file_size=1024,
            mime_type="image/png",
        )

        updated = await ImagingService.update_image(
            db=db_session,
            image_id=image.id,
            practice_id=test_practice.id,
            patient_id=uuid4(),
            notes="ok",
        )
        assert updated is not None
        assert updated.notes == "ok"
        # The identity columns are unchanged despite being supplied.
        assert updated.patient_id == test_patient.id
        assert updated.practice_id == test_practice.id

    async def test_delete_image(self, db_session, test_practice, test_patient, test_user):
        """Test soft-deleting an image."""
        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/1.png",
            file_name="1.png",
            file_size=1024,
            mime_type="image/png"
        )
        
        success = await ImagingService.delete_image(
            db_session, image.id, test_practice.id
        )
        assert success is True
        
        # Verify it's soft deleted
        fetched = await ImagingService.get_image(db_session, image.id, test_practice.id)
        assert fetched is None

    async def test_add_annotations(self, db_session, test_practice, test_patient, test_user):
        """Test adding JSON annotations to an image."""
        image = await ImagingService.create_image(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            image_type=ImageType.XRAY,
            file_path="/path/1.png",
            file_name="1.png",
            file_size=1024,
            mime_type="image/png"
        )
        
        annotations = [
            {"type": "arrow", "x": 100, "y": 200, "label": "Caries detected"},
            {"type": "rect", "x1": 50, "y1": 50, "x2": 150, "y2": 150}
        ]
        
        updated = await ImagingService.add_annotations(
            db_session, image.id, annotations, test_practice.id
        )
        assert updated.annotations is not None
        if isinstance(updated.annotations, str):
            saved_annotations = json.loads(updated.annotations)
        else:
            saved_annotations = updated.annotations
            
        assert len(saved_annotations) == 2
        assert saved_annotations[0]["label"] == "Caries detected"

    async def test_series_operations(self, db_session, test_practice, test_patient, test_user):
        """Test CRUD operations for image series."""
        from datetime import datetime as _dt
        series = await ImagingService.create_series(
            db=db_session,
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            series_name="Full Mouth Series",
            acquisition_date=_dt.now()
        )
        assert series.id is not None
        
        all_series = await ImagingService.get_image_series(db_session, test_patient.id, test_practice.id)
        assert len(all_series) == 1
        
        fetched = await ImagingService.get_series(db_session, series.id, test_practice.id)
        assert fetched.id == series.id
        
        updated = await ImagingService.update_series(
            db_session, series.id, test_practice.id, series_name="Updated Series Name"
        )
        assert updated.series_name == "Updated Series Name"

    async def test_template_operations(self, db_session, test_practice):
        """Test CRUD operations for image templates."""
        config = [{"position": 1, "type": "bitewing", "label": "UR"}]
        template = await ImagingService.create_template(
            db=db_session,
            practice_id=test_practice.id,
            name="Standard FMX",
            configuration=config
        )
        assert template.id is not None
        
        templates = await ImagingService.get_templates(db_session, test_practice.id, is_active=True)
        assert len(templates) == 1
        
        fetched = await ImagingService.get_template(db_session, template.id, test_practice.id)
        assert fetched.id == template.id
        
        new_config = [{"position": 1, "type": "bitewing", "label": "UR_NEW"}]
        updated = await ImagingService.update_template(
            db=db_session, 
            template_id=template.id, 
            configuration=new_config,
            is_active=False
        )
        assert updated.is_active is False
        
        if isinstance(updated.configuration, str):
            saved_config = json.loads(updated.configuration)
        else:
            saved_config = updated.configuration
        assert saved_config[0]["label"] == "UR_NEW"
