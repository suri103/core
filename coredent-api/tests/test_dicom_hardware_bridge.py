"""
Tests for DICOM Parser and Hardware Sensor Bridge Endpoints
"""

import base64
import struct
import pytest
from httpx import AsyncClient

from app.core.dicom_parser import DicomParser, DicomParseError
from app.models.user import UserRole


def build_synthetic_dicom() -> bytes:
    """Build a minimal valid DICOM Part 10 binary file with explicit VR elements."""
    preamble = b"\x00" * 128
    magic = b"DICM"

    elements = bytearray()

    # Patient Name (0x0010, 0x0010), VR=PN, length=8, "Doe^Jane"
    val = b"Doe^Jane"
    elements.extend(struct.pack("<HH", 0x0010, 0x0010))
    elements.extend(b"PN")
    elements.extend(struct.pack("<H", len(val)))
    elements.extend(val)

    # Patient ID (0x0010, 0x0020), VR=LO, length=7, "PAT0099"
    val_id = b"PAT0099"
    elements.extend(struct.pack("<HH", 0x0010, 0x0020))
    elements.extend(b"LO")
    elements.extend(struct.pack("<H", len(val_id)))
    elements.extend(val_id)

    # Modality (0x0008, 0x0060), VR=CS, length=2, "IO"
    elements.extend(struct.pack("<HH", 0x0008, 0x0060))
    elements.extend(b"CS")
    elements.extend(struct.pack("<H", 2))
    elements.extend(b"IO")

    # Rows (0x0028, 0x0010), VR=US, length=2, 512
    elements.extend(struct.pack("<HH", 0x0028, 0x0010))
    elements.extend(b"US")
    elements.extend(struct.pack("<H", 2))
    elements.extend(struct.pack("<H", 512))

    # Columns (0x0028, 0x0011), VR=US, length=2, 512
    elements.extend(struct.pack("<HH", 0x0028, 0x0011))
    elements.extend(b"US")
    elements.extend(struct.pack("<H", 2))
    elements.extend(struct.pack("<H", 512))

    # Pixel Data (0x7FE0, 0x0010), VR=OW, 2 reserved bytes, length 32
    pixel_bytes = b"\x80" * 32
    elements.extend(struct.pack("<HH", 0x7FE0, 0x0010))
    elements.extend(b"OW")
    elements.extend(b"\x00\x00")
    elements.extend(struct.pack("<I", len(pixel_bytes)))
    elements.extend(pixel_bytes)

    return preamble + magic + bytes(elements)


class TestDicomParser:
    def test_parses_valid_dicom(self):
        raw = build_synthetic_dicom()
        assert DicomParser.is_dicom(raw) is True

        meta = DicomParser.parse(raw)
        assert meta.patient_name == "Doe Jane"
        assert meta.patient_id == "PAT0099"
        assert meta.modality == "IO"
        assert meta.rows == 512
        assert meta.columns == 512
        assert meta.pixel_data_length == 32

    def test_rejects_non_dicom(self):
        raw = b"NOT_A_DICOM_FILE_HEADER" + (b"\x00" * 150)
        assert DicomParser.is_dicom(raw) is False
        with pytest.raises(DicomParseError):
            DicomParser.parse(raw)


@pytest.mark.asyncio
class TestHardwareBridgeEndpoints:
    async def test_get_bridge_config(self, async_client: AsyncClient, auth_headers: dict):
        response = await async_client.get(
            "/api/v1/imaging/hardware-bridge/config",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.4.0"
        assert data["bridge_port"] == 19844
        assert len(data["supported_sensors"]) >= 5
        sensor_ids = [s["id"] for s in data["supported_sensors"]]
        assert "dexis_titanium" in sensor_ids
        assert "schick_33" in sensor_ids

    async def test_list_connected_devices(self, async_client: AsyncClient, auth_headers: dict):
        response = await async_client.get(
            "/api/v1/imaging/hardware-bridge/devices",
            headers=auth_headers,
        )
        assert response.status_code == 200
        devices = response.json()
        assert isinstance(devices, list)
        assert any(d["vendor"] == "Carestream Dental" for d in devices)

    async def test_session_lifecycle_and_acquire(
        self, async_client: AsyncClient, auth_headers: dict, test_patient
    ):
        # 1. Create capture session
        session_res = await async_client.post(
            "/api/v1/imaging/hardware-bridge/sessions",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "sensor_id": "dexis_titanium",
                "mount_type": "bitewing_4",
                "tooth_number": "14",
            },
        )
        assert session_res.status_code == 200
        session_data = session_res.json()
        token = session_data["session_token"]
        assert token is not None

        # 2. Acquire DICOM frame
        dcm_bytes = build_synthetic_dicom()
        b64_payload = base64.b64encode(dcm_bytes).decode("ascii")

        acquire_res = await async_client.post(
            "/api/v1/imaging/hardware-bridge/acquire",
            headers=auth_headers,
            json={
                "session_token": token,
                "sensor_id": "dexis_titanium",
                "image_format": "dcm",
                "raw_base64_data": b64_payload,
                "tooth_number": "14",
                "kvp": 70.0,
                "exposure_time_ms": 120.0,
            },
        )
        assert acquire_res.status_code == 200
        acq_data = acquire_res.json()
        assert acq_data["success"] is True
        assert acq_data["tooth_number"] == "14"
        assert acq_data["dicom_metadata"]["modality"] == "IO"

        # 3. Replay with consumed token fails
        replay_res = await async_client.post(
            "/api/v1/imaging/hardware-bridge/acquire",
            headers=auth_headers,
            json={
                "session_token": token,
                "sensor_id": "dexis_titanium",
                "image_format": "dcm",
                "raw_base64_data": b64_payload,
            },
        )
        assert replay_res.status_code == 401
