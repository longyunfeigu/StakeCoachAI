# input: 无外部依赖，纯业务逻辑
# output: Scenario 领域实体
# owner: wanhua.gu
# pos: 领域层 - 利益相关者对话场景实体定义；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain entity for conversation scenario templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Scenario:
    """A reusable conversation scenario template with context prompt."""

    id: Optional[int]
    name: str
    description: str = ""
    context_prompt: str = ""
    suggested_persona_ids: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()
