"""AWS S3 storage provider implementation."""

import hashlib
from typing import AsyncIterator, Optional, Any
from datetime import datetime, timedelta
import anyio
from functools import partial

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


class S3Provider(AdvancedStorageProvider):
    """AWS S3 storage provider."""

    def __init__(self, client: Any, config: StorageConfig):  # boto3 S3 client
        """Initialize S3 provider.

        Args:
            client: Boto3 S3 client instance
            config: Storage configuration
        """
        self.client = client
        self.config = config
        self.bucket = config.bucket
        self.region = config.region or "us-east-1"

    async def upload(
        self,
        file: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadResult:
        """Upload file to S3."""
        try:
            # Prepare upload arguments
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            if metadata:
                extra_args["Metadata"] = metadata
            if self.config.s3_acl:
                extra_args["ACL"] = self.config.s3_acl
            if self.config.s3_sse:
                extra_args["ServerSideEncryption"] = self.config.s3_sse

            # Upload using thread pool for sync SDK
            response = await anyio.to_thread.run_sync(
                partial(
                    self.client.put_object, Bucket=self.bucket, Key=key, Body=file, **extra_args
                )
            )

            # Use server returned ETag if available; else fallback to local hash
            etag = None
            try:
                etag = (response or {}).get("ETag", "").strip('"')  # type: ignore[union-attr]
            except Exception:
                etag = None
            if not etag:
                etag = hashlib.md5(file).hexdigest()

            # Build result
            result = UploadResult(key=key, etag=etag, size=len(file), content_type=content_type)

            # Attach only stable public URL when available (no temporary presigned here)
            if self.config.public_base_url:
                result.url = f"{self.config.public_base_url}/{key}"
            elif self.config.s3_acl == "public-read":
                # Public bucket: static URL is sufficient
                result.url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
            # For private buckets, do not attach presigned URLs to result.url

            logger.info(f"Uploaded to S3", key=key, size=len(file))
            return result

        except Exception as e:
            self._handle_exception(e, f"upload {key}")

    async def download(self, key: str) -> bytes:
        """Download file from S3."""
        try:
            response = await anyio.to_thread.run_sync(
                partial(self.client.get_object, Bucket=self.bucket, Key=key)
            )
            body = response["Body"]
            try:
                data = await anyio.to_thread.run_sync(body.read)
                logger.info(f"Downloaded from S3", key=key, size=len(data))
                return data
            finally:
                # Ensure underlying stream is closed even if read fails
                try:
                    await anyio.to_thread.run_sync(body.close)
                except Exception:
                    pass
        except Exception as e:
            self._handle_exception(e, f"download {key}")

    async def stream_download(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream download file from S3."""
        try:
            response = await anyio.to_thread.run_sync(
                partial(self.client.get_object, Bucket=self.bucket, Key=key)
            )

            body = response["Body"]
            try:
                while True:
                    chunk = await anyio.to_thread.run_sync(partial(body.read, chunk_size))
                    if not chunk:
                        break
                    yield chunk
            finally:
                # Ensure underlying stream is closed to free the connection
                try:
                    await anyio.to_thread.run_sync(body.close)
                except Exception:
                    pass

        except Exception as e:
            self._handle_exception(e, f"stream download {key}")

    async def delete(self, key: str) -> bool:
        """Delete file from S3."""
        try:
            await anyio.to_thread.run_sync(
                partial(self.client.delete_object, Bucket=self.bucket, Key=key)
            )
            logger.info(f"Deleted from S3", key=key)
            return True
        except Exception as e:
            self._handle_exception(e, f"delete {key}")

    async def exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            await anyio.to_thread.run_sync(
                partial(self.client.head_object, Bucket=self.bucket, Key=key)
            )
            return True
        except Exception as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            self._handle_exception(e, f"exists {key}")

    async def list_objects(self, prefix: str = "", limit: int = 1000) -> list[StorageObject]:
        """List objects in S3."""
        try:
            response = await anyio.to_thread.run_sync(
                partial(
                    self.client.list_objects_v2, Bucket=self.bucket, Prefix=prefix, MaxKeys=limit
                )
            )

            objects = []
            for obj in response.get("Contents", []):
                objects.append(
                    StorageObject(
                        key=obj["Key"],
                        size=obj["Size"],
                        etag=obj.get("ETag", "").strip('"'),
                        last_modified=obj.get("LastModified"),
                    )
                )

            return objects

        except Exception as e:
            self._handle_exception(e, f"list objects {prefix}")

    async def get_metadata(self, key: str) -> StorageMetadata:
        """Get file metadata from S3."""
        try:
            response = await anyio.to_thread.run_sync(
                partial(self.client.head_object, Bucket=self.bucket, Key=key)
            )

            return StorageMetadata(
                etag=response.get("ETag", "").strip('"'),
                content_type=response.get("ContentType"),
                size=response.get("ContentLength", 0),
                last_modified=response.get("LastModified"),
                custom_metadata=response.get("Metadata", {}),
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
        """Generate presigned URL for S3."""
        try:
            if method == "GET":
                params = {"Bucket": self.bucket, "Key": key}
                if response_content_disposition:
                    params["ResponseContentDisposition"] = response_content_disposition
                if response_content_type:
                    params["ResponseContentType"] = response_content_type
                url = await anyio.to_thread.run_sync(
                    partial(
                        self.client.generate_presigned_url,
                        ClientMethod="get_object",
                        Params=params,
                        ExpiresIn=expires_in,
                    )
                )
                return PresignedRequest(url=url, method="GET", expires_in=expires_in)

            elif method == "PUT":
                url = await anyio.to_thread.run_sync(
                    partial(
                        self.client.generate_presigned_url,
                        ClientMethod="put_object",
                        Params={
                            "Bucket": self.bucket,
                            "Key": key,
                            **({"ContentType": content_type} if content_type else {}),
                        },
                        ExpiresIn=expires_in,
                    )
                )
                return PresignedRequest(
                    url=url,
                    method="PUT",
                    expires_in=expires_in,
                    headers={"Content-Type": content_type or "application/octet-stream"},
                )

            elif method == "POST":
                # Generate presigned POST
                if content_type:
                    response = await anyio.to_thread.run_sync(
                        partial(
                            self.client.generate_presigned_post,
                            Bucket=self.bucket,
                            Key=key,
                            ExpiresIn=expires_in,
                            Fields={"Content-Type": content_type},
                            Conditions=[{"Content-Type": content_type}],
                        )
                    )
                else:
                    response = await anyio.to_thread.run_sync(
                        partial(
                            self.client.generate_presigned_post,
                            Bucket=self.bucket,
                            Key=key,
                            ExpiresIn=expires_in,
                        )
                    )
                headers = {}
                if content_type:
                    headers["Content-Type"] = content_type
                return PresignedRequest(
                    url=response["url"],
                    method="POST",
                    expires_in=expires_in,
                    fields=response["fields"],
                    headers=headers,
                )

            else:
                raise ValueError(f"Unsupported method: {method}")

        except Exception as e:
            self._handle_exception(e, f"generate presigned URL {key}")

    async def copy(self, source_key: str, dest_key: str) -> bool:
        """Copy file within S3."""
        try:
            copy_source = {"Bucket": self.bucket, "Key": source_key}
            await anyio.to_thread.run_sync(
                partial(
                    self.client.copy_object,
                    CopySource=copy_source,
                    Bucket=self.bucket,
                    Key=dest_key,
                )
            )
            logger.info(f"Copied in S3", source=source_key, dest=dest_key)
            return True
        except Exception as e:
            self._handle_exception(e, f"copy {source_key} to {dest_key}")

    async def move(self, source_key: str, dest_key: str) -> bool:
        """Move file within S3."""
        if await self.copy(source_key, dest_key):
            return await self.delete(source_key)
        return False

    def public_url(self, key: str) -> Optional[str]:
        """Get public/CDN URL for file."""
        if self.config.public_base_url:
            return f"{self.config.public_base_url}/{key}"
        elif self.config.s3_acl == "public-read":
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        else:
            # Private bucket, require presigned URL (explicit None)
            return None

    async def health_check(self) -> bool:
        """Check S3 connectivity."""
        try:
            await anyio.to_thread.run_sync(partial(self.client.head_bucket, Bucket=self.bucket))
            logger.info("S3 health check passed")
            return True
        except Exception as e:
            logger.error(f"S3 health check failed", error=str(e))
            return False

    # Advanced methods
    async def multipart_upload_start(self, key: str, content_type: Optional[str] = None) -> str:
        """Start multipart upload."""
        try:
            args = {"Bucket": self.bucket, "Key": key}
            if content_type:
                args["ContentType"] = content_type

            response = await anyio.to_thread.run_sync(
                partial(self.client.create_multipart_upload, **args)
            )
            return response["UploadId"]
        except Exception as e:
            self._handle_exception(e, f"start multipart upload {key}")

    async def multipart_upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> str:
        """Upload part in multipart upload."""
        try:
            response = await anyio.to_thread.run_sync(
                partial(
                    self.client.upload_part,
                    Bucket=self.bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=data,
                )
            )
            return response["ETag"]
        except Exception as e:
            self._handle_exception(e, f"upload part {part_number}")

    async def multipart_upload_complete(
        self, upload_id: str, key: str, parts: list[dict]
    ) -> UploadResult:
        """Complete multipart upload."""
        try:
            response = await anyio.to_thread.run_sync(
                partial(
                    self.client.complete_multipart_upload,
                    Bucket=self.bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
            )

            return UploadResult(
                key=key,
                etag=response.get("ETag", "").strip('"'),
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
            objects = [{"Key": key} for key in keys]
            response = await anyio.to_thread.run_sync(
                partial(self.client.delete_objects, Bucket=self.bucket, Delete={"Objects": objects})
            )

            deleted = {obj["Key"]: True for obj in response.get("Deleted", [])}
            errors = {obj["Key"]: False for obj in response.get("Errors", [])}

            return {**deleted, **errors}

        except Exception as e:
            self._handle_exception(e, "batch delete")

    async def create_directory(self, path: str) -> bool:
        """Create directory in S3 (creates empty object with trailing slash)."""
        if not path.endswith("/"):
            path = f"{path}/"

        await self.upload(b"", path)
        return True

    async def delete_directory(self, path: str, recursive: bool = False) -> bool:
        """Delete directory from S3."""
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
        """Map S3 exceptions to storage exceptions."""
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")

        if error_code in ["NoSuchKey", "404"]:
            raise NotFoundError(f"Object not found: {operation}")
        elif error_code in ["AccessDenied", "403"]:
            raise PermissionDeniedError(f"Access denied: {operation}")
        elif error_code in ["RequestTimeout", "SlowDown", "ServiceUnavailable"]:
            raise TransientError(f"Transient error: {operation}: {e}")
        else:
            raise StorageError(f"S3 error during {operation}: {e}") from e


async def build_s3_provider(config: StorageConfig) -> S3Provider:
    """Build S3 storage provider.

    Args:
        config: Storage configuration

    Returns:
        Configured S3 provider instance
    """
    if not config.bucket:
        raise ConfigurationError("S3 bucket name is required")

    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise ConfigurationError("boto3 is required for S3 storage")

    # Build boto3 client config
    boto_config = BotoConfig(
        region_name=config.region,
        signature_version="s3v4",
        retries={"max_attempts": config.max_retry_attempts, "mode": "standard"},
        connect_timeout=config.timeout,
        read_timeout=config.timeout,
    )

    # Build client arguments
    client_args = {"service_name": "s3", "config": boto_config}

    if config.aws_access_key_id and config.aws_secret_access_key:
        client_args.update(
            {
                "aws_access_key_id": config.aws_access_key_id,
                "aws_secret_access_key": config.aws_secret_access_key,
            }
        )

    if config.endpoint:
        client_args["endpoint_url"] = config.endpoint
        client_args["use_ssl"] = config.enable_ssl

    # Create client
    client = boto3.client(**client_args)

    # Create and return provider
    provider = S3Provider(client, config)

    # Check connectivity
    if not await provider.health_check():
        raise ConfigurationError("Failed to connect to S3")

    return provider
