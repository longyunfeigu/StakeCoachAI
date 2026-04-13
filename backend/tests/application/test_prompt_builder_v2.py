# input: build_system_prompt_v2 / build_compressed_llm_messages_v2
# output: Story 2.8 v2 prompt builder 单元测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.8 v2 prompt builder 单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for prompt_builder v2 functions (Story 2.8 AC3, AC4)."""

from __future__ import annotations

from application.services.stakeholder.prompt_builder import (
    build_compressed_group_llm_messages_v2,
    build_compressed_llm_messages_v2,
    build_system_prompt_v2,
)
from domain.stakeholder.persona_entity import (
    DecisionPattern,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)


def _make_persona(**overrides) -> Persona:
    base = dict(
        id="cfo",
        name="CFO",
        role="首席财务官",
        schema_version=2,
        hard_rules=[HardRule(statement="预算超支必报", severity="critical")],
        identity=IdentityProfile(
            background="20 年会计经验",
            core_values=["成本控制", "数据严谨"],
            hidden_agenda="今年要裁员 15%",
        ),
        expression=ExpressionStyle(
            tone="严谨冷静",
            catchphrases=["数字会说话", "ROI 呢？"],
            interruption_tendency="medium",
        ),
        decision=DecisionPattern(
            style="保守",
            risk_tolerance="low",
            typical_questions=["ROI 是多少？", "风险敞口怎么算？"],
        ),
        interpersonal=InterpersonalStyle(
            authority_mode="正式",
            triggers=["情绪化论据"],
            emotion_states=["严肃", "怀疑"],
        ),
    )
    base.update(overrides)
    return Persona(**base)


# ---------------------------------------------------------------------------
# AC3: 5-layer ordering
# ---------------------------------------------------------------------------


def test_system_prompt_has_5_layers_in_order() -> None:
    p = _make_persona()
    system = build_system_prompt_v2(p)

    positions = [
        system.index("## Hard Rules"),
        system.index("## Identity"),
        system.index("## Expression"),
        system.index("## Decision"),
        system.index("## Interpersonal"),
    ]
    assert positions == sorted(positions), f"layers out of order: {positions}"


def test_system_prompt_includes_catchphrases() -> None:
    """AC6 prerequisite: Expression catchphrases must appear in system prompt."""
    p = _make_persona()
    system = build_system_prompt_v2(p)
    assert "数字会说话" in system
    assert "ROI 呢？" in system


# ---------------------------------------------------------------------------
# AC4: hostile section with hidden agenda + critical hard rules
# ---------------------------------------------------------------------------


def test_hidden_agenda_injected_with_do_not_expose_marker() -> None:
    p = _make_persona()
    system = build_system_prompt_v2(p)
    assert "对抗化字段" in system
    assert "不要在对话里直接说出来" in system
    assert "今年要裁员 15%" in system


def test_critical_hard_rule_in_hostile_block() -> None:
    p = _make_persona()
    system = build_system_prompt_v2(p)
    # hostile section must flag the critical rule (it appears both in Hard Rules
    # and the hostile block)
    assert "【critical 底线】预算超支必报" in system


def test_no_hostile_block_when_no_hidden_agenda_or_critical() -> None:
    p = _make_persona(
        hard_rules=[HardRule(statement="不接匿名请求", severity="medium")],
        identity=IdentityProfile(background="x", core_values=[], hidden_agenda=None),
    )
    system = build_system_prompt_v2(p)
    assert "对抗化字段" not in system


# ---------------------------------------------------------------------------
# Empty layers survive (no crash)
# ---------------------------------------------------------------------------


def test_empty_layers_omit_sections() -> None:
    p = Persona(
        id="bare",
        name="Bare",
        role="x",
        schema_version=2,
        hard_rules=[],
        identity=None,
        expression=None,
        decision=None,
        interpersonal=None,
    )
    system = build_system_prompt_v2(p)
    assert "Bare" in system
    # Core role-behavior block still present
    assert "层级行为约束" in system


# ---------------------------------------------------------------------------
# Compressed wrapper preserves layer content
# ---------------------------------------------------------------------------


def test_compressed_v2_preserves_system_prompt_and_history() -> None:
    p = _make_persona()
    history = [
        {"sender_type": "user", "sender_id": "user", "content": "预算怎么卡这么紧？"},
        {"sender_type": "persona", "sender_id": "cfo", "content": "数字会说话。"},
    ]
    system, messages = build_compressed_llm_messages_v2(persona=p, history=history)
    assert "数字会说话" in system  # catchphrase preserved
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_compressed_group_v2_labels_other_personas() -> None:
    p = _make_persona()
    history = [
        {"sender_type": "user", "sender_id": "user", "content": "你们怎么看？"},
        {"sender_type": "persona", "sender_id": "cto", "content": "技术没问题"},
        {"sender_type": "persona", "sender_id": "cfo", "content": "钱不够"},
    ]
    system, messages = build_compressed_group_llm_messages_v2(
        persona=p,
        persona_id="cfo",
        history=history,
        is_mentioned=True,
    )
    assert "@了你" in system  # is_mentioned hint appended
    # messages should label other personas distinctly
    assert any("其他角色 cto" in m["content"] for m in messages)
    # cfo's own message → assistant
    assert any(m["role"] == "assistant" and m["content"] == "钱不够" for m in messages)
