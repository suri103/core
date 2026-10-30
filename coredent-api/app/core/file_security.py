"""
File Upload Security Module
Comprehensive security checks for file uploads
"""

try:
    import magic
except (ImportError, Exception):
    magic = None
import hashlib
import uuid
import re
import logging
import os
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Magic number signatures for allowed file types
ALLOWED_MIME_TYPES = {
    # Images
    'image/jpeg': [b'\xFF\xD8\xFF'],
    'image/png': [b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'],
    'image/gif': [b'GIF87a', b'GIF89a'],
    'image/webp': [b'RIFF', b'WEBP'],
    'image/bmp': [b'BM'],
    'image/tiff': [b'II*\x00', b'MM\x00*'],
    'image/x-tiff': [b'II*\x00', b'MM\x00*'],

    # Documents
    'application/pdf': [b'%PDF-'],
    'application/msword': [b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'],  # DOC
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': [
        b'PK\x03\x04'  # DOCX (ZIP-based)
    ],
    'text/plain': [],  # Text files don't have magic numbers

    # Archives (for batch uploads)
    'application/zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],

    # Medical / Dental Imaging
    'application/dicom': [b'DICM'],
    'application/x-dicom': [b'DICM'],
}

# File size limits (in bytes)
FILE_SIZE_LIMITS = {
    'image/jpeg': 10 * 1024 * 1024,  # 10MB
    'image/png': 10 * 1024 * 1024,   # 10MB
    'image/gif': 5 * 1024 * 1024,    # 5MB
    'image/webp': 10 * 1024 * 1024,  # 10MB
    'image/bmp': 10 * 1024 * 1024,   # 10MB
    'image/tiff': 20 * 1024 * 1024,  # 20MB
    'image/x-tiff': 20 * 1024 * 1024,  # 20MB
    'application/pdf': 20 * 1024 * 1024,  # 20MB
    'application/msword': 10 * 1024 * 1024,  # 10MB
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 10 * 1024 * 1024,  # 10MB
    'text/plain': 1 * 1024 * 1024,  # 1MB
    'application/zip': 50 * 1024 * 1024,  # 50MB
    'application/dicom': 50 * 1024 * 1024,  # 50MB
    'application/x-dicom': 50 * 1024 * 1024,  # 50MB
}

# Default max size
DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10MB


class FileSecurityError(Exception):
    """Raised when file security validation fails"""
    pass


def validate_file_extension(filename: str, allowed_extensions: list = None) -> bool:
    """
    Validate file extension
    
    Args:
        filename: Original filename
        allowed_extensions: List of allowed extensions (e.g., ['jpg', 'png'])
        
    Returns:
        True if extension is allowed
        
    Raises:
        FileSecurityError: If extension is not allowed
    """
    if allowed_extensions is None:
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx', 'txt']

    # Extract extension
    ext = Path(filename).suffix.lower().lstrip('.')

    if not ext:
        raise FileSecurityError("File has no extension")

    if ext not in allowed_extensions:
        raise FileSecurityError(f"File extension '{ext}' is not allowed")

    return True


def validate_magic_number(file_content: bytes, expected_mime_type: str) -> bool:
    """
    Validate file magic number (file signature)
    
    This prevents attackers from uploading malicious files with fake extensions.
    
    Args:
        file_content: Binary content of the file
        expected_mime_type: Expected MIME type based on extension
        
    Returns:
        True if magic number matches expected type
        
    Raises:
        FileSecurityError: If magic number doesn't match
    """
    if expected_mime_type not in ALLOWED_MIME_TYPES:
        raise FileSecurityError(f"MIME type '{expected_mime_type}' is not allowed")

    # Get expected magic numbers
    magic_numbers = ALLOWED_MIME_TYPES[expected_mime_type]

    # Text files don't have magic numbers
    if not magic_numbers:
        return True

    # WebP is a RIFF container; a bare ``RIFF`` prefix (also used by WAV/AVI)
    # is not sufficient proof. Require the ``WEBP`` fourcc at offset 8.
    if expected_mime_type == 'image/webp':
        if file_content.startswith(b'RIFF') and file_content[8:12] == b'WEBP':
            return True
        raise FileSecurityError(
            "File content does not match expected type 'image/webp'. "
            "Possible file type mismatch or malicious upload attempt."
        )

    # DICOM Part 10 files contain a 128-byte preamble followed by 'DICM'
    if expected_mime_type in ('application/dicom', 'application/x-dicom'):
        if len(file_content) >= 132 and file_content[128:132] == b'DICM':
            return True
        raise FileSecurityError(
            "File content does not match expected type 'application/dicom'. "
            "Missing standard DICOM Part 10 header at offset 128."
        )

    # Check if file starts with any of the expected magic numbers
    for magic_num in magic_numbers:
        if file_content.startswith(magic_num):
            return True

    raise FileSecurityError(
        f"File content does not match expected type '{expected_mime_type}'. "
        "Possible file type mismatch or malicious upload attempt."
    )


def validate_file_size(file_content: bytes, mime_type: str) -> bool:
    """
    Validate file size is within limits
    
    Args:
        file_content: Binary content of the file
        mime_type: MIME type of the file
        
    Returns:
        True if size is within limits
        
    Raises:
        FileSecurityError: If file is too large
    """
    file_size = len(file_content)
    max_size = FILE_SIZE_LIMITS.get(mime_type, DEFAULT_MAX_SIZE)

    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise FileSecurityError(
            f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
        )

    if file_size == 0:
        raise FileSecurityError("File is empty")

    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path components (prevent directory traversal)
    filename = Path(filename).name

    # Remove or replace dangerous characters
    # Allow only alphanumeric, dash, underscore, dot
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Prevent multiple dots (can bypass extension checks)
    filename = re.sub(r'\.+', '.', filename)

    # Prevent leading/trailing dots or dashes
    filename = filename.strip('.-')

    # Limit filename length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')

    return filename


def generate_secure_filename(original_filename: str) -> str:
    """
    Generate a secure random filename while preserving extension
    
    Args:
        original_filename: Original filename
        
    Returns:
        Secure random filename with original extension
    """
    # Extract extension
    ext = Path(original_filename).suffix.lower()

    # Generate UUID-based filename
    secure_name = f"{uuid.uuid4().hex}{ext}"

    return secure_name


def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate SHA-256 hash of file content
    
    Useful for:
    - Duplicate detection
    - Integrity verification
    - Malware signature matching
    
    Args:
        file_content: Binary content of the file
        
    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(file_content).hexdigest()


def detect_mime_type(file_content: bytes, filename: str) -> str:
    """
    Detect MIME type using python-magic (libmagic)
    
    More reliable than trusting client-provided Content-Type header.
    
    Args:
        file_content: Binary content of the file
        filename: Original filename (for fallback)
        
    Returns:
        Detected MIME type
    """
    if magic is not None:
        try:
            # Use python-magic to detect MIME type
            mime = magic.Magic(mime=True)
            detected_type = mime.from_buffer(file_content)
            if isinstance(detected_type, str) and "/" in detected_type:
                return detected_type
            raise ValueError(f"Invalid detected mime type: {detected_type}")
        except Exception as e:
            logger.warning(f"Failed to detect MIME type with magic: {e}")

    # Fallback to extension-based detection
    ext = Path(filename).suffix.lower()
    extension_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.zip': 'application/zip',
    }
    return extension_map.get(ext, 'application/octet-stream')


