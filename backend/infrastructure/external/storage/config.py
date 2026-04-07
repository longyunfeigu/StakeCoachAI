"""Storage configuration models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class StorageType(str, Enum):
    """Storage provider types."""

    S3 = "s3"
    OSS = "oss"
    LOCAL = "local"


class StorageConfig(BaseModel):
    """Storage configuration model."""

    # Common settings
    type: StorageType = StorageType.LOCAL
    bucket: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    public_base_url: Optional[str] = None  # Public/CDN domain

    # S3 specific
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_sse: Optional[str] = None  # Server-side encryption
    s3_acl: Optional[str] = "private"  # Access control list

    # OSS specific
    oss_access_key_id: Optional[str] = None
    oss_access_key_secret: Optional[str] = None

    # Local specific
    local_base_path: str = "/tmp/storage"

    # Advanced settings
    max_retry_attempts: int = 3
    timeout: int = 30
    enable_ssl: bool = True
    presign_max_size: int = 100 * 1024 * 1024  # 100MB
    presign_content_types: list[str] = Field(
        default_factory=lambda: [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "application/pdf",
            "video/mp4",
            "audio/mpeg",
        ]
    )

    model_config = ConfigDict(use_enum_values=True)
