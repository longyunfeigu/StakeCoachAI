# input: Persona (domain), LLMPort, adversarialize prompt markdown
# output: apply_hostile, mark_hostile_fallback, load_adversarialize_prompt, invoke_adversarialize_llm — 对抗化合成 + LLM 调用 + 降级
# owner: wanhua.gu
# pos: 应用层 - persona 对抗化后处理（注入压迫感/隐藏议程/打断倾向/情绪状态机）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Adversarial persona enhancer: injects pressure / hidden agenda / interruption / emotion state machine.

Pure functions (``apply_hostile``, ``mark_hostile_fallback``) have no I/O and
are safe to unit-test without mocks. ``invoke_adversarialize_llm`` wraps a
single LLM call + JSON parse.

Hostile metadata is stored on the Persona via a helper flag encoded in
``source_materials`` and via mutation of the 5 layers. The persistence
metadata key ``_metadata.hostile_applied`` is written only at persist time
(in PersonaBuilderService) because domain Persona has no metadata dict.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.persona_migrator import (
    MigrationError,
    parse_llm_json,
)
from core.logging_config import get_logger
from domain.stakeholder.persona_entity import Evidence, Persona

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "adversarialize.md"

_ADVERSARIALIZE_SOURCE_ID = "adversarialize"


__all__ = [
    "apply_hostile",
    "invoke_adversarialize_llm",
    "load_adversarialize_prompt",
    "mark_hostile_fallback",
]


