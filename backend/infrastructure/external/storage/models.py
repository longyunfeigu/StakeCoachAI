"""Storage data transfer objects."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class StorageObject(BaseModel):
    """Storage object metadata."""

    key: str
    size: int
    etag: Optional[str] = None
    last_modified: Optional[datetime] = None
    content_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UploadResult(BaseModel):
    """Upload operation result."""

    key: str
    etag: Optional[str] = None
    size: int
    content_type: Optional[str] = None
    url: Optional[str] = None  # Public/CDN URL if available


class StorageMetadata(BaseModel):
    """File metadata in storage."""

    etag: Optional[str] = None
    content_type: Optional[str] = None
    size: int
    last_modified: Optional[datetime] = None
    custom_metadata: dict[str, str] = Field(default_factory=dict)


class PresignedRequest(BaseModel):
    """Presigned request for direct access."""

    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    expires_in: int
    fields: dict[str, str] = Field(default_factory=dict)  # For S3 POST
