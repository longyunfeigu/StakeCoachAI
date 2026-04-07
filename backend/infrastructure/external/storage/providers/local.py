"""Local file system storage provider implementation."""

import hashlib
import shutil
from pathlib import Path
from typing import AsyncIterator, Optional
from datetime import datetime
import mimetypes
import aiofiles
import aiofiles.os

from core.logging_config import get_logger
from ..base import StorageProvider, AdvancedStorageProvider
from ..config import StorageConfig
from ..models import UploadResult, StorageObject, StorageMetadata, PresignedRequest
from ..exceptions import StorageError, NotFoundError, PermissionDeniedError, ValidationError

logger = get_logger(__name__)


class LocalProvider(AdvancedStorageProvider):
    """Local file system storage provider."""

    def __init__(self, config: StorageConfig):
        """Initialize local storage provider.

        Args:
            config: Storage configuration
        """
        self.config = config
        self.base_path = Path(config.local_base_path).resolve()

        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadResult:
        """Upload file to local storage."""
        try:
            # Validate and build safe path
            file_path = self._safe_path(key)

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file)

            # Store metadata if provided
            if metadata or content_type:
                await self._save_metadata(file_path, metadata, content_type)

            # Calculate ETag
            etag = hashlib.md5(file).hexdigest()

            # Build result
            result = UploadResult(
                key=key,
                etag=etag,
                size=len(file),
                content_type=content_type or self._guess_content_type(key),
            )

            # Add public URL if configured
            if self.config.public_base_url:
                result.url = f"{self.config.public_base_url}/{key}"

            logger.info(f"Uploaded to local storage", key=key, size=len(file))
            return result

        except Exception as e:
            raise StorageError(f"Failed to upload {key}: {e}") from e

    async def download(self, key: str) -> bytes:
        """Download file from local storage."""
        try:
            file_path = self._safe_path(key)

            if not file_path.exists():
                raise NotFoundError(f"File not found: {key}")

            async with aiofiles.open(file_path, "rb") as f:
                data = await f.read()

            logger.info(f"Downloaded from local storage", key=key, size=len(data))
            return data

        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to download {key}: {e}") from e

    async def stream_download(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream download file from local storage."""
        try:
            file_path = self._safe_path(key)

            if not file_path.exists():
                raise NotFoundError(f"File not found: {key}")

            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to stream download {key}: {e}") from e

    async def delete(self, key: str) -> bool:
        """Delete file from local storage."""
        try:
            file_path = self._safe_path(key)

            if file_path.exists():
                await aiofiles.os.remove(file_path)

                # Also remove metadata file if exists
                meta_path = self._metadata_path(file_path)
                if meta_path.exists():
                    await aiofiles.os.remove(meta_path)

                logger.info(f"Deleted from local storage", key=key)
                return True

            return False

        except Exception as e:
            raise StorageError(f"Failed to delete {key}: {e}") from e

    async def exists(self, key: str) -> bool:
        """Check if file exists in local storage."""
        try:
            file_path = self._safe_path(key)
            return file_path.exists() and file_path.is_file()
        except:
            return False

    async def list_objects(self, prefix: str = "", limit: int = 1000) -> list[StorageObject]:
        """List objects in local storage."""
        try:
            objects: list[StorageObject] = []
            count = 0

            # Clean prefix for comparison
            clean_prefix = prefix.lstrip("/") if prefix else ""

            # Fast path: exact file
            if clean_prefix:
                candidate = self._safe_path(clean_prefix)
                if candidate.exists() and candidate.is_file():
                    stat = candidate.stat()
                    meta = await self._load_metadata(candidate)
                    key = str(candidate.relative_to(self.base_path))
                    return [
                        StorageObject(
                            key=key,
                            size=stat.st_size,
                            etag=await self._calculate_etag(candidate),
                            last_modified=datetime.fromtimestamp(stat.st_mtime),
                            content_type=(
                                meta.get("content_type") if meta else self._guess_content_type(key)
                            ),
                        )
                    ]

            # General path: enumerate and filter by prefix
            for path in self.base_path.rglob("*"):
                if not path.is_file() or path.name.endswith(".meta"):
                    continue
                key = str(path.relative_to(self.base_path))
                if clean_prefix and not key.startswith(clean_prefix):
                    continue

                stat = path.stat()
                meta = await self._load_metadata(path)
                objects.append(
                    StorageObject(
                        key=key,
                        size=stat.st_size,
                        etag=await self._calculate_etag(path),
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        content_type=(
                            meta.get("content_type") if meta else self._guess_content_type(key)
                        ),
                    )
                )
                count += 1
                if count >= limit:
                    break

            return objects

        except Exception as e:
            raise StorageError(f"Failed to list objects with prefix '{prefix}': {e}") from e

    async def get_metadata(self, key: str) -> StorageMetadata:
        """Get file metadata from local storage."""
        try:
            file_path = self._safe_path(key)

            if not file_path.exists():
                raise NotFoundError(f"File not found: {key}")

            stat = file_path.stat()
            meta = await self._load_metadata(file_path)

            return StorageMetadata(
                etag=await self._calculate_etag(file_path),
                content_type=meta.get("content_type") if meta else self._guess_content_type(key),
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                custom_metadata=meta.get("metadata", {}) if meta else {},
            )

        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to get metadata for {key}: {e}") from e

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ) -> PresignedRequest:
        """Generate presigned URL for local storage.

        For local storage, this returns the public URL directly if configured.
        For secure access, this would need to be integrated with application auth.
        """
        _ = (response_content_disposition, response_content_type)
        if self.config.public_base_url:
            url = f"{self.config.public_base_url}/{key}"
        else:
            # For local storage without public URL, return file:// URL
            file_path = self._safe_path(key)
            url = file_path.as_uri()

        return PresignedRequest(url=url, method=method, expires_in=expires_in)

    async def copy(self, source_key: str, dest_key: str) -> bool:
        """Copy file within local storage."""
        try:
            source_path = self._safe_path(source_key)
            dest_path = self._safe_path(dest_key)

            if not source_path.exists():
                raise NotFoundError(f"Source file not found: {source_key}")

            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source_path, dest_path)

            # Copy metadata if exists
            source_meta = self._metadata_path(source_path)
            if source_meta.exists():
                dest_meta = self._metadata_path(dest_path)
                shutil.copy2(source_meta, dest_meta)

            logger.info(f"Copied in local storage", source=source_key, dest=dest_key)
            return True

        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to copy {source_key} to {dest_key}: {e}") from e

    async def move(self, source_key: str, dest_key: str) -> bool:
        """Move file within local storage."""
        try:
            source_path = self._safe_path(source_key)
            dest_path = self._safe_path(dest_key)

            if not source_path.exists():
                raise NotFoundError(f"Source file not found: {source_key}")

            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source_path), str(dest_path))

            # Move metadata if exists
            source_meta = self._metadata_path(source_path)
            if source_meta.exists():
                dest_meta = self._metadata_path(dest_path)
                shutil.move(str(source_meta), str(dest_meta))

            logger.info(f"Moved in local storage", source=source_key, dest=dest_key)
            return True

        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to move {source_key} to {dest_key}: {e}") from e

    def public_url(self, key: str) -> Optional[str]:
        """Get public URL for file."""
        if self.config.public_base_url:
            return f"{self.config.public_base_url}/{key}"
        # No public base configured; no public URL
        return None

    async def health_check(self) -> bool:
        """Check local storage accessibility."""
        try:
            # Check if base path exists and is writable
            test_file = self.base_path / ".health_check"
            test_file.touch()
            test_file.unlink()
            logger.info("Local storage health check passed")
            return True
        except Exception as e:
            logger.error(f"Local storage health check failed", error=str(e))
            return False

    # Advanced methods
    async def multipart_upload_start(self, key: str, content_type: Optional[str] = None) -> str:
        """Start multipart upload (returns key as upload ID)."""
        # For local storage, we use the key as upload ID
        # Create a temp file for accumulating parts
        temp_path = self.base_path / ".uploads" / key
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.touch()
        return key

    async def multipart_upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> str:
        """Upload part (append to temp file)."""
        temp_path = self.base_path / ".uploads" / upload_id

        # Append data to temp file
        async with aiofiles.open(temp_path, "ab") as f:
            await f.write(data)

        # Return ETag of this part
        return hashlib.md5(data).hexdigest()

    async def multipart_upload_complete(
        self, upload_id: str, key: str, parts: list[dict]
    ) -> UploadResult:
        """Complete multipart upload (move temp file to final location)."""
        temp_path = self.base_path / ".uploads" / upload_id
        final_path = self._safe_path(key)

        # Create parent directories if needed
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Move temp file to final location
        shutil.move(str(temp_path), str(final_path))

        # Get file info
        stat = final_path.stat()

        return UploadResult(
            key=key,
            etag=await self._calculate_etag(final_path),
            size=stat.st_size,
            content_type=self._guess_content_type(key),
            url=self.public_url(key) if self.config.public_base_url else None,
        )

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
        results = {}
        for key in keys:
            try:
                results[key] = await self.delete(key)
            except Exception:
                results[key] = False
        return results

    async def create_directory(self, path: str) -> bool:
        """Create directory in local storage."""
        try:
            dir_path = self._safe_path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            raise StorageError(f"Failed to create directory {path}: {e}") from e

    async def delete_directory(self, path: str, recursive: bool = False) -> bool:
        """Delete directory from local storage."""
        try:
            dir_path = self._safe_path(path)

            if not dir_path.exists():
                return False

            if recursive and dir_path.is_dir():
                shutil.rmtree(dir_path)
            elif dir_path.is_dir():
                dir_path.rmdir()  # Only works if empty

            return True

        except Exception as e:
            raise StorageError(f"Failed to delete directory {path}: {e}") from e

    def _safe_path(self, key: str) -> Path:
        """Build safe path preventing directory traversal.

        Args:
            key: Storage key

        Returns:
            Safe absolute path

        Raises:
            ValidationError: If path is unsafe
        """
        # Remove leading slashes and normalize
        clean_key = key.lstrip("/")

        # Build path
        path = (self.base_path / clean_key).resolve()

        # Ensure path is within base path (avoid traversal)
        try:
            path.relative_to(self.base_path)
        except Exception:
            raise ValidationError(f"Invalid path: {key}")

        return path

    def _metadata_path(self, file_path: Path) -> Path:
        """Get metadata file path for a file."""
        return file_path.parent / f"{file_path.name}.meta"

    async def _save_metadata(
        self, file_path: Path, metadata: Optional[dict], content_type: Optional[str]
    ) -> None:
        """Save metadata to sidecar file."""
        import json

        meta_path = self._metadata_path(file_path)
        meta_data = {}

        if metadata:
            meta_data["metadata"] = metadata
        if content_type:
            meta_data["content_type"] = content_type

        async with aiofiles.open(meta_path, "w") as f:
            await f.write(json.dumps(meta_data))

    async def _load_metadata(self, file_path: Path) -> dict:
        """Load metadata from sidecar file."""
        import json

        meta_path = self._metadata_path(file_path)

        if not meta_path.exists():
            return {}

        try:
            async with aiofiles.open(meta_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except:
            return {}

    async def _calculate_etag(self, file_path: Path) -> str:
        """Calculate ETag for file."""
        hasher = hashlib.md5()

        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)

        return hasher.hexdigest()

    def _guess_content_type(self, key: str) -> str:
        """Guess content type from file extension."""
        content_type, _ = mimetypes.guess_type(key)
        return content_type or "application/octet-stream"


async def build_local_provider(config: StorageConfig) -> LocalProvider:
    """Build local storage provider.

    Args:
        config: Storage configuration

    Returns:
        Configured local provider instance
    """
    provider = LocalProvider(config)

    # Check accessibility
    if not await provider.health_check():
        raise StorageError("Failed to access local storage")

    return provider
