# input: persona_migrator pure functions + migrate_one + migrate_personas_to_v2 script
# output: Story 2.3 AC1-AC6 pure-function 与脚本编排测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.3 旧 persona 迁移 migrator 与 CLI 脚本测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.3: persona migrator pure functions + CLI orchestration.

Covers AC1 (idempotent), AC2 (LLM→5-layer JSON),
AC4 (failure isolation), AC5 (--dry-run), AC6 (summary report).
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock

import pytest

from domain.common.exceptions import DomainValidationException
from domain.stakeholder.persona_entity import Persona


# ---------------------------------------------------------------------------
# Fixtures: canonical v2 LLM response (5-layer JSON)
# ---------------------------------------------------------------------------


def _canonical_llm_json(persona_id: str = "boss") -> dict:
    """Return a well-formed 5-layer JSON as an LLM would ideally produce."""
    return {
        "hard_rules": [
            {"statement": "禁止 quick-and-dirty 修复", "severity": "high"},
        ],
        "identity": {
            "background": "直属上级 / 销售导向",
            "core_values": ["用户视角", "方法论严谨"],
            "hidden_agenda": None,
        },
        "expression": {
            "tone": "直接、强势、不耐烦",
            "catchphrases": ["你们都 mute 了", "经得起推敲"],
            "interruption_tendency": "high",
        },
        "decision": {
            "style": "追因型、当场拍板",
            "risk_tolerance": "low",
            "typical_questions": ["为什么会出现倒退？", "SOP 是什么？"],
        },
        "interpersonal": {
            "authority_mode": "正式高压",
            "triggers": ["细节发散", "模糊承诺"],
            "emotion_states": ["严肃", "不满"],
        },
        "evidence_citations": [
            {
                "claim": "要求方法论经得起推敲",
                "citations": ["「这一段的话可能后面我们要琢磨一下如何能够经得起推敲」"],
                "confidence": 0.9,
                "source_material_id": f"{persona_id}-markdown",
                "layer": "hard_rules",
            },
            {
                "claim": "追因型",
                "citations": ["「为什么会出现倒退？」"],
                "confidence": 0.9,
                "source_material_id": f"{persona_id}-markdown",
                "layer": "decision",
            },
        ],
    }


def _canonical_v1_persona(persona_id: str = "boss") -> Persona:
    return Persona(
        id=persona_id,
        name="剑锋",
        role="直属上级 / Lu Jianfeng",
        avatar_color="#cc3300",
        profile_summary="销售导向",
        voice_id="male-qn-qingse",
        voice_speed=1.0,
        voice_style="Speak with authority",
    )


# ---------------------------------------------------------------------------
# parse_llm_json: pure function
# ---------------------------------------------------------------------------


def test_parse_llm_json_accepts_plain_json():
    from application.services.stakeholder.persona_migrator import parse_llm_json

    raw = json.dumps(_canonical_llm_json())
    data = parse_llm_json(raw)
    assert "hard_rules" in data
    assert "evidence_citations" in data


def test_parse_llm_json_strips_markdown_fence():
    from application.services.stakeholder.persona_migrator import parse_llm_json

    payload = json.dumps(_canonical_llm_json())
    raw = f"```json\n{payload}\n```"
    data = parse_llm_json(raw)
    assert data["identity"]["background"] == "直属上级 / 销售导向"


def test_parse_llm_json_strips_generic_fence():
    from application.services.stakeholder.persona_migrator import parse_llm_json

    payload = json.dumps(_canonical_llm_json())
    raw = f"```\n{payload}\n```"
    data = parse_llm_json(raw)
    assert "identity" in data


def test_parse_llm_json_rejects_non_json():
    from application.services.stakeholder.persona_migrator import (
        MigrationError,
        parse_llm_json,
    )

    with pytest.raises(MigrationError):
        parse_llm_json("this is not json at all")


def test_parse_llm_json_rejects_missing_required_keys():
    from application.services.stakeholder.persona_migrator import (
        MigrationError,
        parse_llm_json,
    )

    bad = json.dumps({"hard_rules": []})  # missing identity/expression/...
    with pytest.raises(MigrationError):
        parse_llm_json(bad)


# ---------------------------------------------------------------------------
# build_persona_v2: pure function
# ---------------------------------------------------------------------------


