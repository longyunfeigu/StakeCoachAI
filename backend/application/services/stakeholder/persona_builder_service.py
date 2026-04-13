# input: AgentSkillClient, LLMPort, StakeholderPersonaRepository, PersonaBuildCache, 两个 prompt 字符串
# output: PersonaBuilderService.build(user_id, materials, ...) -> AsyncIterator[BuildEvent]；Story 2.4 核心编排服务
# owner: wanhua.gu
# pos: 应用层 - persona 构建主编排服务（agent + parse + adversarialize + persist + 幂等缓存 + 240s 总超时）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""PersonaBuilderService — Story 2.4 orchestration.

Pipeline:
    cache_check → agent_stream → read markdown → parse→v2 JSON → adversarialize
    (or downgrade) → evidence补全 → persist → cache_set

Emits BuildEvent envelopes. Respects 240s total timeout; adversarialize
failure is downgraded (hostile_applied=False) rather than raised. Workspace
cleanup is delegated to AgentSkillClient (try/finally already in place there).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.adversarializer import (
    apply_hostile,
    invoke_adversarialize_llm,
    mark_hostile_fallback,
)
from application.services.stakeholder.build_events import (
    BUILD_ADVERSARIALIZE_DONE,
    BUILD_ADVERSARIALIZE_START,
    BUILD_AGENT_MESSAGE,
    BUILD_AGENT_TOOL_USE,
    BUILD_ENHANCEMENT_MERGE,
    BUILD_ENHANCEMENT_START,
    BUILD_ERROR,
    BUILD_PARSE_DONE,
    BUILD_PERSIST_DONE,
    BUILD_WORKSPACE_READY,
    BuildEvent,
)
from application.services.stakeholder.exceptions import BuildError, BuildTimeoutError
from application.services.stakeholder.persona_build_cache import (
    PersonaBuildCache,
    build_cache_key,
)
from application.services.stakeholder.persona_migrator import (
    MigrationError,
    build_persona_v2,
    parse_llm_json,
)
from core.logging_config import get_logger
from domain.stakeholder.persona_entity import Evidence, Persona

logger = get_logger(__name__)

_AGENT_OUTPUT_FILE = "output/persona.md"
_DEFAULT_TOTAL_TIMEOUT_S = 900
_DEFAULT_POST_TIMEOUT_S = 180

# Map known prompt file stems to user-facing phase descriptions.
_PROMPT_PHASE_MAP: dict[str, str] = {
    "intake": "收集基础信息",
    "work_analyzer": "分析工作模式",
    "persona_analyzer": "分析性格特征",
    "work_builder": "构建工作画像",
    "persona_builder": "构建人格画像",
    "merger": "合并画像",
    "correction_handler": "校正与修正",
}


def _infer_phase(tool_uses: list[dict]) -> Optional[str]:
    """Extract a human-readable phase name from tool_use inputs.

    Checks Read/Write file paths for known prompt stems or material patterns.
    Returns None when no recognizable pattern is found.
    """
    for tu in tool_uses:
        name = tu.get("name", "")
        inp = tu.get("input") or {}
        path = inp.get("file_path", "") or inp.get("path", "")

        if name == "Read" and "materials/" in path:
            return "读取素材"
        if name == "Write" and "output/" in path:
            return "写出最终画像"
        if name == "Skill":
            skill = inp.get("skill", "")
            return f"启动 {skill} 技能" if skill else "启动技能"

        # Match prompt file names
        for stem, label in _PROMPT_PHASE_MAP.items():
            if stem in path:
                return label
    return None


def _summarize_text(text: str, max_len: int = 80) -> str:
    """Extract the first meaningful line from agent text as a short summary."""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "---", "```", ">")):
            return line[:max_len] + ("…" if len(line) > max_len else "")
    return text[:max_len]


