"""Application-owned storage port abstraction (hexagonal architecture).

Defines the minimal methods needed by application use cases so that
the application layer does not depend on infrastructure details.
"""

from __future__ import annotations

from typing import AsyncIterator, Optional, Protocol, runtime_checkable
from dataclasses import dataclass, field


@dataclass
class PresignedURL:
    url: str
    method: str = "GET"
    expires_in: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ObjectMetadata:
    etag: Optional[str]
    content_type: Optional[str]
    size: int
    custom_metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class StorageInfo:
    type: str
    bucket: Optional[str]
    region: Optional[str]


@dataclass
class UploadOutcome:
    key: str
    etag: Optional[str]
    size: int
    content_type: Optional[str] = None
    url: Optional[str] = None


@runtime_checkable
class StoragePort(Protocol):
    def info(self) -> StorageInfo: ...

    async def delete(self, key: str) -> bool: ...

    async def get_metadata(self, key: str) -> ObjectMetadata: ...

    async def upload(
        self,
        data: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadOutcome: ...

    async def upload_stream(
        self,
        stream: AsyncIterator[bytes],
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadOutcome: ...

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ) -> PresignedURL: ...

    def public_url(self, key: str) -> Optional[str]: ...
