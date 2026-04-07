"""Shared domain entity primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar

IdT = TypeVar("IdT")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class BaseEntity(Generic[IdT]):
    id: Optional[IdT] = field(default=None, kw_only=True)
    created_at: Optional[datetime] = field(default=None, kw_only=True)
    updated_at: Optional[datetime] = field(default=None, kw_only=True)
    deleted_at: Optional[datetime] = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        self.created_at = _ensure_utc(self.created_at)
        self.updated_at = _ensure_utc(self.updated_at)
        self.deleted_at = _ensure_utc(self.deleted_at)

    def _touch(self) -> None:
        now = datetime.now(timezone.utc)
        self.updated_at = now
        if self.created_at is None:
            self.created_at = now

    def mark_deleted(self) -> None:
        self.deleted_at = datetime.now(timezone.utc)
        self._touch()

    def restore(self) -> None:
        self.deleted_at = None
        self._touch()

    def is_deleted(self) -> bool:
        return self.deleted_at is not None