def test_build_persona_v2_preserves_v1_fields():
    from application.services.stakeholder.persona_migrator import build_persona_v2

    v1 = _canonical_v1_persona()
    v2 = build_persona_v2(v1, _canonical_llm_json())

    assert v2.id == v1.id
    assert v2.name == v1.name
    assert v2.role == v1.role
    assert v2.avatar_color == v1.avatar_color
    assert v2.voice_id == v1.voice_id
    assert v2.voice_speed == v1.voice_speed
    assert v2.voice_style == v1.voice_style


def test_build_persona_v2_populates_all_five_layers():
    from application.services.stakeholder.persona_migrator import build_persona_v2

    v2 = build_persona_v2(_canonical_v1_persona(), _canonical_llm_json())
    assert len(v2.hard_rules) >= 1
    assert v2.identity is not None
    assert v2.expression is not None
    assert v2.decision is not None
    assert v2.interpersonal is not None
    assert len(v2.evidence_citations) == 2


def test_build_persona_v2_rejects_invalid_evidence_layer():
    """AC4 failure path: evidence with bad layer → DomainValidationException bubbles up."""
    from application.services.stakeholder.persona_migrator import build_persona_v2

    bad = _canonical_llm_json()
    bad["evidence_citations"][0]["layer"] = "nonsense"

    with pytest.raises(DomainValidationException):
        build_persona_v2(_canonical_v1_persona(), bad)


# ---------------------------------------------------------------------------
# migrate_one: async orchestration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrate_one_dry_run_returns_skipped_and_does_not_call_llm():
    """AC5: --dry-run does not call LLM."""
    from application.services.stakeholder.persona_migrator import migrate_one

    llm = AsyncMock()
    v1 = _canonical_v1_persona()
    result = await migrate_one(v1, llm, prompt="whatever", dry_run=True)

    assert result.status == "dry_run"
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_one_success_returns_v2_persona():
    from application.services.stakeholder.persona_migrator import migrate_one
    from application.ports.llm import LLMResponse

    llm = AsyncMock()
    llm.generate.return_value = LLMResponse(
        content=json.dumps(_canonical_llm_json()),
        model="claude-opus",
    )

    v1 = _canonical_v1_persona()
    result = await migrate_one(v1, llm, prompt="SYSTEM_PROMPT", dry_run=False)

    assert result.status == "migrated"
    assert result.persona is not None
    assert result.persona.hard_rules  # v2 has structured data
    llm.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_migrate_one_llm_exception_raises_migration_error():
    from application.services.stakeholder.persona_migrator import (
        MigrationError,
        migrate_one,
    )

    llm = AsyncMock()
    llm.generate.side_effect = TimeoutError("api unreachable")

    with pytest.raises(MigrationError):
        await migrate_one(_canonical_v1_persona(), llm, prompt="x", dry_run=False)


@pytest.mark.asyncio
async def test_migrate_one_invalid_json_raises_migration_error():
    from application.services.stakeholder.persona_migrator import (
        MigrationError,
        migrate_one,
    )
    from application.ports.llm import LLMResponse

    llm = AsyncMock()
    llm.generate.return_value = LLMResponse(content="not json", model="m")

    with pytest.raises(MigrationError):
        await migrate_one(_canonical_v1_persona(), llm, prompt="x", dry_run=False)


# ---------------------------------------------------------------------------
# CLI script orchestration: run_migration
# ---------------------------------------------------------------------------


@dataclass
class _SaveCall:
    persona: Persona


class _FakeRepo:
    """In-memory fake repository that satisfies StakeholderPersonaRepository for the script."""

    def __init__(self, initial: Optional[list[Persona]] = None) -> None:
        self._by_id: dict[str, Persona] = {p.id: p for p in (initial or [])}
        self.save_calls: list[_SaveCall] = []

    async def save_structured_persona(self, persona: Persona) -> Persona:
        self._by_id[persona.id] = persona
        self.save_calls.append(_SaveCall(persona=persona))
        return persona

    async def get_by_id(self, persona_id: str) -> Optional[Persona]:
        return self._by_id.get(persona_id)

    async def list_all(self) -> list[Persona]:
        return list(self._by_id.values())

    # conform to ABC
    async def get_with_evidence(self, persona_id: str):  # pragma: no cover - unused
        p = self._by_id.get(persona_id)
        return (p, list(p.evidence_citations)) if p else None


