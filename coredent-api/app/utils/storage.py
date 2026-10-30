"""
CoreDent Storage Utility
Abstracts local filesystem and S3 for HIPAA-compliant image storage.
"""

import os
import boto3
import logging
from botocore.exceptions import ClientError
from pathlib import Path
from app.core.config_simple import settings

logger = logging.getLogger(__name__)

class StorageStrategy:
    def upload(self, content: bytes, destination: str, mime_type: str) -> str:
        raise NotImplementedError

    def get_url(self, path: str, expires_in: int = 3600) -> str:
        raise NotImplementedError

    def delete(self, path: str) -> bool:
        raise NotImplementedError

    def save(self, content: bytes, destination: str, mime_type: str = "application/octet-stream") -> str:
        return self.upload(content, destination, mime_type)

class LocalStorageStrategy(StorageStrategy):
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload(self, content: bytes, destination: str, mime_type: str) -> str:
        full_path = self.base_dir / destination
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return str(full_path)

    def get_url(self, path: str, expires_in: int = 3600) -> str:
        # In development, we return a local path that the backend serves
        # For production-grade local storage, we'd use a proxy or symlink
        return path

    def delete(self, path: str) -> bool:
        try:
            if os.path.exists(path):
                os.remove(path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete local file {path}: {e}")
        return False

class S3StorageStrategy(StorageStrategy):
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket = settings.AWS_S3_BUCKET

    def upload(self, content: bytes, destination: str, mime_type: str) -> str:
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=destination,
                Body=content,
                ContentType=mime_type,
                ServerSideEncryption='AES256'  # HIPAA: Encryption at rest
            )
            return destination
        except ClientError as e:
            logger.error(f"S3 Upload Error: {e}")
            raise

    def get_url(self, path: str, expires_in: int = 300) -> str:
        try:
            # HIPAA: Short-lived presigned URLs (default 5 minutes)
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': path},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"S3 Presigned URL Error: {e}")
            return ""

    def delete(self, path: str) -> bool:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError as e:
            logger.error(f"S3 Delete Error: {e}")
            return False

# Factory: Choose strategy based on environment
def get_storage() -> StorageStrategy:
    from app.core.config_simple import _LOCAL_ENVIRONMENTS
    if settings.ENVIRONMENT not in _LOCAL_ENVIRONMENTS and settings.AWS_S3_BUCKET:
        return S3StorageStrategy()
    return LocalStorageStrategy()

storage = get_storage()