def _serialize_existing_for_merge(persona: Persona) -> str:
    """Serialize existing persona to JSON for merge context."""
    from dataclasses import asdict
    import json

    payload = {
        "name": persona.name,
        "role": persona.role,
        "hard_rules": [asdict(r) for r in persona.hard_rules],
        "identity": asdict(persona.identity) if persona.identity else None,
        "expression": asdict(persona.expression) if persona.expression else None,
        "decision": asdict(persona.decision) if persona.decision else None,
        "interpersonal": asdict(persona.interpersonal) if persona.interpersonal else None,
        "evidence_citations": [asdict(e) for e in persona.evidence_citations],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _merge_evidence(new_persona: Persona, existing: Persona) -> Persona:
    """Merge existing evidence into new persona, deduplicating by claim."""
    from dataclasses import replace

    existing_claims = {e.claim for e in new_persona.evidence_citations}
    merged = list(new_persona.evidence_citations)
    for e in existing.evidence_citations:
        if e.claim not in existing_claims:
            merged.append(e)
            existing_claims.add(e.claim)
    merged_sources = list(new_persona.source_materials)
    for s in existing.source_materials:
        if s not in merged_sources:
            merged_sources.append(s)
    return replace(new_persona, evidence_citations=merged, source_materials=merged_sources)


# Each 5-layer slot we must guarantee has ≥1 evidence backing
_LAYER_NAMES: tuple[str, ...] = (
    "hard_rules",
    "identity",
    "expression",
    "decision",
    "interpersonal",
)


class PersonaBuilderService:
    """Orchestrate agent-driven persona construction with streaming events."""

    def __init__(
        self,
        *,
        agent_client,
        llm: LLMPort,
        repo,
        cache: Optional[PersonaBuildCache] = None,
        adversarialize_prompt: str,
        parse_prompt: str,
        total_timeout_s: int = _DEFAULT_TOTAL_TIMEOUT_S,
        post_timeout_s: int = _DEFAULT_POST_TIMEOUT_S,
    ) -> None:
        self._agent = agent_client
        self._llm = llm
        self._repo = repo
        self._cache = cache or PersonaBuildCache(redis=None)
        self._adversarialize_prompt = adversarialize_prompt
        self._parse_prompt = parse_prompt
        self._total_timeout_s = total_timeout_s
        self._post_timeout_s = post_timeout_s

    async def build(
        self,
        *,
        user_id: str,
        materials: list[str],
        name: Optional[str] = None,
        role: Optional[str] = None,
        target_persona_id: Optional[str] = None,
    ) -> AsyncIterator[BuildEvent]:
        """Yield BuildEvents as the persona is built.

        Raises BuildTimeoutError on total 240s overrun; BuildError on any other
        orchestration failure. Adversarialize JSON failures are downgraded
        inline — they do NOT raise.
        """
        seq = 0

        def _emit(type_: str, **data) -> BuildEvent:
            nonlocal seq
            seq += 1
            return BuildEvent(seq=seq, type=type_, ts=time.time(), data=data)

        # AC7: idempotent cache check (BEFORE any LLM call)
        cache_key = build_cache_key(user_id, materials, persona_id=target_persona_id)
        cached_pid = await self._cache.get(cache_key)
        if cached_pid:
            logger.info("persona_build_cache_hit", user_id=user_id, persona_id=cached_pid)
            yield _emit(
                BUILD_PERSIST_DONE,
                persona_id=cached_pid,
                hostile_applied=True,  # assume previously successful
                from_cache=True,
            )
            return

        # Enhancement mode: load existing persona if target_persona_id is provided
        existing_persona: Optional[Persona] = None
        if target_persona_id:
            existing_persona = await self._repo.get_by_id(target_persona_id)

        t0 = time.perf_counter()
        workspace_path: Optional[Path] = None

        try:
            async with asyncio.timeout(self._total_timeout_s):
                existing_profile_str = (
                    _serialize_existing_for_merge(existing_persona)
                    if existing_persona
                    else None
                )
                agent_stream = self._agent.build_persona(
                    user_id=user_id,
                    materials=materials,
                    target_name=name,
                    target_role=role,
                    existing_profile=existing_profile_str,
                )

                # Enhancement mode: emit start event before agent stream
                if existing_persona:
                    yield _emit(BUILD_ENHANCEMENT_START, persona_id=target_persona_id)

                # Phase: workspace_ready + agent_tool_use relay
                async for agent_ev in agent_stream:
                    ev_type = getattr(agent_ev, "type", None)
                    payload = getattr(agent_ev, "payload", {}) or {}

                    if ev_type == "workspace_ready":
                        wp = payload.get("workspace_path")
                        if wp:
                            workspace_path = Path(wp)
                        yield _emit(
                            BUILD_WORKSPACE_READY,
                            user_id=user_id,
                            workspace_path=str(workspace_path) if workspace_path else None,
                        )
                    elif ev_type == "tool_use":
                        tool_uses = payload.get("tool_uses") or []
                        yield _emit(
                            BUILD_AGENT_TOOL_USE,
                            tool_uses=tool_uses,
                            phase=_infer_phase(tool_uses),
                        )
                    elif ev_type == "assistant_text":
                        text = (payload.get("text") or "").strip()
                        if text:
                            yield _emit(
                                BUILD_AGENT_MESSAGE,
                                text=text,
                                summary=_summarize_text(text),
                            )
                    # system / tool_result / result → suppress

                # Agent finished: read its output
                markdown = self._read_agent_output(workspace_path)

                # Phase: parse_done
                async with asyncio.timeout(self._post_timeout_s):
                    llm_json = await self._parse_markdown_to_json(
                        markdown, existing_persona=existing_persona
                    )

                # Back-fill name/role from LLM extraction when user left them blank
                resolved_name = name or llm_json.get("name") or None
                resolved_role = role or llm_json.get("role") or None
                persona_id = target_persona_id or _synthesize_persona_id(
                    resolved_name or user_id
                )
                v2 = build_persona_v2(
                    _build_v1_shell(
                        persona_id=persona_id,
                        name=resolved_name,
                        role=resolved_role,
                        markdown=markdown,
                    ),
                    llm_json,
                )
                yield _emit(
                    BUILD_PARSE_DONE,
                    persona_id=v2.id,
                    claims=_count_claims(v2),
                )

                # Phase: adversarialize_start / adversarialize_done
                yield _emit(BUILD_ADVERSARIALIZE_START)
                hostile_applied = True
                warning_msg: Optional[str] = None
                try:
                    async with asyncio.timeout(self._post_timeout_s):
                        hostile_json = await invoke_adversarialize_llm(
                            self._llm, v2, self._adversarialize_prompt
                        )
                    v2 = apply_hostile(v2, hostile_json)
                except (MigrationError, ValueError) as exc:  # AC4: downgrade
                    hostile_applied = False
                    warning_msg = str(exc)
                    v2 = mark_hostile_fallback(v2, warning_msg)
                    logger.warning("persona_build_adversarialize_downgrade", error=warning_msg)
                except asyncio.TimeoutError:
                    # Inner timeout (per-stage 60s). Treat as downgrade, not fatal.
                    hostile_applied = False
                    warning_msg = "adversarialize stage timeout"
                    v2 = mark_hostile_fallback(v2, warning_msg)
                    logger.warning("persona_build_adversarialize_timeout")

                yield _emit(
                    BUILD_ADVERSARIALIZE_DONE,
                    hostile_applied=hostile_applied,
                )

                # Normalize LLM-abbreviated claims → exact layer statements so the
                # frontend's claim-indexed evidenceMap lookup finds them.
                v2 = align_evidence_claims(v2)

                # AC5: ensure every layer has ≥1 evidence
                v2 = ensure_evidence_completeness(v2)

                # Enhancement mode: merge evidence from existing persona
                if existing_persona:
                    v2 = _merge_evidence(v2, existing_persona)
                    yield _emit(
                        BUILD_ENHANCEMENT_MERGE,
                        merged_evidence_count=len(v2.evidence_citations),
                    )

                # AC4: stash hostile_applied + warning in structured_profile._metadata
                # This mutation survives save_structured_persona's serialization
                # because serialization reads the live Persona state.
                # NOTE: domain Persona has no metadata dict → we stash in the
                # 5-layer dict at serialization time via the repo adapter.
                # For MVP we rely on source_materials marker (adversarialize / adversarialize:failed).

                # Phase: persist_done
                await self._repo.save_structured_persona(v2)
                await self._cache.set(cache_key, v2.id)

                yield _emit(
                    BUILD_PERSIST_DONE,
                    persona_id=v2.id,
                    hostile_applied=hostile_applied,
                    from_cache=False,
                )

        except asyncio.TimeoutError as exc:
            elapsed = time.perf_counter() - t0
            yield _emit(
                BUILD_ERROR,
                error_code="BUILD_TIMEOUT",
                message=f"total timeout {self._total_timeout_s}s exceeded ({elapsed:.1f}s)",
            )
            raise BuildTimeoutError(
                total_timeout_s=self._total_timeout_s,
                elapsed_s=elapsed,
                stage="total",
            ) from exc
        except BuildError:
            raise
        except Exception as exc:
            yield _emit(
                BUILD_ERROR,
                error_code="BUILD_FAILED",
                message=f"{type(exc).__name__}: {exc}",
            )
            raise BuildError(f"persona build failed: {type(exc).__name__}: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_agent_output(self, workspace_path: Optional[Path]) -> str:
        if workspace_path is None:
            raise BuildError(
                "agent finished without emitting workspace_ready event",
                error_code="NO_WORKSPACE",
            )
        md_path = workspace_path / _AGENT_OUTPUT_FILE
        if not md_path.exists():
            raise BuildError(
                f"agent produced no output at {md_path}",
                error_code="NO_AGENT_OUTPUT",
            )
        try:
            return md_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BuildError(
                f"failed to read agent output: {exc}",
                error_code="AGENT_OUTPUT_READ_FAILED",
            ) from exc

    async def _parse_markdown_to_json(
        self,
        markdown: str,
        *,
        existing_persona: Optional[Persona] = None,
    ) -> dict[str, Any]:
        """Call LLM with parse_prompt + markdown and return parsed 5-layer JSON.

        When ``existing_persona`` is provided (enhancement mode), the user message
        includes the existing profile JSON with merge instructions so the LLM
        preserves existing traits while incorporating new material.
        """
        if existing_persona:
            existing_json = _serialize_existing_for_merge(existing_persona)
            user_content = (
                f"# Existing Profile (KEEP and ENHANCE)\n\n```json\n{existing_json}\n```\n\n"
                f"# New Agent Output (MERGE into above)\n\n{markdown}\n\n"
                f"# Merge Rules\n"
                f"- Keep ALL existing evidence_citations and ADD new ones from new material\n"
                f"- For conflicting traits: NEW overrides OLD\n"
                f"- Accumulate lists (hard_rules, catchphrases, triggers) — deduplicate\n"
                f"- Keep existing values for fields where new material adds nothing\n"
            )
        else:
            user_content = markdown
        messages = [
            LLMMessage(role="system", content=self._parse_prompt),
            LLMMessage(role="user", content=user_content),
        ]
        try:
            response = await self._llm.generate(messages, temperature=0.2)
        except Exception as exc:
            raise BuildError(
                f"markdown→JSON LLM call failed: {exc}",
                error_code="STRUCTURED_PARSE_LLM_FAILED",
            ) from exc
        try:
            return parse_llm_json(response.content)
        except MigrationError as exc:
            raise BuildError(
                f"markdown→JSON parse failed: {exc}",
                error_code="STRUCTURED_PARSE_FAILED",
            ) from exc


# ---------------------------------------------------------------------------
# Module-level helpers (exported for unit testing)
# ---------------------------------------------------------------------------


def _build_v1_shell(
    *,
    persona_id: str,
    name: Optional[str],
    role: Optional[str],
    markdown: str,
) -> Persona:
    """Create a minimal Persona shell to feed into build_persona_v2."""
    return Persona(
        id=persona_id,
        name=name or persona_id,
        role=role or "",
        profile_summary="",
    )


def _synthesize_persona_id(hint: str) -> str:
    """Generate a fresh persona_id from a name or user_id hint.

    Produces e.g. ``lu-jianfeng-a1b2c3d4`` for a Chinese name or
    ``anonymous-a1b2c3d4`` for a bare user_id.
    """
    import re

    slug = re.sub(r"[^\w\s-]", "", hint.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)[:30].strip("-") or "persona"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _count_claims(persona: Persona) -> int:
    """Count addressable claims across all 5 layers for parse_done payload."""
    count = len(persona.hard_rules)
    if persona.identity:
        count += 1 if persona.identity.hidden_agenda else 0
        count += len(persona.identity.core_values)
    if persona.expression:
        count += len(persona.expression.catchphrases)
    if persona.decision:
        count += len(persona.decision.typical_questions)
    if persona.interpersonal:
        count += len(persona.interpersonal.triggers)
    return count


def _layer_statements(persona: Persona, layer: str) -> list[str]:
    """Candidate exact strings that a claim in ``layer`` may refer to."""
    if layer == "hard_rules":
        return [r.statement for r in persona.hard_rules if r.statement]
    if layer == "identity" and persona.identity:
        out: list[str] = []
        if persona.identity.background:
            out.append(persona.identity.background)
        out.extend(v for v in persona.identity.core_values if v)
        if persona.identity.hidden_agenda:
            out.append(persona.identity.hidden_agenda)
        return out
    if layer == "expression" and persona.expression:
        out = []
        if persona.expression.tone:
            out.append(persona.expression.tone)
        out.extend(c for c in persona.expression.catchphrases if c)
        return out
    if layer == "decision" and persona.decision:
        out = []
        if persona.decision.style:
            out.append(persona.decision.style)
        out.extend(q for q in persona.decision.typical_questions if q)
        return out
    if layer == "interpersonal" and persona.interpersonal:
        out = []
        if persona.interpersonal.authority_mode:
            out.append(persona.interpersonal.authority_mode)
        out.extend(t for t in persona.interpersonal.triggers if t)
        out.extend(e for e in persona.interpersonal.emotion_states if e)
        return out
    return []


def _best_statement_match(claim: str, candidates: list[str]) -> Optional[str]:
    """Pick candidate that best aligns with ``claim``.

    Prefers a candidate that contains ``claim`` as substring (LLM often
    abbreviates the real statement). Falls back to claim-contains-candidate,
    then to fuzzy similarity via ``difflib.SequenceMatcher``. Returns None
    when nothing clears the 0.5 similarity floor.
    """
    if not claim or not candidates:
        return None
    # 1) candidate contains claim → LLM trimmed the statement
    contains = [c for c in candidates if claim in c]
    if contains:
        # Shortest containing candidate is the tightest match
        return min(contains, key=len)
    # 2) claim contains candidate (e.g., claim is a paraphrase longer than the
    # stored catchphrase) → need decent overlap to avoid matching "Q3" to a
    # one-character candidate. Require ≥ 4 chars and ≥ 40 % of candidate length.
    reverse = [c for c in candidates if len(c) >= 4 and c in claim]
    if reverse:
        return max(reverse, key=len)
    # 3) Fuzzy match for paraphrased claims. SequenceMatcher is O(n*m) but
    # candidate lists here are tiny (≤ ~20 items, each ≤ ~200 chars).
    from difflib import SequenceMatcher

    best: Optional[tuple[float, str]] = None
    for c in candidates:
        ratio = SequenceMatcher(None, claim, c).ratio()
        if ratio >= 0.5 and (best is None or ratio > best[0]):
            best = (ratio, c)
    return best[1] if best else None


def align_evidence_claims(persona: Persona) -> Persona:
    """Rewrite each evidence's ``claim`` to the exact matching layer statement.

    The parse LLM frequently abbreviates a rule/catchphrase when populating
    ``evidence_citations[].claim``. The editor UI keys its evidence popover
    by exact-string match against each feature's statement/phrase, so drift
    hides all "view evidence" buttons. This pass reattaches each evidence to
    the closest literal string available in its declared layer. Evidences
    whose ``layer`` is unknown or have no viable match are passed through
    unchanged.
    """
    if not persona.evidence_citations:
        return persona

    from dataclasses import replace

    updated: list[Evidence] = []
    for ev in persona.evidence_citations:
        candidates = _layer_statements(persona, ev.layer)
        match = _best_statement_match(ev.claim, candidates)
        if match and match != ev.claim:
            updated.append(replace(ev, claim=match))
        else:
            updated.append(ev)
    return replace(persona, evidence_citations=updated)


def ensure_evidence_completeness(persona: Persona) -> Persona:
    """AC5: guarantee every 5-layer slot has ≥1 evidence backing.

    If a layer has claims but no evidence_citations entry with that layer,
    append a low-confidence synthetic evidence so downstream consumers don't
    break on missing citations. Synthetic evidences use source_material_id
    = "synthetic" and confidence = 0.3 as a visible signal that they are
    placeholders.
    """
    existing_layers = {e.layer for e in persona.evidence_citations}
    new_evidences = list(persona.evidence_citations)

    layer_has_claims = {
        "hard_rules": bool(persona.hard_rules),
        "identity": bool(
            persona.identity and (persona.identity.core_values or persona.identity.hidden_agenda)
        ),
        "expression": bool(persona.expression and persona.expression.catchphrases),
        "decision": bool(persona.decision and persona.decision.typical_questions),
        "interpersonal": bool(persona.interpersonal and persona.interpersonal.triggers),
    }

    for layer in _LAYER_NAMES:
        if layer_has_claims[layer] and layer not in existing_layers:
            claim_text = _first_claim_for_layer(persona, layer)
            new_evidences.append(
                Evidence(
                    claim=claim_text or f"{layer} claim",
                    citations=["synthetic: no direct citation"],
                    confidence=0.3,
                    source_material_id="synthetic",
                    layer=layer,
                )
            )

    from dataclasses import replace

    return replace(persona, evidence_citations=new_evidences)


def _first_claim_for_layer(persona: Persona, layer: str) -> str:
    """Return a short string summarizing the first claim in a given layer."""
    if layer == "hard_rules" and persona.hard_rules:
        return persona.hard_rules[0].statement[:60]
    if layer == "identity" and persona.identity:
        if persona.identity.hidden_agenda:
            return persona.identity.hidden_agenda[:60]
        if persona.identity.core_values:
            return persona.identity.core_values[0][:60]
    if layer == "expression" and persona.expression and persona.expression.catchphrases:
        return persona.expression.catchphrases[0][:60]
    if layer == "decision" and persona.decision and persona.decision.typical_questions:
        return persona.decision.typical_questions[0][:60]
    if layer == "interpersonal" and persona.interpersonal and persona.interpersonal.triggers:
        return persona.interpersonal.triggers[0][:60]
    return ""


__all__ = [
    "PersonaBuilderService",
    "ensure_evidence_completeness",
]