def validate_file_upload(
    file_content: bytes,
    filename: str,
    allowed_extensions: list = None,
    max_size: int = None
) -> Dict[str, Any]:
    """
    Comprehensive file upload validation
    
    Performs all security checks:
    1. Extension validation
    2. File size validation
    3. MIME type detection
    4. Magic number validation
    5. Filename sanitization
    6. Hash calculation
    
    Args:
        file_content: Binary content of the file
        filename: Original filename
        allowed_extensions: List of allowed extensions
        max_size: Maximum file size in bytes (overrides default)
        
    Returns:
        Dictionary with validation results and metadata
        
    Raises:
        FileSecurityError: If any validation fails
    """
    try:
        # 1. Validate extension
        validate_file_extension(filename, allowed_extensions)

        # 2. Detect MIME type
        detected_mime = detect_mime_type(file_content, filename)

        # 3. Validate magic number
        validate_magic_number(file_content, detected_mime)

        # 4. Validate file size
        if max_size:
            if len(file_content) > max_size:
                raise FileSecurityError(f"File size exceeds maximum allowed size ({max_size} bytes)")
        else:
            validate_file_size(file_content, detected_mime)

        # 5. Sanitize filename
        safe_filename = sanitize_filename(filename)

        # 6. Generate secure filename
        secure_filename = generate_secure_filename(filename)

        # 7. Calculate file hash
        file_hash = calculate_file_hash(file_content)

        logger.info(
            f"File validation successful: {filename} -> {secure_filename}",
            extra={
                "original_filename": filename,
                "secure_filename": secure_filename,
                "mime_type": detected_mime,
                "size": len(file_content),
                "hash": file_hash[:16] + "..."
            }
        )

        return {
            "valid": True,
            "original_filename": filename,
            "safe_filename": safe_filename,
            "secure_filename": secure_filename,
            "mime_type": detected_mime,
            "size": len(file_content),
            "hash": file_hash,
        }

    except FileSecurityError as e:
        logger.warning(
            f"File validation failed: {filename}",
            extra={"original_filename": filename, "error": str(e)},
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during file validation: {e}",
            extra={"original_filename": filename},
        )
        raise FileSecurityError(f"File validation error: {str(e)}")


