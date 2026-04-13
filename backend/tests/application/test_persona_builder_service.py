# input: PersonaBuilderService + mock AgentSkillClient/LLM/repo/cache
# output: Story 2.4 AC1-AC8 核心集成测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.4 PersonaBuilderService 集成测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Integration tests for PersonaBuilderService (Story 2.4 AC1-AC8)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from unittest.mock import AsyncMock

import pytest

from application.ports.llm import LLMResponse
from application.services.stakeholder.build_events import (
    BUILD_ADVERSARIALIZE_DONE,
    BUILD_ADVERSARIALIZE_START,
    BUILD_ERROR,
    BUILD_PARSE_DONE,
    BUILD_PERSIST_DONE,
    BUILD_WORKSPACE_READY,
    BuildEvent,
)
from application.services.stakeholder.exceptions import (
    BuildError,
    BuildTimeoutError,
)
from application.services.stakeholder.persona_build_cache import PersonaBuildCache
from application.services.stakeholder.persona_builder_service import (
    PersonaBuilderService,
    ensure_evidence_completeness,
)
from domain.stakeholder.persona_entity import Persona


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PARSE_JSON = {
    "hard_rules": [{"statement": "禁止模糊承诺", "severity": "high"}],
    "identity": {
        "background": "直属上级",
        "core_values": ["交付"],
        "hidden_agenda": None,
    },
    "expression": {
        "tone": "直接",
        "catchphrases": ["经得起推敲"],
        "interruption_tendency": "medium",
    },
    "decision": {
        "style": "追因型",
        "risk_tolerance": "low",
        "typical_questions": ["为什么倒退？"],
    },
    "interpersonal": {
        "authority_mode": "正式",
        "triggers": ["含糊"],
        "emotion_states": ["严肃"],
    },
    "evidence_citations": [
        {
            "claim": "追因",
            "citations": ["「为什么会出现倒退？」"],
            "confidence": 0.9,
            "source_material_id": "agent-markdown",
            "layer": "decision",
        },
        {
            "claim": "雷区",
            "citations": ["「不要模糊承诺」"],
            "confidence": 0.8,
            "source_material_id": "agent-markdown",
            "layer": "hard_rules",
        },
    ],
}


_HOSTILE_JSON = {
    "pressure_injection": {
        "interruption_tendency": "high",
        "escalation_triggers": ["含糊回答"],
        "silence_penalty": "立即点名追问",
    },
    "hidden_agenda_triggers": [
        {
            "agenda": "把责任推给团队",
            "surface_pretext": "关心交付",
            "leak_signal": "提到历史延期",
        }
    ],
    "interruption_tendency": {
        "level": "high",
        "cue_phrases": ["等一下"],
        "topics_cut_off": ["技术细节"],
    },
    "emotion_state_machine": {
        "default_state": "alert",
        "states": ["alert", "confrontational"],
        "transitions": [{"from": "alert", "to": "confrontational", "trigger": "含糊"}],
    },
    "injected_evidences": [
        {
            "claim": "压迫感",
            "citations": ["adversarialize inject"],
            "confidence": 0.6,
            "source_material_id": "adversarialize",
            "layer": "interpersonal",
        }
    ],
}


class _FakeAgentEvent:
    def __init__(self, type_: str, payload: dict | None = None) -> None:
        self.type = type_
        self.payload = payload or {}


def _write_markdown(tmp: Path, content: str = "# Persona\n\nBody.") -> Path:
    ws = tmp / "ws"
    (ws / "output").mkdir(parents=True, exist_ok=True)
    (ws / "output" / "persona.md").write_text(content, encoding="utf-8")
    return ws


class _FakeAgentClient:
    """Produces a scripted agent event stream AND materializes workspace on disk."""

    def __init__(
        self,
        workspace_path: Path,
        *,
        tool_uses: int = 2,
        raise_on_iter: Optional[Exception] = None,
    ) -> None:
        self._ws = workspace_path
        self._tool_uses = tool_uses
        self._raise = raise_on_iter
        self.cleanup_invoked = False

    async def _generator(
        self, *, user_id: str, materials: list[str]
    ) -> AsyncIterator[_FakeAgentEvent]:
        # Simulate AgentSkillClient's own try/finally — cleanup flag set on exit
        try:
            yield _FakeAgentEvent(
                "workspace_ready",
                {"workspace_path": str(self._ws), "user_id": user_id},
            )
            for i in range(self._tool_uses):
                yield _FakeAgentEvent(
                    "tool_use", {"tool_uses": [{"name": "Read", "input": {"file": f"{i}"}}]}
                )
            if self._raise:
                raise self._raise
            yield _FakeAgentEvent("result", {"is_error": False})
        finally:
            self.cleanup_invoked = True

    def build_persona(self, *, user_id: str, materials: list[str]):
        return self._generator(user_id=user_id, materials=materials)


class _FakeRepo:
    def __init__(self) -> None:
        self.saved: list[Persona] = []

    async def save_structured_persona(self, persona: Persona) -> Persona:
        self.saved.append(persona)
        return persona


