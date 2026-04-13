# input: application.services.stakeholder.adversarializer + domain Persona fixtures
# output: Story 2.4 apply_hostile / mark_hostile_fallback / prompt shape 单元测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.4 对抗化 pure function 单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.4 adversarializer pure functions and prompt contract (AC3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from application.ports.llm import LLMResponse
from application.services.stakeholder.adversarializer import (
    apply_hostile,
    invoke_adversarialize_llm,
    load_adversarialize_prompt,
    mark_hostile_fallback,
)
from application.services.stakeholder.persona_migrator import MigrationError
from domain.stakeholder.persona_entity import (
    DecisionPattern,
    Evidence,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)


def _base_persona() -> Persona:
    return Persona(
        id="boss",
        name="剑锋",
        role="上级",
        hard_rules=[HardRule(statement="禁止 quick-and-dirty", severity="high")],
        identity=IdentityProfile(
            background="直属上级",
            core_values=["结果导向"],
            hidden_agenda=None,
        ),
        expression=ExpressionStyle(
            tone="直接",
            catchphrases=["经得起推敲"],
            interruption_tendency="medium",
        ),
        decision=DecisionPattern(
            style="追因型",
            risk_tolerance="low",
            typical_questions=["为什么倒退？"],
        ),
        interpersonal=InterpersonalStyle(
            authority_mode="正式",
            triggers=["含糊"],
            emotion_states=["严肃"],
        ),
        evidence_citations=[
            Evidence(
                claim="追因",
                citations=["「为什么会出现倒退？」"],
                confidence=0.9,
                source_material_id="boss-markdown",
                layer="decision",
            )
        ],
        schema_version=2,
    )


def _hostile_payload() -> dict:
    return {
        "pressure_injection": {
            "interruption_tendency": "high",
            "escalation_triggers": ["用户让步", "含糊回答"],
            "silence_penalty": "立即点名追问",
        },
        "hidden_agenda_triggers": [
            {
                "agenda": "把延期责任推给团队",
                "surface_pretext": "关心交付风险",
                "leak_signal": "当团队提到历史延期",
            }
        ],
        "interruption_tendency": {
            "level": "high",
            "cue_phrases": ["等一下", "先别展开", "这个不是关键"],
            "topics_cut_off": ["技术细节", "历史复盘"],
        },
        "emotion_state_machine": {
            "default_state": "alert",
            "states": ["alert", "irritated", "confrontational"],
            "transitions": [
                {"from": "alert", "to": "irritated", "trigger": "用户让步"},
                {"from": "irritated", "to": "confrontational", "trigger": "时间节点模糊"},
            ],
        },
        "injected_evidences": [
            {
                "claim": "压迫感注入",
                "citations": ["adversarialize: pressure injection"],
                "confidence": 0.6,
                "source_material_id": "adversarialize",
                "layer": "interpersonal",
            },
            {
                "claim": "隐藏议程",
                "citations": ["adversarialize: hidden agenda"],
                "confidence": 0.55,
                "source_material_id": "adversarialize",
                "layer": "identity",
            },
        ],
    }


# ---------------------------------------------------------------------------
# AC3: prompt contract
# ---------------------------------------------------------------------------


def test_adversarialize_prompt_exists_and_has_4_rule_sections():
    prompt = load_adversarialize_prompt()
    assert "规则段 1" in prompt and "注入压迫感" in prompt
    assert "规则段 2" in prompt and "暴露隐藏议程触发器" in prompt
    assert "规则段 3" in prompt and "打断倾向" in prompt
    assert "规则段 4" in prompt and "情绪状态机" in prompt


def test_adversarialize_prompt_file_is_in_prompts_dir():
    path = (
        Path(__file__).resolve().parent.parent.parent
        / "application"
        / "services"
        / "stakeholder"
        / "prompts"
        / "adversarialize.md"
    )
    assert path.exists()


# ---------------------------------------------------------------------------
# apply_hostile: pure function
# ---------------------------------------------------------------------------


def test_apply_hostile_injects_hidden_agenda_when_baseline_empty():
    persona = _base_persona()
    out = apply_hostile(persona, _hostile_payload())
    assert out.identity is not None
    assert out.identity.hidden_agenda == "把延期责任推给团队"


