"""Aliyun OSS storage provider implementation."""

import hashlib
from typing import AsyncIterator, Optional, Any
from datetime import datetime, timedelta
import anyio
from functools import partial
import io

from core.logging_config import get_logger
from ..base import StorageProvider, AdvancedStorageProvider
from ..config import StorageConfig
from ..models import UploadResult, StorageObject, StorageMetadata, PresignedRequest
from ..exceptions import (
    StorageError,
    NotFoundError,
    PermissionDeniedError,
    TransientError,
    ConfigurationError,
)

logger = get_logger(__name__)


class OSSProvider(AdvancedStorageProvider):
    """Aliyun OSS storage provider."""

    def __init__(self, bucket: Any, config: StorageConfig):  # oss2.Bucket
        """Initialize OSS provider.

        Args:
            bucket: OSS2 Bucket instance
            config: Storage configuration
        """
        self.bucket = bucket
        self.config = config

    async def upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadResult:
        """Upload file to OSS."""
        try:
            headers = {}
            if content_type:
                headers["Content-Type"] = content_type
            if metadata:
                for k, v in metadata.items():
                    headers[f"x-oss-meta-{k}"] = v

            # Upload using thread pool for sync SDK
            result = await anyio.to_thread.run_sync(
                partial(self.bucket.put_object, key, file, headers=headers if headers else None)
            )

            # Use server returned ETag if available; else fallback to local hash
            etag = getattr(result, "etag", None) or hashlib.md5(file).hexdigest()

            # Build result
            upload_result = UploadResult(
                key=key, etag=etag, size=len(file), content_type=content_type
            )

            # Attach only stable public URL when available (no temporary presigned here)
            if self.config.public_base_url:
                upload_result.url = f"{self.config.public_base_url}/{key}"
            # For private buckets, do not attach presigned URLs to result.url

            logger.info(f"Uploaded to OSS", key=key, size=len(file))
            return upload_result

        except Exception as e:
            self._handle_exception(e, f"upload {key}")

    async def download(self, key: str) -> bytes:
        """Download file from OSS."""
        try:
            result = await anyio.to_thread.run_sync(partial(self.bucket.get_object, key))
            try:
                data = await anyio.to_thread.run_sync(result.read)
                logger.info(f"Downloaded from OSS", key=key, size=len(data))
                return data
            finally:
                # Best-effort close of underlying result/stream
                try:
                    await anyio.to_thread.run_sync(result.close)  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception as e:
            self._handle_exception(e, f"download {key}")

    async def stream_download(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream download file from OSS."""
        try:
            # Get object with streaming
            result = await anyio.to_thread.run_sync(partial(self.bucket.get_object, key))

            try:
                # Stream chunks
                while True:
                    chunk = await anyio.to_thread.run_sync(partial(result.read, chunk_size))
                    if not chunk:
                        break
                    yield chunk
            finally:
                # Best-effort close of underlying stream/response
                try:
                    await anyio.to_thread.run_sync(result.close)  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception as e:
            self._handle_exception(e, f"stream download {key}")

    async def delete(self, key: str) -> bool:
        """Delete file from OSS."""
        try:
            await anyio.to_thread.run_sync(partial(self.bucket.delete_object, key))
            logger.info(f"Deleted from OSS", key=key)
            return True
        except Exception as e:
            self._handle_exception(e, f"delete {key}")

    async def exists(self, key: str) -> bool:
        """Check if file exists in OSS."""
        try:
            result = await anyio.to_thread.run_sync(partial(self.bucket.object_exists, key))
            return result
        except Exception as e:
            self._handle_exception(e, f"exists {key}")

    async def list_objects(self, prefix: str = "", limit: int = 1000) -> list[StorageObject]:
        """List objects in OSS."""
        try:
            import oss2

            def _collect(bucket, pref, lim):
                out = []
                for obj in oss2.ObjectIterator(bucket, prefix=pref):
                    out.append(
                        (
                            obj.key,
                            obj.size,
                            obj.etag,
                            obj.last_modified,
                            getattr(obj, "content_type", None),
                        )
                    )
                    if len(out) >= lim:
                        break
                return out

            entries = await anyio.to_thread.run_sync(_collect, self.bucket, prefix, limit)

            objects: list[StorageObject] = []
            for key, size, etag, last_modified, content_type in entries:
                objects.append(
                    StorageObject(
                        key=key,
                        size=size,
                        etag=etag.strip('"') if etag else None,
                        last_modified=(
                            datetime.fromtimestamp(last_modified) if last_modified else None
                        ),
                        content_type=content_type,
                    )
                )

            return objects

        except Exception as e:
            self._handle_exception(e, f"list objects {prefix}")

    async def _list_objects_iterator(self, prefix: str) -> AsyncIterator:
        """Deprecated internal iterator (kept for compatibility)."""
        import oss2

        objs = await anyio.to_thread.run_sync(
            lambda: list(oss2.ObjectIterator(self.bucket, prefix=prefix))
        )
        for obj in objs:
            yield obj

    async def get_metadata(self, key: str) -> StorageMetadata:
        """Get file metadata from OSS."""
        try:
            result = await anyio.to_thread.run_sync(partial(self.bucket.get_object_meta, key))

            headers = result.headers

            # Extract custom metadata
            custom_meta = {}
            for k, v in headers.items():
                if k.startswith("x-oss-meta-"):
                    custom_meta[k[11:]] = v

            return StorageMetadata(
                etag=headers.get("etag", "").strip('"'),
                content_type=headers.get("content-type"),
                size=int(headers.get("content-length", 0)),
                last_modified=(
                    datetime.strptime(headers.get("last-modified", ""), "%a, %d %b %Y %H:%M:%S %Z")
                    if headers.get("last-modified")
                    else None
                ),
                custom_metadata=custom_meta,
            )

        except Exception as e:
            self._handle_exception(e, f"get metadata {key}")

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ) -> PresignedRequest:
        """Generate presigned URL for OSS."""
        try:
            if method == "GET":
                # For GET, do NOT sign with headers like Content-Type: browsers won't send them.
                # OSS also may reject overriding content-type via response headers in some configs.
                # Only set response-content-disposition (inline/attachment + filename).
                params = {}
                if response_content_disposition:
                    params["response-content-disposition"] = response_content_disposition
                # Intentionally ignore response_content_type to avoid InvalidRequest
                url = await anyio.to_thread.run_sync(
                    partial(
                        self.bucket.sign_url,
                        "GET",
                        key,
                        expires_in,
                        params=params if params else None,
                    )
                )
                return PresignedRequest(url=url, method="GET", expires_in=expires_in)

            elif method == "PUT":
                headers = {"Content-Type": content_type or "application/octet-stream"}
                url = await anyio.to_thread.run_sync(
                    partial(
                        self.bucket.sign_url,
                        "PUT",
                        key,
                        expires_in,
                        headers=headers,
                    )
                )
                return PresignedRequest(
                    url=url,
                    method="PUT",
                    expires_in=expires_in,
                    headers=headers,
                )

            elif method == "POST":
                # OSS doesn't have native POST policy like S3
                # Fall back to PUT presigned URL
                return await self.generate_presigned_url(key, expires_in, "PUT", content_type)

            else:
                raise ValueError(f"Unsupported method: {method}")

        except Exception as e:
            self._handle_exception(e, f"generate presigned URL {key}")

    async def copy(self, source_key: str, dest_key: str) -> bool:
        """Copy file within OSS."""
        try:
            await anyio.to_thread.run_sync(
                partial(self.bucket.copy_object, self.bucket.bucket_name, source_key, dest_key)
            )
            logger.info(f"Copied in OSS", source=source_key, dest=dest_key)
            return True
        except Exception as e:
            self._handle_exception(e, f"copy {source_key} to {dest_key}")

    async def move(self, source_key: str, dest_key: str) -> bool:
        """Move file within OSS."""
        if await self.copy(source_key, dest_key):
            return await self.delete(source_key)
        return False

    def public_url(self, key: str) -> Optional[str]:
        """Get public/CDN URL for file."""
        if self.config.public_base_url:
            return f"{self.config.public_base_url}/{key}"
        else:
            # Use bucket's public endpoint
            endpoint_host = (
                (self.config.endpoint or "").replace("http://", "").replace("https://", "")
            )
            return f"https://{self.config.bucket}.{endpoint_host}/{key}"

    async def health_check(self) -> bool:
        """Check OSS connectivity."""
        try:
            # Try to get bucket info
            await anyio.to_thread.run_sync(self.bucket.get_bucket_info)
            logger.info("OSS health check passed")
            return True
        except Exception as e:
            logger.error(f"OSS health check failed", error=str(e))
            return False

    # Advanced methods
    async def multipart_upload_start(self, key: str, content_type: Optional[str] = None) -> str:
        """Start multipart upload."""
        try:
            headers = {}
            if content_type:
                headers["Content-Type"] = content_type

            upload_id = await anyio.to_thread.run_sync(
                partial(
                    self.bucket.init_multipart_upload, key, headers=headers if headers else None
                )
            )
            return upload_id.upload_id
        except Exception as e:
            self._handle_exception(e, f"start multipart upload {key}")

    async def multipart_upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> str:
        """Upload part in multipart upload."""
        try:
            from oss2.models import PartInfo

            result = await anyio.to_thread.run_sync(
                partial(
                    self.bucket.upload_part,
                    key,
                    upload_id,
                    part_number,
                    data,
                )
            )
            return result.etag
        except Exception as e:
            self._handle_exception(e, f"upload part {part_number}")

    async def multipart_upload_complete(
        self, upload_id: str, key: str, parts: list[dict]
    ) -> UploadResult:
        """Complete multipart upload."""
        try:
            from oss2.models import PartInfo

            # Convert parts to OSS PartInfo
            oss_parts = []
            for part in parts:
                oss_parts.append(PartInfo(part["PartNumber"], part["ETag"]))

            result = await anyio.to_thread.run_sync(
                partial(self.bucket.complete_multipart_upload, key, upload_id, oss_parts)
            )

            return UploadResult(
                key=key,
                etag=result.etag,
                size=0,  # Size would need to be tracked separately
                url=self.public_url(key) if self.config.public_base_url else None,
            )
        except Exception as e:
            self._handle_exception(e, f"complete multipart upload {key}")

    async def batch_upload(
        self, files: list[tuple[bytes, str]], metadata: Optional[dict] = None
    ) -> list[UploadResult]:
        """Batch upload multiple files."""
        results = []
        for data, key in files:
            result = await self.upload(data, key, metadata)
            results.append(result)
        return results

    async def batch_delete(self, keys: list[str]) -> dict[str, bool]:
        """Batch delete multiple files."""
        try:
            # OSS batch delete
            result = await anyio.to_thread.run_sync(partial(self.bucket.batch_delete_objects, keys))

            # All deleted keys are successful
            return {key: True for key in result.deleted_keys}

        except Exception as e:
            self._handle_exception(e, "batch delete")

    async def create_directory(self, path: str) -> bool:
        """Create directory in OSS (creates empty object with trailing slash)."""
        if not path.endswith("/"):
            path = f"{path}/"

        await self.upload(b"", path)
        return True

    async def delete_directory(self, path: str, recursive: bool = False) -> bool:
        """Delete directory from OSS."""
        if not path.endswith("/"):
            path = f"{path}/"

        if recursive:
            # List and delete all objects with prefix
            objects = await self.list_objects(prefix=path, limit=1000)
            keys = [obj.key for obj in objects]
            if keys:
                await self.batch_delete(keys)
        else:
            # Just delete the directory marker
            await self.delete(path)

        return True

    def _handle_exception(self, e: Exception, operation: str) -> None:
        """Map OSS exceptions to storage exceptions."""
        import oss2

        if isinstance(e, oss2.exceptions.NoSuchKey):
            raise NotFoundError(f"Object not found: {operation}")
        elif isinstance(e, oss2.exceptions.AccessDenied):
            raise PermissionDeniedError(f"Access denied: {operation}")
        elif isinstance(e, oss2.exceptions.RequestError):
            raise TransientError(f"Request error: {operation}: {e}")
        elif isinstance(e, oss2.exceptions.ServerError):
            if hasattr(e, "status") and e.status in [500, 502, 503]:
                raise TransientError(f"Server error: {operation}: {e}")
            else:
                raise StorageError(f"OSS server error: {operation}: {e}")
        else:
            raise StorageError(f"OSS error during {operation}: {e}") from e


async def build_oss_provider(config: StorageConfig) -> OSSProvider:
    """Build OSS storage provider.

    Args:
        config: Storage configuration

    Returns:
        Configured OSS provider instance
    """
    if not config.bucket:
        raise ConfigurationError("OSS bucket name is required")

    if not config.oss_access_key_id or not config.oss_access_key_secret:
        raise ConfigurationError("OSS access key ID and secret are required")

    if not config.endpoint:
        raise ConfigurationError("OSS endpoint is required")

    try:
        import oss2
    except ImportError:
        raise ConfigurationError("oss2 is required for OSS storage")

    # Create OSS auth
    auth = oss2.Auth(config.oss_access_key_id, config.oss_access_key_secret)

    # Create bucket instance
    bucket = oss2.Bucket(
        auth, config.endpoint, config.bucket, connect_timeout=config.timeout, enable_crc=True
    )

    # Create and return provider
    provider = OSSProvider(bucket, config)

    # Check connectivity
    if not await provider.health_check():
        raise ConfigurationError("Failed to connect to OSS")

    return provider
