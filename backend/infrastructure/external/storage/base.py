"""Storage provider protocol definitions."""

from typing import Protocol, AsyncIterator, Optional, runtime_checkable
from datetime import datetime

from .models import UploadResult, StorageObject, StorageMetadata, PresignedRequest


@runtime_checkable
class StorageProvider(Protocol):
    """Core storage provider protocol for duck typing."""

    async def upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadResult:
        """Upload file to storage."""
        ...

    async def download(self, key: str) -> bytes:
        """Download file from storage."""
        ...

    async def stream_download(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream download file from storage."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete file from storage."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if file exists in storage."""
        ...

    async def list_objects(self, prefix: str = "", limit: int = 1000) -> list[StorageObject]:
        """List objects in storage."""
        ...

    async def get_metadata(self, key: str) -> StorageMetadata:
        """Get file metadata."""
        ...

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ) -> PresignedRequest:
        """Generate presigned URL for direct access."""
        ...

    async def copy(self, source_key: str, dest_key: str) -> bool:
        """Copy file within storage."""
        ...

    async def move(self, source_key: str, dest_key: str) -> bool:
        """Move file within storage."""
        ...

    def public_url(self, key: str) -> Optional[str]:
        """Get public/CDN URL for file."""
        ...

    async def health_check(self) -> bool:
        """Check storage connectivity and permissions."""
        ...


@runtime_checkable
class AdvancedStorageProvider(StorageProvider, Protocol):
    """Advanced storage provider protocol with extended capabilities."""

    async def multipart_upload_start(self, key: str, content_type: Optional[str] = None) -> str:
        """Start multipart upload."""
        ...

    async def multipart_upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> str:
        """Upload part in multipart upload."""
        ...

    async def multipart_upload_complete(
        self, upload_id: str, key: str, parts: list[dict]
    ) -> UploadResult:
        """Complete multipart upload."""
        ...

    async def batch_upload(
        self, files: list[tuple[bytes, str]], metadata: Optional[dict] = None
    ) -> list[UploadResult]:
        """Batch upload multiple files."""
        ...

    async def batch_delete(self, keys: list[str]) -> dict[str, bool]:
        """Batch delete multiple files."""
        ...

    async def create_directory(self, path: str) -> bool:
        """Create directory in storage."""
        ...

    async def delete_directory(self, path: str, recursive: bool = False) -> bool:
        """Delete directory from storage."""
        ...
