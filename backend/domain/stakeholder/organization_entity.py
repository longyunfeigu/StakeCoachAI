# input: 无外部依赖，纯业务逻辑
# output: Organization, Team, PersonaRelationship 领域实体
# owner: wanhua.gu
# pos: 领域层 - 组织上下文聚合实体定义（组织、团队、角色关系）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain entities for the organization context aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from domain.common.exceptions import DomainValidationException

_RELATIONSHIP_TYPES = {"superior", "subordinate", "peer", "cross_department"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class Organization:
    """A company or organization that provides context for stakeholder personas."""

    id: Optional[int]
    name: str
    industry: str = ""
    description: str = ""
    context_prompt: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)


@dataclass
class Team:
    """A department or team within an organization."""

    id: Optional[int]
    organization_id: int
    name: str
    description: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)


@dataclass
class PersonaRelationship:
    """A directed relationship between two personas within an organization."""

    id: Optional[int]
    organization_id: int
    from_persona_id: str
    to_persona_id: str
    relationship_type: str  # superior | subordinate | peer | cross_department
    description: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.relationship_type not in _RELATIONSHIP_TYPES:
            raise DomainValidationException(
                f"Invalid relationship type: {self.relationship_type}",
                field="relationship_type",
                details={"allowed": sorted(_RELATIONSHIP_TYPES)},
            )
        if self.from_persona_id == self.to_persona_id:
            raise DomainValidationException(
                "A persona cannot have a relationship with itself",
                field="to_persona_id",
            )
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)