def load_adversarialize_prompt() -> str:
    """Load the adversarialize system prompt from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _clamp_level(current: str, proposed: str) -> str:
    """Keep interruption_tendency at max(current, proposed) on an ordinal scale."""
    order = {"low": 0, "medium": 1, "high": 2}
    cur = order.get(current, 1)
    prop = order.get(proposed, 1)
    return {0: "low", 1: "medium", 2: "high"}[max(cur, prop)]


def apply_hostile(persona: Persona, hostile: dict[str, Any]) -> Persona:
    """Merge adversarial injection from LLM JSON into a baseline persona.

    Mutations (copy-on-write):
    - identity.hidden_agenda ← first hostile.hidden_agenda_triggers[].agenda if baseline empty
    - interpersonal.triggers += hostile.interruption_tendency.topics_cut_off
    - interpersonal.emotion_states += hostile.emotion_state_machine.states
    - expression.catchphrases += hostile.interruption_tendency.cue_phrases (dedup)
    - expression.interruption_tendency = max(current, hostile.interruption_tendency.level)
    - evidence_citations += [Evidence(...) for each injected_evidences]
    - source_materials += ["adversarialize"]
    """
    if not isinstance(hostile, dict):
        raise ValueError("hostile payload must be a dict")

    pressure = hostile.get("pressure_injection") or {}
    hidden_agenda = hostile.get("hidden_agenda_triggers") or []
    interruption = hostile.get("interruption_tendency") or {}
    emotion = hostile.get("emotion_state_machine") or {}
    injected = hostile.get("injected_evidences") or []

    # Start from a deep copy so the input persona is never mutated
    new_hard_rules = copy.deepcopy(persona.hard_rules)
    new_evidences = list(persona.evidence_citations)

    # --- identity ---
    new_identity = copy.deepcopy(persona.identity) if persona.identity else None
    if new_identity is not None and not (new_identity.hidden_agenda or "").strip():
        if hidden_agenda:
            first = hidden_agenda[0] or {}
            new_identity.hidden_agenda = first.get("agenda") or None

    # --- expression ---
    new_expression = copy.deepcopy(persona.expression) if persona.expression else None
    if new_expression is not None:
        cue_phrases = interruption.get("cue_phrases") or []
        existing_cp = set(new_expression.catchphrases)
        for cp in cue_phrases:
            if cp and cp not in existing_cp:
                new_expression.catchphrases.append(cp)
                existing_cp.add(cp)
        # bump interruption_tendency to max(current, proposed)
        proposed_level = interruption.get("level") or pressure.get("interruption_tendency")
        if proposed_level:
            new_expression.interruption_tendency = _clamp_level(
                new_expression.interruption_tendency, proposed_level
            )

    # --- decision (untouched, adversarial doesn't rewrite decision-making) ---
    new_decision = copy.deepcopy(persona.decision) if persona.decision else None

    # --- interpersonal ---
    new_interpersonal = copy.deepcopy(persona.interpersonal) if persona.interpersonal else None
    if new_interpersonal is not None:
        topics_cut_off = interruption.get("topics_cut_off") or []
        existing_triggers = set(new_interpersonal.triggers)
        for t in topics_cut_off:
            if t and t not in existing_triggers:
                new_interpersonal.triggers.append(t)
                existing_triggers.add(t)
        # Escalation triggers also count as interpersonal triggers
        for t in pressure.get("escalation_triggers") or []:
            if t and t not in existing_triggers:
                new_interpersonal.triggers.append(t)
                existing_triggers.add(t)
        emotion_states = emotion.get("states") or []
        existing_states = set(new_interpersonal.emotion_states)
        for s in emotion_states:
            if s and s not in existing_states:
                new_interpersonal.emotion_states.append(s)
                existing_states.add(s)

    # --- evidences ---
    for ev_data in injected:
        if not isinstance(ev_data, dict):
            continue
        try:
            new_evidences.append(Evidence(**ev_data))
        except Exception as exc:  # pragma: no cover - defensive; validation handled by domain
            logger.warning(
                "adversarialize_evidence_skip",
                error=str(exc),
                evidence=ev_data,
            )

    # --- source materials ---
    new_sources = list(persona.source_materials)
    if _ADVERSARIALIZE_SOURCE_ID not in new_sources:
        new_sources.append(_ADVERSARIALIZE_SOURCE_ID)

    return replace(
        persona,
        hard_rules=new_hard_rules,
        identity=new_identity,
        expression=new_expression,
        decision=new_decision,
        interpersonal=new_interpersonal,
        evidence_citations=new_evidences,
        source_materials=new_sources,
    )


def mark_hostile_fallback(persona: Persona, warning: str) -> Persona:
    """Mark a persona as 'adversarialization attempted but failed'.

    Encodes the fallback state in ``source_materials`` (visible path) since
    domain Persona lacks a free-form metadata dict. Callers (e.g.
    PersonaBuilderService) can additionally write ``structured_profile._metadata.hostile_applied``
    at persist time.
    """
    new_sources = list(persona.source_materials)
    marker = f"{_ADVERSARIALIZE_SOURCE_ID}:failed"
    if marker not in new_sources:
        new_sources.append(marker)
    # Best-effort: stash warning in a synthetic "evidence" so humans can see it
    try:
        fallback_ev = Evidence(
            claim=f"adversarialization skipped: {warning[:80]}",
            citations=[warning[:500]],
            confidence=0.1,
            source_material_id=_ADVERSARIALIZE_SOURCE_ID,
            layer="interpersonal",
        )
    except Exception:  # pragma: no cover
        fallback_ev = None

    new_evidences = list(persona.evidence_citations)
    if fallback_ev is not None:
        new_evidences.append(fallback_ev)

    return replace(
        persona,
        source_materials=new_sources,
        evidence_citations=new_evidences,
    )


async def invoke_adversarialize_llm(
    llm: LLMPort,
    persona: Persona,
    prompt: str,
    *,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Call the LLM with the adversarialize prompt and parse its JSON output.

    Raises ``MigrationError`` (reused from persona_migrator) on invalid JSON /
    missing top-level keys — callers handle by falling back to
    ``mark_hostile_fallback``.
    """
    persona_digest = _serialize_persona_for_prompt(persona)
    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(role="user", content=persona_digest),
    ]
    response = await llm.generate(messages, model=model, temperature=0.3)

    data = (
        json.loads(_strip_fence(response.content))
        if response.content.strip().startswith("```")
        else _safe_json(response.content)
    )

    required = {
        "pressure_injection",
        "hidden_agenda_triggers",
        "interruption_tendency",
        "emotion_state_machine",
    }
    missing = required - set(data.keys())
    if missing:
        raise MigrationError(f"adversarialize response missing keys: {sorted(missing)}")
    return data


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _safe_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        # Fall through to persona_migrator-style normalization
        return parse_llm_json(raw)


def _serialize_persona_for_prompt(persona: Persona) -> str:
    """Compact JSON rendering of the 5 layers for the adversarialize LLM prompt."""
    from dataclasses import asdict

    payload = {
        "id": persona.id,
        "name": persona.name,
        "role": persona.role,
        "hard_rules": [asdict(r) for r in persona.hard_rules],
        "identity": asdict(persona.identity) if persona.identity else None,
        "expression": asdict(persona.expression) if persona.expression else None,
        "decision": asdict(persona.decision) if persona.decision else None,
        "interpersonal": asdict(persona.interpersonal) if persona.interpersonal else None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
