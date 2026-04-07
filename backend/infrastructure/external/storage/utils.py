"""Storage utility functions and middleware support."""

import hashlib
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, AsyncIterator, Callable
from functools import wraps
import time

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.logging_config import get_logger
from .base import StorageProvider
from .exceptions import TransientError, ValidationError
from .models import UploadResult

logger = get_logger(__name__)


# Key generation utilities
def key_builder(
    kind: str, user_id: Optional[str] = None, ext: Optional[str] = None, prefix_date: bool = True
) -> str:
    """Build storage key with organized structure.

    Args:
        kind: Type of content (avatar, document, video, etc.)
        user_id: Optional user identifier
        ext: File extension
        prefix_date: Whether to prefix with date path

    Returns:
        Structured storage key

    Example:
        key_builder("avatar", "123", "jpg") -> "2024/01/15/avatar/123/uuid.jpg"
    """
    parts = []

    # Add date prefix for organization
    if prefix_date:
        now = datetime.utcnow()
        parts.extend([str(now.year), f"{now.month:02d}", f"{now.day:02d}"])

    # Add kind
    parts.append(kind)

    # Add user path if provided
    if user_id:
        parts.append(str(user_id))

    # Generate unique filename
    filename = str(uuid.uuid4())
    if ext:
        if not ext.startswith("."):
            ext = f".{ext}"
        filename += ext

    parts.append(filename)

    return "/".join(parts)


def guess_content_type(filename: str) -> str:
    """Guess content type from filename.

    Args:
        filename: File name or path

    Returns:
        MIME type string
    """
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


def safe_join(base: str, relative: str) -> str:
    """Safely join paths preventing traversal attacks.

    Args:
        base: Base path
        relative: Relative path to join

    Returns:
        Safe joined path

    Raises:
        ValidationError: If path would escape base
    """
    # Clean the relative path
    clean = relative.lstrip("/")

    # Build and resolve path
    base_path = Path(base).resolve()
    full_path = (base_path / clean).resolve()

    # Ensure result is within base using relative_to guard
    try:
        full_path.relative_to(base_path)
    except Exception:
        raise ValidationError(f"Path escapes base directory: {relative}")

    return str(full_path)


def calculate_etag(data: bytes, algorithm: str = "md5") -> str:
    """Calculate ETag for data.

    Args:
        data: Data to hash
        algorithm: Hash algorithm (md5, sha256)

    Returns:
        Hex digest string
    """
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    hasher.update(data)
    return hasher.hexdigest()


async def calculate_etag_stream(stream: AsyncIterator[bytes], algorithm: str = "md5") -> str:
    """Calculate ETag for streamed data.

    Args:
        stream: Async iterator of data chunks
        algorithm: Hash algorithm

    Returns:
        Hex digest string
    """
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    async for chunk in stream:
        hasher.update(chunk)

    return hasher.hexdigest()