def _make_llm_chain(parse_json: dict, hostile_json: dict | Exception | str | None):
    """Sequence mock responses: first call = parse, second = adversarialize."""
    llm = AsyncMock()
    responses: list[Any] = [LLMResponse(content=json.dumps(parse_json), model="m")]

    if isinstance(hostile_json, Exception):
        responses.append(hostile_json)
    elif isinstance(hostile_json, str):
        responses.append(LLMResponse(content=hostile_json, model="m"))
    elif hostile_json is None:
        pass  # no second call expected
    else:
        responses.append(LLMResponse(content=json.dumps(hostile_json), model="m"))

    llm.generate.side_effect = responses
    return llm


def _make_service(
    *,
    agent: _FakeAgentClient,
    llm,
    repo: _FakeRepo,
    cache: Optional[PersonaBuildCache] = None,
    total_timeout_s: int = 30,
    post_timeout_s: int = 15,
) -> PersonaBuilderService:
    return PersonaBuilderService(
        agent_client=agent,
        llm=llm,
        repo=repo,
        cache=cache or PersonaBuildCache(redis=None),
        adversarialize_prompt="ADVERSARIALIZE_SYSTEM_PROMPT",
        parse_prompt="PARSE_SYSTEM_PROMPT",
        total_timeout_s=total_timeout_s,
        post_timeout_s=post_timeout_s,
    )


# ---------------------------------------------------------------------------
# AC1 + AC2: happy path produces 6 canonical events in order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_emits_six_canonical_event_sequence_happy_path(tmp_path):
    ws = _write_markdown(tmp_path)
    agent = _FakeAgentClient(ws, tool_uses=2)
    llm = _make_llm_chain(_PARSE_JSON, _HOSTILE_JSON)
    repo = _FakeRepo()
    service = _make_service(agent=agent, llm=llm, repo=repo)

    events: list[BuildEvent] = []
    async for ev in service.build(user_id="u1", materials=["m1", "m2"]):
        events.append(ev)

    types_in_order = [ev.type for ev in events]

    # AC2: all 6 canonical stages appear in the required order
    canonical = [
        BUILD_WORKSPACE_READY,
        BUILD_PARSE_DONE,
        BUILD_ADVERSARIALIZE_START,
        BUILD_ADVERSARIALIZE_DONE,
        BUILD_PERSIST_DONE,
    ]
    idx = -1
    for want in canonical:
        assert want in types_in_order, f"missing {want}"
        idx2 = types_in_order.index(want, idx + 1)
        assert idx2 > idx, f"{want} out of order"
        idx = idx2

    # agent_tool_use appears between workspace_ready and parse_done
    assert "agent_tool_use" in types_in_order

    # seq monotonically increasing
    seqs = [ev.seq for ev in events]
    assert seqs == sorted(seqs)


@pytest.mark.asyncio
async def test_build_persists_v2_persona_with_evidence_citations(tmp_path):
    """AC5: every 5-layer claim gets at least 1 evidence (synthetic if missing)."""
    ws = _write_markdown(tmp_path)
    agent = _FakeAgentClient(ws)
    llm = _make_llm_chain(_PARSE_JSON, _HOSTILE_JSON)
    repo = _FakeRepo()
    service = _make_service(agent=agent, llm=llm, repo=repo)

    async for _ in service.build(user_id="u1", materials=["m"]):
        pass

    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.schema_version == 2

    # Every layer that has claims must have at least one evidence backing it
    layers_with_claims = set()
    if saved.hard_rules:
        layers_with_claims.add("hard_rules")
    if saved.decision and saved.decision.typical_questions:
        layers_with_claims.add("decision")
    if saved.expression and saved.expression.catchphrases:
        layers_with_claims.add("expression")
    if saved.interpersonal and saved.interpersonal.triggers:
        layers_with_claims.add("interpersonal")

    evidence_layers = {e.layer for e in saved.evidence_citations}
    assert layers_with_claims.issubset(
        evidence_layers
    ), f"layers without evidence: {layers_with_claims - evidence_layers}"


# ---------------------------------------------------------------------------
# AC7: cache hit short-circuits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_cache_hit_short_circuits_and_yields_persist_done_only(tmp_path):
    class _PrePopulatedRedis:
        def __init__(self, stored: str):
            self._stored = stored

        async def get(self, key):
            return self._stored

        async def set(self, key, value, ttl=None):
            pass

    cache = PersonaBuildCache(redis=_PrePopulatedRedis("persona-cached-123"))

    ws = _write_markdown(tmp_path)
    agent = _FakeAgentClient(ws)
    llm = AsyncMock()
    repo = _FakeRepo()
    service = _make_service(agent=agent, llm=llm, repo=repo, cache=cache)

    events = []
    async for ev in service.build(user_id="u1", materials=["m"]):
        events.append(ev)

    assert len(events) == 1
    assert events[0].type == BUILD_PERSIST_DONE
    assert events[0].data["persona_id"] == "persona-cached-123"
    assert events[0].data["from_cache"] is True

    # LLM must NOT have been called
    llm.generate.assert_not_called()
    # repo must NOT have saved anything (cache short-circuit)
    assert repo.saved == []


