# input: domain.stakeholder.persona_entity (Persona + 5-layer dataclasses + Evidence), application.ports.llm (LLMPort/LLMMessage/LLMResponse), prompts/persona_v1_to_v2.md
# output: parse_llm_json, build_persona_v2, migrate_one, run_migration, print_report, MigrationError, MigrationOutcome, MigrationReport (Story 2.3)
# owner: wanhua.gu
# pos: 应用层 - 旧 markdown persona → v2 结构化 5-layer 迁移核心逻辑 (纯函数 + async 编排)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Persona v1 (markdown) → v2 (5-layer structured) migration logic (Story 2.3).

两层拆分:
- 纯函数 (`parse_llm_json`, `build_persona_v2`): 不依赖 I/O，便于单元测试
- 异步编排 (`migrate_one`, `run_migration`): 调度 LLM + Repository，供 CLI 脚本使用

AC 映射:
- AC1 幂等: run_migration skip already-migrated personas
- AC2 LLM → 5-layer JSON: migrate_one + parse_llm_json + build_persona_v2
- AC4 失败不阻塞: run_migration try/except 每条独立
- AC5 --dry-run: migrate_one + run_migration 双层拦截
- AC6 汇总: MigrationReport + print_report
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from application.ports.llm import LLMMessage, LLMPort
from core.logging_config import get_logger
from domain.stakeholder.persona_entity import (
    DecisionPattern,
    Evidence,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)

logger = get_logger(__name__)

_REQUIRED_KEYS = {
    "hard_rules",
    "identity",
    "expression",
    "decision",
    "interpersonal",
    "evidence_citations",
}

_PROMPT_PATH = Path(__file__).parent / "prompts" / "persona_v1_to_v2.md"


__all__ = [
    "MigrationError",
    "MigrationOutcome",
    "MigrationReport",
    "build_persona_v2",
    "load_prompt",
    "migrate_one",
    "parse_llm_json",
    "print_report",
    "run_migration",
]


class MigrationError(Exception):
    """Raised when a single persona migration fails (parse/LLM/validation)."""


@dataclass
class MigrationOutcome:
    """Result of migrating a single persona."""

    status: Literal["migrated", "failed", "dry_run"]
    persona: Optional[Persona] = None
    error: Optional[str] = None


@dataclass
class MigrationReport:
    """Aggregate report across all personas in a migration run."""

    migrated: int = 0
    failed: int = 0
    skipped: int = 0


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def _strip_code_fence(raw: str) -> str:
    """Remove a surrounding triple-backtick code fence if present."""
    text = raw.strip()
    if text.startswith("```"):
        # drop first fence line (may be ```json or just ```)
        lines = text.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
        # drop trailing ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_llm_json(raw: str) -> dict:
    """Parse LLM response into a dict, stripping code fences; validate required top-level keys.

    Raises MigrationError on invalid JSON or missing required keys.
    """
    cleaned = _strip_code_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MigrationError(f"invalid JSON from LLM: {exc}") from exc

    if not isinstance(data, dict):
        raise MigrationError(f"expected JSON object, got {type(data).__name__}")

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise MigrationError(f"missing required keys: {sorted(missing)}")

    return data


def build_persona_v2(v1: Persona, llm_data: dict) -> Persona:
    """Compose a v2 Persona by merging v1 identity fields with LLM-extracted 5-layer JSON.

    Raises DomainValidationException (from Evidence.__post_init__) if layer is invalid.
    """
    hard_rules = [HardRule(**r) for r in llm_data.get("hard_rules") or []]

    identity_data = llm_data.get("identity") or {}
    identity = IdentityProfile(
        background=identity_data.get("background", ""),
        core_values=list(identity_data.get("core_values") or []),
        hidden_agenda=identity_data.get("hidden_agenda"),
    )

    expression_data = llm_data.get("expression") or {}
    expression = ExpressionStyle(
        tone=expression_data.get("tone", ""),
        catchphrases=list(expression_data.get("catchphrases") or []),
        interruption_tendency=expression_data.get("interruption_tendency", "medium"),
    )

    decision_data = llm_data.get("decision") or {}
    decision = DecisionPattern(
        style=decision_data.get("style", ""),
        risk_tolerance=decision_data.get("risk_tolerance", "medium"),
        typical_questions=list(decision_data.get("typical_questions") or []),
    )

    interpersonal_data = llm_data.get("interpersonal") or {}
    interpersonal = InterpersonalStyle(
        authority_mode=interpersonal_data.get("authority_mode", ""),
        triggers=list(interpersonal_data.get("triggers") or []),
        emotion_states=list(interpersonal_data.get("emotion_states") or []),
    )

    evidence_citations = [Evidence(**e) for e in llm_data.get("evidence_citations") or []]

    return Persona(
        id=v1.id,
        name=v1.name,
        role=v1.role,
        avatar_color=v1.avatar_color,
        organization_id=v1.organization_id,
        team_id=v1.team_id,
        profile_summary=v1.profile_summary,
        parse_status=v1.parse_status,
        voice_id=v1.voice_id,
        voice_speed=v1.voice_speed,
        voice_style=v1.voice_style,
        hard_rules=hard_rules,
        identity=identity,
        expression=expression,
        decision=decision,
        interpersonal=interpersonal,
        evidence_citations=evidence_citations,
        source_materials=[f"{v1.id}-markdown"],
    )


