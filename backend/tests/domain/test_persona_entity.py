# input: domain.stakeholder.persona_entity
# output: Story 2.2 AC1-AC3 5-layer persona + Evidence 领域实体单元测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.2 领域实体验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.2: 5-layer Persona domain entities + Evidence."""

from __future__ import annotations

import pytest

from domain.common.exceptions import DomainValidationException
from domain.stakeholder.persona_entity import (
    DecisionPattern,
    Evidence,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)


# ---------------------------------------------------------------------------
# AC1: 5 个 layer dataclass 可实例化
# ---------------------------------------------------------------------------


def test_hard_rule_instantiation() -> None:
    rule = HardRule(statement="绝不在周会上讨论技术债", severity="high")
    assert rule.statement == "绝不在周会上讨论技术债"
    assert rule.severity == "high"


def test_identity_profile_instantiation() -> None:
    identity = IdentityProfile(
        background="20 年金融科技经验",
        core_values=["效率", "结果导向"],
        hidden_agenda="隐藏意图：把团队裁掉一半",
    )
    assert identity.background == "20 年金融科技经验"
    assert identity.core_values == ["效率", "结果导向"]
    assert identity.hidden_agenda == "隐藏意图：把团队裁掉一半"


def test_expression_style_instantiation() -> None:
    style = ExpressionStyle(
        tone="冷峻",
        catchphrases=["你在讲什么？", "重点是什么？"],
        interruption_tendency="high",
    )
    assert style.tone == "冷峻"
    assert "重点是什么？" in style.catchphrases
    assert style.interruption_tendency == "high"


def test_decision_pattern_instantiation() -> None:
    pattern = DecisionPattern(
        style="数据驱动",
        risk_tolerance="low",
        typical_questions=["ROI 是多少？"],
    )
    assert pattern.style == "数据驱动"
    assert pattern.risk_tolerance == "low"


def test_interpersonal_style_instantiation() -> None:
    style = InterpersonalStyle(
        authority_mode="强势",
        triggers=["被质疑专业性"],
        emotion_states=["愤怒", "冷漠"],
    )
    assert style.authority_mode == "强势"
    assert "被质疑专业性" in style.triggers


# ---------------------------------------------------------------------------
# AC3: Evidence dataclass + layer 校验
# ---------------------------------------------------------------------------


def test_evidence_valid_layer() -> None:
    ev = Evidence(
        claim="老板追问 ROI",
        citations=["「这个功能的 ROI 是多少？」"],
        confidence=0.85,
        source_material_id="mat-001",
        layer="decision",
    )
    assert ev.layer == "decision"
    assert ev.confidence == 0.85
    assert len(ev.citations) == 1


def test_evidence_invalid_layer_raises() -> None:
    with pytest.raises(DomainValidationException):
        Evidence(
            claim="X",
            citations=[],
            confidence=0.5,
            source_material_id="mat-001",
            layer="unknown_layer",
        )


@pytest.mark.parametrize(
    "layer",
    ["hard_rules", "identity", "expression", "decision", "interpersonal"],
)
def test_evidence_all_valid_layers(layer: str) -> None:
    ev = Evidence(claim="x", citations=[], confidence=0.5, source_material_id="m", layer=layer)
    assert ev.layer == layer


# ---------------------------------------------------------------------------
# AC2: Persona v2 字段完整
# ---------------------------------------------------------------------------


def test_persona_minimal_defaults() -> None:
    """Minimal persona: only required fields, 5 layers default to empty/None."""
    p = Persona(id="boss", name="老板", role="CEO")
    assert p.id == "boss"
    assert p.name == "老板"
    assert p.hard_rules == []
    assert p.evidence_citations == []
    assert p.identity is None
    assert p.expression is None
    assert p.decision is None
    assert p.interpersonal is None


def test_persona_v2_has_all_fields() -> None:
    """v2 persona: 5 layers + evidence."""
    p = Persona(
        id="cfo",
        name="CFO",
        role="首席财务官",
        hard_rules=[HardRule(statement="预算超支必须事前报告", severity="critical")],
        identity=IdentityProfile(background="会计师出身", core_values=["成本"], hidden_agenda=None),
        expression=ExpressionStyle(
            tone="严谨", catchphrases=["数字会说话"], interruption_tendency="low"
        ),
        decision=DecisionPattern(
            style="保守", risk_tolerance="low", typical_questions=["现金流影响？"]
        ),
        interpersonal=InterpersonalStyle(
            authority_mode="正式", triggers=["数据造假"], emotion_states=["严肃"]
        ),
        evidence_citations=[
            Evidence(
                claim="严谨",
                citations=["按会计准则"],
                confidence=0.9,
                source_material_id="m1",
                layer="expression",
            )
        ],
    )
    assert p.hard_rules[0].severity == "critical"
    assert p.identity is not None
    assert p.identity.background == "会计师出身"
    assert p.expression.catchphrases == ["数字会说话"]
    assert p.decision.risk_tolerance == "low"
    assert p.interpersonal.authority_mode == "正式"
    assert len(p.evidence_citations) == 1
    assert p.evidence_citations[0].layer == "expression"


def test_persona_optional_fields() -> None:
    """Optional fields (avatar_color, voice_*) still work."""
    p = Persona(
        id="pm",
        name="PM",
        role="产品经理",
        avatar_color="#FF0000",
        voice_id="v1",
        voice_speed=1.2,
    )
    assert p.avatar_color == "#FF0000"
    assert p.voice_id == "v1"
    assert p.voice_speed == 1.2