# Retry decorator for transient errors
def with_retry(max_attempts: int = 3, wait_multiplier: int = 1, wait_max: int = 10):
    """Decorator to retry operations on transient errors.

    Args:
        max_attempts: Maximum number of attempts
        wait_multiplier: Exponential backoff multiplier
        wait_max: Maximum wait time between retries
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_multiplier, max=wait_max),
        retry=retry_if_exception_type(TransientError),
        reraise=True,
    )


# Middleware support
class StorageMiddleware:
    """Base class for storage middleware."""

    async def before_upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> tuple[bytes, str, Optional[dict], Optional[str]]:
        """Process before upload.

        Returns:
            Potentially modified (file, key, metadata, content_type)
        """
        return file, key, metadata, content_type

    async def after_upload(self, result: UploadResult, file: bytes, key: str) -> UploadResult:
        """Process after successful upload.

        Returns:
            Potentially modified result
        """
        return result

    async def on_error(self, error: Exception, operation: str, **kwargs) -> None:
        """Handle errors during operations."""
        pass


class LoggingMiddleware(StorageMiddleware):
    """Middleware for structured logging of storage operations."""

    async def before_upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> tuple[bytes, str, Optional[dict], Optional[str]]:
        """Log before upload."""
        logger.info("Storage upload starting", key=key, size=len(file), content_type=content_type)
        return file, key, metadata, content_type

    async def after_upload(self, result: UploadResult, file: bytes, key: str) -> UploadResult:
        """Log after successful upload."""
        logger.info(
            "Storage upload completed", key=key, size=result.size, etag=result.etag, url=result.url
        )
        return result

    async def on_error(self, error: Exception, operation: str, **kwargs) -> None:
        """Log storage errors."""
        logger.error(f"Storage operation failed", operation=operation, error=str(error), **kwargs)


class ValidationMiddleware(StorageMiddleware):
    """Middleware for validating uploads."""

    def __init__(
        self, max_size: int = 100 * 1024 * 1024, allowed_types: Optional[list[str]] = None  # 100MB
    ):
        """Initialize validation middleware.

        Args:
            max_size: Maximum file size in bytes
            allowed_types: Allowed MIME types
        """
        self.max_size = max_size
        self.allowed_types = allowed_types

    async def before_upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> tuple[bytes, str, Optional[dict], Optional[str]]:
        """Validate before upload."""
        # Check size
        if len(file) > self.max_size:
            raise ValidationError(f"File too large: {len(file)} > {self.max_size}")

        # Check content type
        if self.allowed_types and content_type:
            if content_type not in self.allowed_types:
                raise ValidationError(f"Content type not allowed: {content_type}")

        return file, key, metadata, content_type


class MetricsMiddleware(StorageMiddleware):
    """Middleware for collecting metrics."""

    def __init__(self):
        """Initialize metrics middleware."""
        self.upload_times = []
        self.upload_sizes = []
        self.error_count = 0

    async def after_upload(self, result: UploadResult, file: bytes, key: str) -> UploadResult:
        """Collect upload metrics."""
        self.upload_sizes.append(result.size)
        return result

    async def on_error(self, error: Exception, operation: str, **kwargs) -> None:
        """Count errors."""
        self.error_count += 1


class MiddlewareStorage(StorageProvider):
    """Storage provider wrapper with middleware support."""

    def __init__(self, provider: StorageProvider, middlewares: list[StorageMiddleware]):
        """Initialize middleware storage.

        Args:
            provider: Underlying storage provider
            middlewares: List of middleware to apply
        """
        self.provider = provider
        self.middlewares = middlewares

    async def upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadResult:
        """Upload with middleware processing."""
        # Process before middleware
        for middleware in self.middlewares:
            try:
                file, key, metadata, content_type = await middleware.before_upload(
                    file, key, metadata, content_type
                )
            except Exception as e:
                for mw in self.middlewares:
                    await mw.on_error(e, "before_upload", key=key)
                raise

        # Perform upload
        try:
            start_time = time.time()
            result = await self.provider.upload(file, key, metadata, content_type)
            elapsed_ms = (time.time() - start_time) * 1000

            # Log performance
            logger.info(
                "Storage upload performance",
                key=key,
                elapsed_ms=f"{elapsed_ms:.2f}",
                size=len(file),
            )

        except Exception as e:
            for middleware in self.middlewares:
                await middleware.on_error(e, "upload", key=key)
            raise

        # Process after middleware
        for middleware in self.middlewares:
            try:
                result = await middleware.after_upload(result, file, key)
            except Exception as e:
                for mw in self.middlewares:
                    await mw.on_error(e, "after_upload", key=key)
                raise

        return result

    # Delegate other methods to underlying provider
    async def download(self, key: str) -> bytes:
        """Download from storage."""
        return await self.provider.download(key)

    async def stream_download(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream download from storage."""
        async for chunk in self.provider.stream_download(key, chunk_size):
            yield chunk

    async def delete(self, key: str) -> bool:
        """Delete from storage."""
        return await self.provider.delete(key)

    async def exists(self, key: str) -> bool:
        """Check existence."""
        return await self.provider.exists(key)

    async def list_objects(self, prefix: str = "", limit: int = 1000):
        """List objects."""
        return await self.provider.list_objects(prefix, limit)

    async def get_metadata(self, key: str):
        """Get metadata."""
        return await self.provider.get_metadata(key)

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ):
        """Generate presigned URL."""
        return await self.provider.generate_presigned_url(
            key,
            expires_in,
            method,
            content_type,
            response_content_disposition=response_content_disposition,
            response_content_type=response_content_type,
        )

    async def copy(self, source_key: str, dest_key: str) -> bool:
        """Copy file."""
        return await self.provider.copy(source_key, dest_key)

    async def move(self, source_key: str, dest_key: str) -> bool:
        """Move file."""
        return await self.provider.move(source_key, dest_key)

    def public_url(self, key: str) -> Optional[str]:
        """Get public URL."""
        return self.provider.public_url(key)

    async def health_check(self) -> bool:
        """Check health."""
        return await self.provider.health_check()


def apply_middleware(
    provider: StorageProvider, middlewares: list[StorageMiddleware]
) -> StorageProvider:
    """Apply middleware to a storage provider.

    Args:
        provider: Base storage provider
        middlewares: List of middleware to apply

    Returns:
        Provider wrapped with middleware
    """
    if not middlewares:
        return provider

    return MiddlewareStorage(provider, middlewares)