def load_prompt() -> str:
    """Load the migration prompt from disk.

    Kept as a function (not module-level constant) so tests can mock _PROMPT_PATH if needed.
    """
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Async orchestration
# ---------------------------------------------------------------------------


async def migrate_one(
    v1: Persona,
    llm: LLMPort,
    prompt: str,
    *,
    dry_run: bool,
) -> MigrationOutcome:
    """Migrate a single v1 persona to v2 using the given LLM.

    - dry_run=True: skip LLM + return status='dry_run'
    - On LLM exception / parse error: raise MigrationError
    """
    if dry_run:
        logger.info("migrate_one_dry_run", persona_id=v1.id)
        return MigrationOutcome(status="dry_run")

    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(
            role="user",
            content=(
                f"persona_id: {v1.id}\n"
                f"name: {v1.name}\n"
                f"role: {v1.role}\n\n"
                "---\n"
                f"{v1.profile_summary}"
            ),
        ),
    ]

    try:
        response = await llm.generate(messages)
    except Exception as exc:  # broad: connection/timeout/etc.
        raise MigrationError(f"LLM call failed: {type(exc).__name__}: {exc}") from exc

    data = parse_llm_json(response.content)
    v2 = build_persona_v2(v1, data)  # may raise DomainValidationException
    return MigrationOutcome(status="migrated", persona=v2)


async def run_migration(
    *,
    repo,  # StakeholderPersonaRepository-like (duck-typed to ease testing)
    llm: LLMPort,
    disk_personas: list[Persona],
    prompt: str,
    dry_run: bool,
) -> MigrationReport:
    """Orchestrate migration across DB v1 records + disk markdown personas.

    Strategy:
    - Scan DB for existing records
    - Build merged map by persona_id (DB takes priority; disk fills gaps)
    - Skip records already with structured_profile
    - For each remaining, call migrate_one; persist v2 on success; record error on failure
    """
    report = MigrationReport()

    # Load current DB state once
    all_db = await repo.list_all()
    db_by_id: dict[str, Persona] = {p.id: p for p in all_db}

    # Build to-process list: DB wins over disk; disk fills gaps; already-structured skipped
    to_process_by_id: dict[str, Persona] = {}
    for p in disk_personas:
        if p.id not in db_by_id:
            to_process_by_id[p.id] = p
    for p in all_db:
        if not p.hard_rules and p.identity is None:
            to_process_by_id[p.id] = p  # not yet structured
        else:
            report.skipped += 1
            logger.info("migrate_skip_structured", persona_id=p.id)

    # Process in stable order (by id)
    for persona_id in sorted(to_process_by_id.keys()):
        v1 = to_process_by_id[persona_id]
        try:
            outcome = await migrate_one(v1, llm, prompt=prompt, dry_run=dry_run)
        except MigrationError as exc:
            logger.warning("migrate_failed", persona_id=persona_id, error=str(exc))
            report.failed += 1
            continue
        except Exception as exc:  # e.g. DomainValidationException
            logger.warning(
                "migrate_failed_unexpected",
                persona_id=persona_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            report.failed += 1
            continue

        if outcome.status == "dry_run":
            report.skipped += 1
            print(f"[DRY-RUN] will migrate: persona_id={persona_id}")
            continue

        assert outcome.persona is not None
        await repo.save_structured_persona(outcome.persona)
        report.migrated += 1
        logger.info("migrate_success", persona_id=persona_id)

    return report


def print_report(report: MigrationReport) -> None:
    """Print the canonical summary line per AC6."""
    print(f"Migrated: {report.migrated}, Failed: {report.failed}, Skipped: {report.skipped}")


# re-export helper used in error metadata
def build_error_metadata(error: str) -> dict:
    """Construct {'_error': ..., '_attempted_at': ...} dict for structured_profile."""
    return {
        "_error": error,
        "_attempted_at": datetime.now(timezone.utc).isoformat(),
    }
