# input: 无外部依赖，纯业务逻辑
# output: Conversation, Message, Run, AgentConfig 领域实体
# owner: unknown
# pos: 领域层 - 对话聚合根及关联实体定义；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain entities for the conversation aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from domain.common.exceptions import DomainValidationException

_CONVERSATION_STATUSES = {"active", "archived"}
_MESSAGE_ROLES = {"system", "user", "assistant"}
_RUN_STATUSES = {"running", "completed", "failed"}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Conversation:
    """Aggregate root for a chat conversation."""

    id: Optional[int]
    title: str
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.status = self.status or "active"
        if self.status not in _CONVERSATION_STATUSES:
            raise DomainValidationException(
                f"Invalid conversation status: {self.status}",
                field="status",
                details={"allowed": sorted(_CONVERSATION_STATUSES)},
            )
        self.created_at = _ensure_utc(self.created_at)
        self.updated_at = _ensure_utc(self.updated_at)
        self.deleted_at = _ensure_utc(self.deleted_at)
        if self.metadata is None:
            self.metadata = {}

    def _touch(self) -> None:
        now = _utcnow()
        self.updated_at = now
        if self.created_at is None:
            self.created_at = now

    def update_title(self, title: str) -> None:
        self.title = title
        self._touch()

    def archive(self) -> None:
        self.status = "archived"
        self._touch()

    def soft_delete(self) -> None:
        self.status = "archived"
        self.deleted_at = _utcnow()
        self._touch()

    def is_active(self) -> bool:
        return self.status == "active" and self.deleted_at is None


@dataclass
class Message:
    """A single message within a conversation."""

    id: Optional[int]
    conversation_id: int
    role: str  # system | user | assistant
    content: str
    run_id: Optional[int] = None
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.role not in _MESSAGE_ROLES:
            raise DomainValidationException(
                f"Invalid message role: {self.role}",
                field="role",
                details={"allowed": sorted(_MESSAGE_ROLES)},
            )
        self.created_at = _ensure_utc(self.created_at)
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Run:
    """Tracks a single LLM invocation within a conversation.

    Phase 1 state machine: running → completed | failed
    """

    id: Optional[int]
    conversation_id: int
    status: str = "running"
    model: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.status not in _RUN_STATUSES:
            raise DomainValidationException(
                f"Invalid run status: {self.status}",
                field="status",
                details={"allowed": sorted(_RUN_STATUSES)},
            )
        self.started_at = _ensure_utc(self.started_at) or _utcnow()
        self.completed_at = _ensure_utc(self.completed_at)
        self.created_at = _ensure_utc(self.created_at)

    def mark_completed(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.status = "completed"
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.completed_at = _utcnow()

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error_message = error
        self.completed_at = _utcnow()


@dataclass
class AgentConfig:
    """Standalone aggregate for reusable agent configurations."""

    id: Optional[int]
    name: str
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainValidationException(
                "Agent config name is required",
                field="name",
            )
        self.created_at = _ensure_utc(self.created_at)
        self.updated_at = _ensure_utc(self.updated_at)
        if self.metadata is None:
            self.metadata = {}

    def _touch(self) -> None:
        now = _utcnow()
        self.updated_at = now
        if self.created_at is None:
            self.created_at = now
