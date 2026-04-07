"""Domain entity representing a stored file asset."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from domain.common.exceptions import DomainValidationException

_ALLOWED_STATUSES = {"pending", "active", "deleted"}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class FileAsset:
    """Aggregate root describing a file stored in object storage."""

    id: Optional[int]
    owner_id: Optional[int]
    storage_type: str
    bucket: Optional[str]
    region: Optional[str]
    key: str
    size: int = 0
    etag: Optional[str] = None
    content_type: Optional[str] = None
    original_filename: Optional[str] = None
    kind: Optional[str] = None
    is_public: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.status = self.status or "pending"
        self._validate_status(self.status)
        self.created_at = _ensure_utc(self.created_at)
        self.updated_at = _ensure_utc(self.updated_at)
        self.deleted_at = _ensure_utc(self.deleted_at)
        if self.metadata is None:
            self.metadata = {}

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in _ALLOWED_STATUSES:
            raise DomainValidationException(
                f"非法的文件状态: {status}",
                field="status",
                details={"allowed": sorted(_ALLOWED_STATUSES)},
            )

    def _touch(self) -> None:
        now = datetime.now(timezone.utc)
        self.updated_at = now
        if self.created_at is None:
            self.created_at = now

    def mark_pending(self) -> None:
        self._validate_status("pending")
        self.status = "pending"
        self.deleted_at = None
        self._touch()

    def mark_active(self) -> None:
        self._validate_status("active")
        self.status = "active"
        self.deleted_at = None
        self._touch()

    def mark_deleted(self) -> None:
        self._validate_status("deleted")
        self.status = "deleted"
        self.deleted_at = datetime.now(timezone.utc)
        self._touch()

    def update_object_metadata(
        self,
        *,
        size: Optional[int] = None,
        etag: Optional[str] = None,
        content_type: Optional[str] = None,
        url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if size is not None:
            self.size = size
        if etag is not None:
            self.etag = etag
        if content_type is not None:
            self.content_type = content_type
        if url is not None:
            self.url = url
        if metadata is not None:
            self.metadata = metadata
        self._touch()

    def is_deleted(self) -> bool:
        return self.status == "deleted"

    def belongs_to(self, user_id: int) -> bool:
        return self.owner_id == user_id