class VirusScanResult:
    """Result of virus scanning operation"""
    def __init__(
        self,
        is_clean: bool,
        scanner: str,
        threats_found: Optional[List[str]] = None,
        scan_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.is_clean = is_clean
        self.scanner = scanner
        self.threats_found = threats_found or []
        self.scan_id = scan_id
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_clean": self.is_clean,
            "scanner": self.scanner,
            "threats_found": self.threats_found,
            "scan_id": self.scan_id,
            "error": self.error
        }


_LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "test", "testing", "local"})


def _is_production_like() -> bool:
    """True for any real deployment environment (production, staging, uat, preview)."""
    return os.getenv("ENVIRONMENT", "development").strip().lower() not in _LOCAL_ENVIRONMENTS


async def read_stream_with_size_limit(
    file: Any,
    max_size: int,
    chunk_size: int = 64 * 1024,
) -> bytes:
    """Read an UploadFile stream up to max_size bytes.

    Aborts immediately if the stream exceeds max_size bytes before buffering.
    """
    total = 0
    chunks = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise FileSecurityError(
                f"File too large. Maximum size is {max_size / 1024 / 1024:.1f}MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


class VirusScanner:
    """
    Multi-provider virus scanning service
    
    Supports:
    - ClamAV (local, fast, preferred)
    - VirusTotal API (cloud, comprehensive)
    """

    def __init__(self):
        self._clamav_available = False
        self._clamd = None
        self._init_clamav()

    def _init_clamav(self) -> None:
        """Initialize ClamAV connection if available"""
        try:
            import clamd
            clamav_host = os.getenv("CLAMAV_HOST")
            timeout = float(os.getenv("CLAMAV_TIMEOUT", "10.0"))
            if clamav_host:
                self._clamd = clamd.ClamdNetworkSocket(
                    host=clamav_host,
                    port=int(os.getenv("CLAMAV_PORT", "3310")),
                    timeout=timeout,
                )
            else:
                self._clamd = clamd.ClamdUnixSocket(timeout=timeout)
            self._clamd.ping()
            self._clamav_available = True
            logger.info("ClamAV virus scanner initialized successfully")
        except ImportError:
            logger.warning("python-clamd not installed. Install with: pip install python-clamd")
        except Exception as e:
            logger.warning(f"ClamAV not available: {e}")

    async def scan_file(
        self,
        file_content: bytes,
        filename: str,
        enable_virustotal: Optional[bool] = None,
    ) -> VirusScanResult:
        """
        Scan file for viruses using available providers
        
        Args:
            file_content: Binary content of the file
            filename: Original filename for logging
            enable_virustotal: Whether to use VirusTotal (default False unless VIRUSTOTAL_ENABLED=true)
            
        Returns:
            VirusScanResult with scan status and details
        """
        if enable_virustotal is None:
            enable_virustotal = os.getenv("VIRUSTOTAL_ENABLED", "false").strip().lower() in ("true", "1", "yes")

        scan_results: List[Dict[str, Any]] = []

        if self._clamav_available and self._clamd:
            result = await self._scan_with_clamav(file_content, filename)
            scan_results.append(result.to_dict())
            # Return immediately on a clean scan OR a confirmed threat.
            # Only fall through to VirusTotal when ClamAV errored — otherwise
            # a VT error path (which fails open) could override a detection.
            if result.is_clean or not result.error:
                return result

        if enable_virustotal:
            result = await self._scan_with_virustotal(file_content, filename)
            scan_results.append(result.to_dict())
            return result

        is_production = _is_production_like()
        logger.warning(
            f"No virus scanners available: {filename}",
            extra={"original_filename": filename, "results": scan_results}
        )
        return VirusScanResult(
            is_clean=not is_production,
            scanner="none",
            error="No scanners available"
        )

    async def _scan_with_clamav(
        self,
        file_content: bytes,
        filename: str
    ) -> VirusScanResult:
        """Scan file using ClamAV via clamd socket"""
        try:
            import asyncio
            result = await asyncio.to_thread(self._clamd.scan_stream, file_content)

            if result:
                for threat_name, threat_status in result.items():
                    if threat_status == "FOUND":
                        logger.warning(
                            f"Virus detected by ClamAV: {threat_name}",
                            extra={"original_filename": filename, "threat": threat_name}
                        )
                        return VirusScanResult(
                            is_clean=False,
                            scanner="clamav",
                            threats_found=[f"{threat_name}: {threat_status}"]
                        )

            return VirusScanResult(is_clean=True, scanner="clamav")

        except Exception as e:
            logger.error(f"ClamAV scan failed: {e}")
            is_production = _is_production_like()
            # Fail closed in production: an errored scan must not pass files.
            return VirusScanResult(
                is_clean=not is_production,
                scanner="clamav",
                error=str(e)
            )

    async def _scan_with_virustotal(
        self,
        file_content: bytes,
        filename: str
    ) -> VirusScanResult:
        """Scan file using VirusTotal API"""
        from app.core.config_simple import settings

        api_key = getattr(settings, 'VIRUSTOTAL_API_KEY', None) or os.getenv('VIRUSTOTAL_API_KEY')

        is_production = _is_production_like()

        if not api_key:
            return VirusScanResult(
                is_clean=not is_production,
                scanner="virustotal",
                error="VirusTotal API key not configured"
            )

        try:
            import requests
            from requests_toolbelt import MultipartEncoder

            encoder = MultipartEncoder(
                fields={
                    'file': (filename, file_content, 'application/octet-stream')
                }
            )

            response = requests.post(
                'https://www.virustotal.com/api/v3/files',
                headers={
                    'x-apikey': api_key,
                    'Content-Type': encoder.content_type
                },
                data=encoder,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                scan_id = data.get('data', {}).get('id')

                stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                malicious_count = stats.get('malicious', 0)
                suspicious_count = stats.get('suspicious', 0)

                if malicious_count > 0 or suspicious_count > 0:
                    threats = []
                    results = data.get('data', {}).get('attributes', {}).get('last_analysis_results', {})
                    for engine, result in results.items():
                        if result.get('category') in ['malicious', 'suspicious']:
                            threats.append(f"{engine}: {result.get('result')}")

                    logger.warning(
                        f"Threats detected by VirusTotal: {malicious_count + suspicious_count}",
                        extra={"original_filename": filename, "threats": threats[:10]}
                    )

                    return VirusScanResult(
                        is_clean=False,
                        scanner="virustotal",
                        threats_found=threats,
                        scan_id=scan_id
                    )

                return VirusScanResult(
                    is_clean=True,
                    scanner="virustotal",
                    scan_id=scan_id
                )

            elif response.status_code == 429:
                logger.warning("VirusTotal rate limit exceeded")
                return VirusScanResult(
                    is_clean=not is_production,
                    scanner="virustotal",
                    error="Rate limited"
                )
            else:
                return VirusScanResult(
                    is_clean=not is_production,
                    scanner="virustotal",
                    error=f"API returned {response.status_code}"
                )

        except ImportError:
            logger.warning("requests or requests_toolbelt not installed")
            return VirusScanResult(
                is_clean=not is_production,
                scanner="virustotal",
                error="Dependencies not installed"
            )
        except Exception as e:
            logger.error(f"VirusTotal scan failed: {e}")
            return VirusScanResult(
                is_clean=not is_production,
                scanner="virustotal",
                error=str(e)
            )


_virus_scanner: Optional[VirusScanner] = None


def get_virus_scanner() -> VirusScanner:
    """Get singleton virus scanner instance"""
    global _virus_scanner
    if _virus_scanner is None:
        _virus_scanner = VirusScanner()
    return _virus_scanner


async def scan_file_for_viruses(
    file_content: bytes,
    filename: str,
    enable_virustotal: Optional[bool] = None,
) -> VirusScanResult:
    """
    Scan file for viruses using available providers
    
    Args:
        file_content: Binary content of the file
        filename: Original filename
        enable_virustotal: Whether to use VirusTotal (default False unless VIRUSTOTAL_ENABLED=true)
        
    Returns:
        VirusScanResult indicating if file is clean or infected
    """
    scanner = get_virus_scanner()
    return await scanner.scan_file(file_content, filename, enable_virustotal)


async def scan_and_validate_file(
    file_content: bytes,
    filename: str,
    allowed_extensions: list = None,
    max_size: int = None,
    enable_virustotal: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Complete file validation including virus scanning
    
    Performs:
    1. Extension validation
    2. File size validation
    3. MIME type detection
    4. Magic number validation
    5. Filename sanitization
    6. Hash calculation
    7. Virus scanning
    
    Args:
        file_content: Binary content of the file
        filename: Original filename
        allowed_extensions: List of allowed extensions
        max_size: Maximum file size override
        enable_virustotal: Override VirusTotal flag
        
    Returns:
        Dictionary with validation results including virus scan
        
    Raises:
        FileSecurityError: If validation fails
    """
    validation_result = validate_file_upload(
        file_content, filename, allowed_extensions, max_size
    )

    try:
        scan_result = await scan_file_for_viruses(
            file_content, filename, enable_virustotal=enable_virustotal
        )
        validation_result["virus_scan"] = scan_result.to_dict()

        if not scan_result.is_clean:
            raise FileSecurityError(
                f"File rejected: virus detected - {scan_result.threats_found}"
            )
    except FileSecurityError:
        raise
    except Exception as e:
        logger.error(f"Virus scan error: {e}")
        # Fail closed in production-like environments: an errored/unavailable
        # scanner must not silently pass a file through.
        is_production = _is_production_like()
        if is_production:
            raise FileSecurityError(
                f"File rejected: virus scan could not be completed ({e})"
            )
        validation_result["virus_scan"] = {
            "is_clean": False,
            "scanner": "unknown",
            "error": str(e)
        }

    return validation_result
