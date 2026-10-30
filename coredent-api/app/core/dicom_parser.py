"""
DICOM Part 10 File Parser for Dental Radiography
Pure-Python parser for DICOM files from intraoral sensors (IO), panoramic (PX),
and digital radiography (DX) units without external C dependencies.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class DicomMetadata:
    """Parsed DICOM metadata tags relevant to dental practice management."""
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_sex: Optional[str] = None
    modality: str = "IO"  # IO (intraoral), PX (panoramic), DX (digital x-ray)
    study_date: Optional[str] = None
    study_description: Optional[str] = None
    study_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    sop_instance_uid: Optional[str] = None
    kvp: Optional[float] = None
    exposure_time_ms: Optional[float] = None
    rows: int = 0
    columns: int = 0
    bits_allocated: int = 16
    bits_stored: int = 12
    photometric_interpretation: str = "MONOCHROME2"
    tooth_number: Optional[str] = None
    pixel_data_length: int = 0
    raw_tags: Dict[str, Any] = field(default_factory=dict)


class DicomParseError(ValueError):
    """Raised when a file does not conform to the DICOM standard."""
    pass


class DicomParser:
    """Parses standard DICOM Part 10 binary files."""

    DICM_MAGIC = b"DICM"
    PREAMBLE_LENGTH = 128

    # Standard explicit VR tags where length is 4 bytes preceded by 2 reserved bytes
    EXPLICIT_VR_LONG = {"OB", "OW", "OF", "OD", "OL", "UC", "UR", "UT", "UN", "SQ"}

    # Common Dental DICOM Tags
    TAG_PATIENT_NAME = (0x0010, 0x0010)
    TAG_PATIENT_ID = (0x0010, 0x0020)
    TAG_PATIENT_DOB = (0x0010, 0x0030)
    TAG_PATIENT_SEX = (0x0010, 0x0040)
    TAG_MODALITY = (0x0008, 0x0060)
    TAG_STUDY_DATE = (0x0008, 0x0020)
    TAG_STUDY_DESC = (0x0008, 0x1030)
    TAG_STUDY_UID = (0x0020, 0x000D)
    TAG_SERIES_UID = (0x0020, 0x000E)
    TAG_SOP_UID = (0x0008, 0x0018)
    TAG_KVP = (0x0018, 0x0060)
    TAG_EXPOSURE_TIME = (0x0018, 0x1150)
    TAG_ROWS = (0x0028, 0x0010)
    TAG_COLUMNS = (0x0028, 0x0011)
    TAG_BITS_ALLOCATED = (0x0028, 0x0100)
    TAG_BITS_STORED = (0x0028, 0x0101)
    TAG_PHOTOMETRIC = (0x0028, 0x0004)
    TAG_PIXEL_DATA = (0x7FE0, 0x0010)

    @classmethod
    def is_dicom(cls, data: bytes) -> bool:
        """Check if bytes start with or contain DICOM Part 10 magic bytes."""
        if len(data) < cls.PREAMBLE_LENGTH + 4:
            return False
        return data[cls.PREAMBLE_LENGTH : cls.PREAMBLE_LENGTH + 4] == cls.DICM_MAGIC

    @classmethod
    def parse(cls, data: bytes) -> DicomMetadata:
        """Parse DICOM bytes into structured DicomMetadata."""
        if not cls.is_dicom(data):
            raise DicomParseError("File missing DICOM Part 10 header ('DICM' magic at offset 128)")

        meta = DicomMetadata()
        offset = cls.PREAMBLE_LENGTH + 4
        length = len(data)

        # Detect explicit vs implicit VR by inspecting first data element after File Meta Information
        # File Meta Info elements (Group 0x0002) are always Explicit VR Little Endian
        is_explicit = True

        while offset + 8 <= length:
            group, elem = struct.unpack_from("<HH", data, offset)
            offset += 4

            if (group, elem) == (0xFFFE, 0xE0DD):  # Sequence delimitation item
                offset += 4
                continue

            vr: Optional[str] = None
            elem_len: int = 0

            # Inspect VR
            possible_vr = data[offset : offset + 2].decode("ascii", errors="ignore")
            if is_explicit and possible_vr.isalpha() and possible_vr.isupper():
                vr = possible_vr
                offset += 2
                if vr in cls.EXPLICIT_VR_LONG:
                    offset += 2  # 2 reserved bytes
                    if offset + 4 <= length:
                        elem_len = struct.unpack_from("<I", data, offset)[0]
                        offset += 4
                    else:
                        break
                else:
                    if offset + 2 <= length:
                        elem_len = struct.unpack_from("<H", data, offset)[0]
                        offset += 2
                    else:
                        break
            else:
                # Implicit VR Little Endian
                if offset + 4 <= length:
                    elem_len = struct.unpack_from("<I", data, offset)[0]
                    offset += 4
                else:
                    break

            if elem_len == 0xFFFFFFFF:
                # Undefined length (e.g. encapsulated pixel data or sequence)
                if (group, elem) == cls.TAG_PIXEL_DATA:
                    meta.pixel_data_length = length - offset
                    break
                else:
                    # Skip until end of item or next tag
                    continue

            if offset + elem_len > length:
                val_bytes = data[offset:]
                offset = length
            else:
                val_bytes = data[offset : offset + elem_len]
                offset += elem_len

            tag = (group, elem)

            # Map tag to metadata field
            try:
                cls._map_tag(meta, tag, val_bytes, vr)
            except Exception:
                pass  # Tolerate corrupted or unusual tag formatting

            if tag == cls.TAG_PIXEL_DATA:
                meta.pixel_data_length = len(val_bytes)
                break

        return meta

    @classmethod
    def _map_tag(cls, meta: DicomMetadata, tag: Tuple[int, int], val_bytes: bytes, vr: Optional[str]) -> None:
        def to_str(b: bytes) -> str:
            return b.decode("utf-8", errors="replace").strip("\x00 \t\r\n")

        if tag == cls.TAG_PATIENT_NAME:
            meta.patient_name = to_str(val_bytes).replace("^", " ")
        elif tag == cls.TAG_PATIENT_ID:
            meta.patient_id = to_str(val_bytes)
        elif tag == cls.TAG_PATIENT_DOB:
            meta.patient_dob = to_str(val_bytes)
        elif tag == cls.TAG_PATIENT_SEX:
            meta.patient_sex = to_str(val_bytes).upper()
        elif tag == cls.TAG_MODALITY:
            meta.modality = to_str(val_bytes).upper() or "IO"
        elif tag == cls.TAG_STUDY_DATE:
            meta.study_date = to_str(val_bytes)
        elif tag == cls.TAG_STUDY_DESC:
            meta.study_description = to_str(val_bytes)
        elif tag == cls.TAG_STUDY_UID:
            meta.study_instance_uid = to_str(val_bytes)
        elif tag == cls.TAG_SERIES_UID:
            meta.series_instance_uid = to_str(val_bytes)
        elif tag == cls.TAG_SOP_UID:
            meta.sop_instance_uid = to_str(val_bytes)
        elif tag == cls.TAG_KVP:
            try:
                meta.kvp = float(to_str(val_bytes))
            except ValueError:
                pass
        elif tag == cls.TAG_EXPOSURE_TIME:
            try:
                meta.exposure_time_ms = float(to_str(val_bytes))
            except ValueError:
                pass
        elif tag == cls.TAG_ROWS:
            if len(val_bytes) >= 2:
                meta.rows = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == cls.TAG_COLUMNS:
            if len(val_bytes) >= 2:
                meta.columns = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == cls.TAG_BITS_ALLOCATED:
            if len(val_bytes) >= 2:
                meta.bits_allocated = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == cls.TAG_BITS_STORED:
            if len(val_bytes) >= 2:
                meta.bits_stored = struct.unpack("<H", val_bytes[:2])[0]
        elif tag == cls.TAG_PHOTOMETRIC:
            meta.photometric_interpretation = to_str(val_bytes).upper()
