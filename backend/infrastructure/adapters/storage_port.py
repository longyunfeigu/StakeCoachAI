"""Infrastructure adapter that implements the application StoragePort
by delegating to the concrete StorageProvider and translating models.
"""

from __future__ import annotations

from typing import AsyncIterator, Optional

from application.ports.storage import StoragePort
from application.ports.storage import (
    PresignedURL,
    ObjectMetadata,
    StorageInfo,
    UploadOutcome,
)
from infrastructure.external.storage import StorageProvider
from infrastructure.external.storage.base import AdvancedStorageProvider


class StorageProviderPortAdapter(StoragePort):
    def __init__(self, provider: StorageProvider):
        self.provider = provider

    def info(self) -> StorageInfo:
        cfg = getattr(self.provider, "config", None)
        stype = getattr(cfg, "type", None)
        bucket = getattr(cfg, "bucket", None)
        region = getattr(cfg, "region", None)
        if hasattr(stype, "value"):
            stype_value = str(getattr(stype, "value"))
        else:
            stype_value = str(stype) if stype is not None else ""
        return StorageInfo(type=stype_value, bucket=bucket, region=region)

    async def delete(self, key: str) -> bool:
        return await self.provider.delete(key)

    async def get_metadata(self, key: str) -> ObjectMetadata:
        meta = await self.provider.get_metadata(key)
        return ObjectMetadata(
            etag=getattr(meta, "etag", None),
            content_type=getattr(meta, "content_type", None),
            size=int(getattr(meta, "size", 0) or 0),
            custom_metadata=dict(getattr(meta, "custom_metadata", {}) or {}),
        )

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ) -> PresignedURL:
        presigned = await self.provider.generate_presigned_url(
            key,
            expires_in,
            method,
            content_type,
            response_content_disposition=response_content_disposition,
            response_content_type=response_content_type,
        )
        return PresignedURL(
            url=getattr(presigned, "url", ""),
            method=getattr(presigned, "method", method),
            expires_in=int(getattr(presigned, "expires_in", expires_in) or expires_in),
            headers=dict(getattr(presigned, "headers", {}) or {}),
            fields=dict(getattr(presigned, "fields", {}) or {}),
        )

    def public_url(self, key: str) -> Optional[str]:
        return self.provider.public_url(key)

    async def upload(
        self,
        data: bytes,
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadOutcome:
        result = await self.provider.upload(data, key, metadata=metadata, content_type=content_type)
        return UploadOutcome(
            key=getattr(result, "key", key),
            etag=getattr(result, "etag", None),
            size=int(getattr(result, "size", 0) or 0),
            content_type=getattr(result, "content_type", content_type),
            url=getattr(result, "url", None),
        )

    async def upload_stream(
        self,
        stream: AsyncIterator[bytes],
        key: str,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
    ) -> UploadOutcome:
        provider = self.provider

        part_size = 5 * 1024 * 1024
        threshold = part_size

        buffer = bytearray()
        total = 0

        upload_id: Optional[str] = None
        parts: list[dict[str, int | str]] = []
        part_number = 1

        async def _ensure_multipart() -> str:
            nonlocal upload_id
            if upload_id is not None:
                return upload_id
            if not isinstance(provider, AdvancedStorageProvider):
                raise RuntimeError("Provider does not support multipart upload")
            upload_id = await provider.multipart_upload_start(key, content_type=content_type)
            return upload_id

        async for chunk in stream:
            if not chunk:
                continue
            total += len(chunk)
            buffer.extend(chunk)

            if upload_id is None and len(buffer) >= threshold:
                await _ensure_multipart()

            if upload_id is None:
                continue

            while len(buffer) >= part_size:
                part = bytes(buffer[:part_size])
                del buffer[:part_size]
                etag = await provider.multipart_upload_part(key, upload_id, part_number, part)
                parts.append({"PartNumber": part_number, "ETag": etag})
                part_number += 1

        if upload_id is None:
            # Small file: do a normal upload to preserve metadata when possible.
            result = await provider.upload(
                bytes(buffer), key, metadata=metadata, content_type=content_type
            )
            return UploadOutcome(
                key=getattr(result, "key", key),
                etag=getattr(result, "etag", None),
                size=int(getattr(result, "size", total) or total),
                content_type=getattr(result, "content_type", content_type),
                url=getattr(result, "url", None),
            )

        if buffer:
            etag = await provider.multipart_upload_part(key, upload_id, part_number, bytes(buffer))
            parts.append({"PartNumber": part_number, "ETag": etag})

        result = await provider.multipart_upload_complete(upload_id, key, parts)
        return UploadOutcome(
            key=getattr(result, "key", key),
            etag=getattr(result, "etag", None),
            size=total,
            content_type=content_type,
            url=getattr(result, "url", None),
        )