def test_apply_hostile_appends_cue_phrases_to_expression():
    persona = _base_persona()
    out = apply_hostile(persona, _hostile_payload())
    assert "等一下" in out.expression.catchphrases
    assert "先别展开" in out.expression.catchphrases
    assert "经得起推敲" in out.expression.catchphrases  # baseline preserved


def test_apply_hostile_bumps_interruption_tendency():
    persona = _base_persona()
    persona.expression.interruption_tendency = "low"
    out = apply_hostile(persona, _hostile_payload())
    assert out.expression.interruption_tendency == "high"


def test_apply_hostile_adds_topics_and_escalations_to_triggers():
    persona = _base_persona()
    out = apply_hostile(persona, _hostile_payload())
    triggers = set(out.interpersonal.triggers)
    assert "含糊" in triggers  # baseline preserved
    assert "技术细节" in triggers  # from topics_cut_off
    assert "用户让步" in triggers  # from escalation_triggers


def test_apply_hostile_appends_emotion_states():
    persona = _base_persona()
    out = apply_hostile(persona, _hostile_payload())
    assert "severe" not in out.interpersonal.emotion_states
    assert "confrontational" in out.interpersonal.emotion_states
    assert "严肃" in out.interpersonal.emotion_states  # baseline preserved


def test_apply_hostile_appends_evidence_citations():
    persona = _base_persona()
    out = apply_hostile(persona, _hostile_payload())
    adversarialize_layers = [
        e.layer for e in out.evidence_citations if e.source_material_id == "adversarialize"
    ]
    assert len(adversarialize_layers) == 2


def test_apply_hostile_marks_source_materials():
    persona = _base_persona()
    out = apply_hostile(persona, _hostile_payload())
    assert "adversarialize" in out.source_materials


def test_apply_hostile_does_not_mutate_input():
    persona = _base_persona()
    original_catchphrases = list(persona.expression.catchphrases)
    _ = apply_hostile(persona, _hostile_payload())
    assert persona.expression.catchphrases == original_catchphrases


# ---------------------------------------------------------------------------
# mark_hostile_fallback
# ---------------------------------------------------------------------------


def test_mark_hostile_fallback_records_failure_source_marker():
    persona = _base_persona()
    out = mark_hostile_fallback(persona, "LLM returned non-JSON")
    assert "adversarialize:failed" in out.source_materials


def test_mark_hostile_fallback_appends_fallback_evidence():
    persona = _base_persona()
    out = mark_hostile_fallback(persona, "bad json line 1")
    fallback = [e for e in out.evidence_citations if e.source_material_id == "adversarialize"]
    assert len(fallback) == 1
    assert "bad json line 1" in fallback[0].citations[0]


# ---------------------------------------------------------------------------
# invoke_adversarialize_llm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_adversarialize_llm_happy_path():
    llm = AsyncMock()
    llm.generate.return_value = LLMResponse(content=json.dumps(_hostile_payload()), model="m")
    result = await invoke_adversarialize_llm(llm, _base_persona(), prompt="SYS")
    assert "pressure_injection" in result
    llm.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_invoke_adversarialize_llm_strips_code_fence():
    llm = AsyncMock()
    wrapped = f"```json\n{json.dumps(_hostile_payload())}\n```"
    llm.generate.return_value = LLMResponse(content=wrapped, model="m")
    result = await invoke_adversarialize_llm(llm, _base_persona(), prompt="SYS")
    assert "pressure_injection" in result


@pytest.mark.asyncio
async def test_invoke_adversarialize_llm_missing_keys_raises_MigrationError():
    llm = AsyncMock()
    llm.generate.return_value = LLMResponse(
        content=json.dumps({"pressure_injection": {}}), model="m"
    )
    with pytest.raises(MigrationError):
        await invoke_adversarialize_llm(llm, _base_persona(), prompt="SYS")


@pytest.mark.asyncio
async def test_invoke_adversarialize_llm_non_json_raises_MigrationError():
    llm = AsyncMock()
    llm.generate.return_value = LLMResponse(content="not json at all", model="m")
    with pytest.raises(MigrationError):
        await invoke_adversarialize_llm(llm, _base_persona(), prompt="SYS")