@pytest.mark.asyncio
async def test_script_idempotent_skips_already_structured():
    """AC1: already-structured personas are skipped; LLM not called for them."""
    from application.services.stakeholder.persona_migrator import build_persona_v2, run_migration

    v2_already = build_persona_v2(
        _canonical_v1_persona("done"),
        _canonical_llm_json("done"),
    )
    v1 = _canonical_v1_persona("fresh")
    repo = _FakeRepo(initial=[v2_already, v1])
    llm = AsyncMock()
    from application.ports.llm import LLMResponse

    llm.generate.return_value = LLMResponse(
        content=json.dumps(_canonical_llm_json("fresh")), model="m"
    )

    report = await run_migration(
        repo=repo,
        llm=llm,
        disk_personas=[],
        prompt="p",
        dry_run=False,
    )

    assert report.skipped == 1
    assert report.migrated == 1
    assert report.failed == 0
    # LLM called once for v1 "fresh", zero times for already-structured "done"
    assert llm.generate.await_count == 1


@pytest.mark.asyncio
async def test_script_dry_run_does_not_call_llm_or_save():
    """AC5: --dry-run does not call LLM or save."""
    from application.services.stakeholder.persona_migrator import run_migration

    v1 = _canonical_v1_persona()
    repo = _FakeRepo()
    llm = AsyncMock()

    report = await run_migration(
        repo=repo,
        llm=llm,
        disk_personas=[v1],
        prompt="p",
        dry_run=True,
    )

    llm.generate.assert_not_called()
    assert repo.save_calls == []
    assert report.migrated == 0
    assert report.skipped == 1  # dry-run items count as skipped


@pytest.mark.asyncio
async def test_script_one_failure_does_not_block_others():
    """AC4: 1 failure does not stop others; failure recorded."""
    from application.ports.llm import LLMResponse
    from application.services.stakeholder.persona_migrator import run_migration

    personas = [_canonical_v1_persona(f"p{i}") for i in range(5)]
    repo = _FakeRepo()

    # Second call fails with non-JSON; others succeed
    responses = [
        LLMResponse(content=json.dumps(_canonical_llm_json("p0")), model="m"),
        LLMResponse(content="BROKEN NOT JSON", model="m"),
        LLMResponse(content=json.dumps(_canonical_llm_json("p2")), model="m"),
        LLMResponse(content=json.dumps(_canonical_llm_json("p3")), model="m"),
        LLMResponse(content=json.dumps(_canonical_llm_json("p4")), model="m"),
    ]
    llm = AsyncMock()
    llm.generate.side_effect = responses

    report = await run_migration(
        repo=repo,
        llm=llm,
        disk_personas=personas,
        prompt="p",
        dry_run=False,
    )

    assert report.migrated == 4
    assert report.failed == 1
    assert report.skipped == 0
    # Other 4 were saved as v2
    saved_ids = {call.persona.id for call in repo.save_calls}
    assert saved_ids == {"p0", "p2", "p3", "p4"}


@pytest.mark.asyncio
async def test_script_report_format_matches_spec(capsys):
    """AC6: stdout contains 'Migrated: N, Failed: M, Skipped: K'."""
    from application.ports.llm import LLMResponse
    from application.services.stakeholder.persona_migrator import (
        print_report,
        run_migration,
    )

    personas = [_canonical_v1_persona(f"p{i}") for i in range(5)]
    llm = AsyncMock()
    llm.generate.side_effect = [
        LLMResponse(content=json.dumps(_canonical_llm_json(f"p{i}")), model="m") for i in range(5)
    ]
    repo = _FakeRepo()

    report = await run_migration(
        repo=repo, llm=llm, disk_personas=personas, prompt="p", dry_run=False
    )
    print_report(report)
    captured = capsys.readouterr().out
    assert "Migrated: 5" in captured
    assert "Failed: 0" in captured
    assert "Skipped: 0" in captured


@pytest.mark.asyncio
async def test_script_migrates_five_personas():
    """AC2: 5 预置 persona 全部迁移成功 (mock LLM)."""
    from application.ports.llm import LLMResponse
    from application.services.stakeholder.persona_migrator import run_migration

    ids = ["boss", "cfo", "cto", "pm", "teamlead"]
    personas = [_canonical_v1_persona(pid) for pid in ids]
    llm = AsyncMock()
    llm.generate.side_effect = [
        LLMResponse(content=json.dumps(_canonical_llm_json(pid)), model="m") for pid in ids
    ]
    repo = _FakeRepo()

    report = await run_migration(
        repo=repo, llm=llm, disk_personas=personas, prompt="p", dry_run=False
    )

    assert report.migrated == 5
    assert report.failed == 0
    saved_ids = {call.persona.id for call in repo.save_calls}
    assert saved_ids == set(ids)
    for call in repo.save_calls:
        assert call.persona.hard_rules  # structured v2 data present
