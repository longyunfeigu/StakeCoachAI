# input: 无外部依赖，纯业务逻辑
# output: CompetencyEvaluation 领域实体
# owner: wanhua.gu
# pos: 领域层 - 能力评估实体定义（LLM-as-Judge 6 维度评分）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain entity for competency evaluation (LLM-as-Judge)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


COMPETENCY_DIMENSIONS = (
    "persuasion",
    "emotional_management",
    "active_listening",
    "structured_expression",
    "conflict_resolution",
    "stakeholder_alignment",
)


@dataclass
class CompetencyEvaluation:
    """LLM-as-Judge evaluation of user communication competency.

    Each evaluation is linked 1:1 to an AnalysisReport and scores the user
    across 6 dimensions with evidence and improvement suggestions.
    """

    id: Optional[int]
    report_id: int
    room_id: int
    scores: dict = field(default_factory=dict)
    overall_score: float = 0.0
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = _utcnow()
        else:
            self.created_at = _ensure_utc(self.created_at)
