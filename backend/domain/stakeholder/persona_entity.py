# input: 无外部依赖，纯业务逻辑
# output: Persona 聚合实体 + 5-layer 子类型 (HardRule, IdentityProfile, ExpressionStyle, DecisionPattern, InterpersonalStyle) + Evidence 证据链 + rejected_features (Story 2.7)
# owner: wanhua.gu
# pos: 领域层 - 利益相关者画像聚合 (5-layer 结构 + v1/v2 schema 兼容)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain entities for the 5-layer structured Persona (Story 2.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from domain.common.exceptions import DomainValidationException

_EVIDENCE_LAYERS = {"hard_rules", "identity", "expression", "decision", "interpersonal"}


@dataclass
class HardRule:
    """Layer 1 — 不可妥协的硬性规则/底线。"""

    statement: str
    severity: str = "medium"  # low | medium | high | critical


@dataclass
class IdentityProfile:
    """Layer 2 — 身份背景、核心价值、隐藏议程、信息偏好。"""

    background: str = ""
    core_values: list[str] = field(default_factory=list)
    hidden_agenda: Optional[str] = None
    information_preference: Optional[str] = None


@dataclass
class ExpressionStyle:
    """Layer 3 — 表达风格：语气、口头禅、打断倾向。"""

    tone: str = ""
    catchphrases: list[str] = field(default_factory=list)
    interruption_tendency: str = "medium"  # low | medium | high


@dataclass
class DecisionPattern:
    """Layer 4 — 决策模式：风格、风险容忍度、典型追问。"""

    style: str = ""
    risk_tolerance: str = "medium"  # low | medium | high
    typical_questions: list[str] = field(default_factory=list)


@dataclass
class EscalationChain:
    """多步升级序列：触发条件 → 逐级施压步骤。"""

    trigger: str
    steps: list[str] = field(default_factory=list)


@dataclass
class InterpersonalStyle:
    """Layer 5 — 人际互动：权威模式、触发器、情绪状态、升级链。"""

    authority_mode: str = ""
    triggers: list[str] = field(default_factory=list)
    emotion_states: list[str] = field(default_factory=list)
    escalation_chains: list[EscalationChain] = field(default_factory=list)


@dataclass
class Evidence:
    """Persona 特征对应的原文证据引用。

    每条 Evidence 关联到 5 层中的某一层，提供可追溯的原文片段 + 置信度。
    """

    claim: str
    citations: list[str]
    confidence: float
    source_material_id: str
    layer: str  # hard_rules | identity | expression | decision | interpersonal

    def __post_init__(self) -> None:
        if self.layer not in _EVIDENCE_LAYERS:
            raise DomainValidationException(
                f"Invalid evidence layer: {self.layer}",
                field="layer",
                details={"allowed": sorted(_EVIDENCE_LAYERS)},
            )


@dataclass
class Persona:
    """Stakeholder persona (聚合根)。

    v2 5-layer structured persona. All personas use the structured format.
    """

    id: str
    name: str
    role: str
    avatar_color: Optional[str] = None
    organization_id: Optional[int] = None
    team_id: Optional[int] = None
    profile_summary: str = ""
    parse_status: str = "ok"  # ok | partial
    voice_id: Optional[str] = None
    voice_speed: float = 1.0
    voice_style: Optional[str] = None
    # v2 fields (5-layer structured)
    hard_rules: list[HardRule] = field(default_factory=list)
    identity: Optional[IdentityProfile] = None
    expression: Optional[ExpressionStyle] = None
    decision: Optional[DecisionPattern] = None
    interpersonal: Optional[InterpersonalStyle] = None
    user_context: Optional[str] = None
    evidence_citations: list[Evidence] = field(default_factory=list)
    source_materials: list[str] = field(default_factory=list)
    # Story 2.7 — 用户标 "不对" 的特征索引（按 layer 分组）。存到
    # structured_profile._metadata.rejected_features，不触发 DB schema 迁移。
    rejected_features: dict[str, list[int]] = field(default_factory=dict)
