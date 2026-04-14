# input: 无外部依赖，纯业务逻辑
# output: ChatRoom, Message, AnalysisReport, CoachingSession, CoachingMessage 领域实体
# owner: wanhua.gu
# pos: 领域层 - 利益相关者聊天聚合实体定义；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain entities for the stakeholder chat aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from domain.common.exceptions import DomainValidationException

_ROOM_TYPES = {"private", "group", "battle_prep", "defense"}
_SENDER_TYPES = {"user", "persona", "system"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class ChatRoom:
    """A chat room for stakeholder simulation (private, group, or battle_prep)."""

    id: Optional[int]
    name: str
    type: str  # private | group | battle_prep
    persona_ids: list[str] = field(default_factory=list)
    scenario_id: Optional[int] = None
    created_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    context_summary: Optional[str] = None
    summary_up_to_message_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.type not in _ROOM_TYPES:
            raise DomainValidationException(
                f"Invalid room type: {self.type}",
                field="type",
                details={"allowed": sorted(_ROOM_TYPES)},
            )
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)
        self.last_message_at = _ensure_utc(self.last_message_at)


@dataclass
class Message:
    """A single message within a stakeholder chat room."""

    id: Optional[int]
    room_id: int
    sender_type: str  # user | persona | system
    sender_id: str
    content: str
    timestamp: Optional[datetime] = None
    emotion_score: Optional[int] = None  # -5 (strongly opposed) to +5 (strongly supportive)
    emotion_label: Optional[str] = None  # e.g. 支持, 质疑, 愤怒, 犹豫

    def __post_init__(self) -> None:
        if self.sender_type not in _SENDER_TYPES:
            raise DomainValidationException(
                f"Invalid sender type: {self.sender_type}",
                field="sender_type",
                details={"allowed": sorted(_SENDER_TYPES)},
            )
        if self.timestamp is None:
            self.timestamp = _utcnow()
        else:
            self.timestamp = _ensure_utc(self.timestamp)


@dataclass
class AnalysisReport:
    """An LLM-generated analysis report for a stakeholder chat room."""

    id: Optional[int]
    room_id: int
    summary: str
    content: dict = field(default_factory=dict)  # full structured report JSON
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)


_COACHING_STATUSES = {"active", "completed"}
_COACHING_ROLES = {"user", "coach"}


@dataclass
class CoachingSession:
    """An interactive coaching session based on an analysis report."""

    id: Optional[int]
    room_id: int
    report_id: int
    status: str = "active"  # active | completed
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.status not in _COACHING_STATUSES:
            raise DomainValidationException(
                f"Invalid coaching session status: {self.status}",
                field="status",
                details={"allowed": sorted(_COACHING_STATUSES)},
            )
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)
        self.completed_at = _ensure_utc(self.completed_at)


@dataclass
class CoachingMessage:
    """A single message within a coaching session."""

    id: Optional[int]
    session_id: int
    role: str  # user | coach
    content: str
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.role not in _COACHING_ROLES:
            raise DomainValidationException(
                f"Invalid coaching message role: {self.role}",
                field="role",
                details={"allowed": sorted(_COACHING_ROLES)},
            )
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)