# ---------------------------------------------------------------------------
# AC4: adversarialize downgrade when JSON is broken
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_adversarialize_bad_json_downgrades_not_raises(tmp_path):
    ws = _write_markdown(tmp_path)
    agent = _FakeAgentClient(ws)
    # Second LLM call returns non-JSON → adversarialize downgrade path
    llm = _make_llm_chain(_PARSE_JSON, "THIS IS NOT JSON")
    repo = _FakeRepo()
    service = _make_service(agent=agent, llm=llm, repo=repo)

    events = []
    async for ev in service.build(user_id="u1", materials=["m"]):
        events.append(ev)

    # AC4: persist still happens
    assert len(repo.saved) == 1
    # adversarialize_done payload has hostile_applied=False
    adv_done = [e for e in events if e.type == BUILD_ADVERSARIALIZE_DONE]
    assert len(adv_done) == 1
    assert adv_done[0].data["hostile_applied"] is False
    # persist_done also reflects downgrade
    persist_done = [e for e in events if e.type == BUILD_PERSIST_DONE]
    assert persist_done[-1].data["hostile_applied"] is False
    # Fallback marker recorded
    assert "adversarialize:failed" in repo.saved[0].source_materials


# ---------------------------------------------------------------------------
# AC6: total timeout → BuildTimeoutError + error event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_total_timeout_raises_BuildTimeoutError_with_error_event(tmp_path):
    ws = _write_markdown(tmp_path)

    class _SlowAgent:
        async def _gen(self, *, user_id, materials):
            try:
                yield _FakeAgentEvent("workspace_ready", {"workspace_path": str(ws)})
                await asyncio.sleep(5)  # longer than total_timeout_s=1
            finally:
                self.cleanup_invoked = True

        def __init__(self):
            self.cleanup_invoked = False

        def build_persona(self, *, user_id, materials):
            return self._gen(user_id=user_id, materials=materials)

    agent = _SlowAgent()
    llm = AsyncMock()
    repo = _FakeRepo()
    service = _make_service(agent=agent, llm=llm, repo=repo, total_timeout_s=1, post_timeout_s=1)

    events = []
    with pytest.raises(BuildTimeoutError):
        async for ev in service.build(user_id="u1", materials=["m"]):
            events.append(ev)

    # An error event was yielded before raising
    assert any(
        e.type == BUILD_ERROR and e.data.get("error_code") == "BUILD_TIMEOUT" for e in events
    )
    # Cleanup was invoked on the agent (try/finally in generator)
    assert agent.cleanup_invoked


# ---------------------------------------------------------------------------
# AC8: agent failure still triggers workspace cleanup (via agent generator's finally)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_failure_still_runs_generator_finally(tmp_path):
    ws = _write_markdown(tmp_path)
    agent = _FakeAgentClient(ws, raise_on_iter=RuntimeError("agent crash"))
    llm = AsyncMock()
    repo = _FakeRepo()
    service = _make_service(agent=agent, llm=llm, repo=repo)

    with pytest.raises(BuildError):
        async for _ in service.build(user_id="u1", materials=["m"]):
            pass

    # AgentSkillClient's try/finally block (modeled by _FakeAgentClient) ran
    assert agent.cleanup_invoked is True
    # Nothing persisted (agent never produced structured output path anyway)
    assert repo.saved == []


# ---------------------------------------------------------------------------
# AC1 signature sanity: build is an async generator
# ---------------------------------------------------------------------------


def test_build_is_async_generator_function():
    import inspect

    assert inspect.isasyncgenfunction(PersonaBuilderService.build)


# ---------------------------------------------------------------------------
# ensure_evidence_completeness helper
# ---------------------------------------------------------------------------


def test_ensure_evidence_completeness_adds_synthetic_evidences_for_missing_layers():
    from domain.stakeholder.persona_entity import (
        DecisionPattern,
        Evidence,
        ExpressionStyle,
        HardRule,
        IdentityProfile,
        InterpersonalStyle,
    )

    p = Persona(
        id="p",
        name="p",
        role="r",
        hard_rules=[HardRule(statement="x", severity="medium")],
        identity=IdentityProfile(background="b", core_values=["c"]),
        expression=ExpressionStyle(tone="t", catchphrases=["hi"]),
        decision=DecisionPattern(style="s", typical_questions=["q"]),
        interpersonal=InterpersonalStyle(authority_mode="a", triggers=["trig"]),
        evidence_citations=[
            Evidence(
                claim="x",
                citations=["c"],
                confidence=0.9,
                source_material_id="m",
                layer="hard_rules",
            ),
        ],
        schema_version=2,
    )
    out = ensure_evidence_completeness(p)
    layers = {e.layer for e in out.evidence_citations}
    # All 5 layers covered
    assert layers >= {"hard_rules", "identity", "expression", "decision", "interpersonal"}
