# input: AgentSDKSettings, WorkspaceManager
# output: AgentSkillClient.build_persona() async generator yielding AgentEvent
# owner: wanhua.gu
# pos: 基础设施层 - Claude Agent SDK 主客户端封装（Application 层唯一入口）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""``AgentSkillClient`` — the only public entrypoint to the agent runtime.

Application code MUST depend on this class, never on ``claude_agent_sdk``
directly. This isolates the SDK choice and lets us swap implementations.

Behavior:
- Each ``build_persona`` call creates a fresh ``Workspace`` (multi-tenant cwd).
- Materials are written to ``{workspace}/materials/0.txt, 1.txt, ...``.
- Sub-agent runs with ``cwd=workspace.path`` and ``setting_sources=["project"]``
  so it can autoload the colleague-skill from ``.claude/skills/``.
- ``allowed_tools`` is the configured whitelist (Bash is excluded by config).
- Total runtime is bounded by ``agent_timeout_s``.
- ``asyncio.Semaphore(max_concurrent_builds)`` limits concurrent invocations.
- On any termination path, the workspace is scheduled for cleanup.

API key / base URL are NOT taken from constructor params; instead they are set
into ``os.environ`` for the subprocess. Logged with redaction.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import contextmanager
from typing import AsyncIterator, Iterator, Optional

from core.config import AgentSDKSettings
from core.logging_config import get_logger
from infrastructure.external.agent_sdk.events import (
    EVENT_RESULT,
    EVENT_WORKSPACE_READY,
    AgentEvent,
    adapt_event,
)
from infrastructure.external.agent_sdk.exceptions import (
    AgentRunError,
    AgentTimeoutError,
)
from infrastructure.external.agent_sdk.workspace import Workspace, WorkspaceManager

logger = get_logger(__name__)


class AgentSkillClient:
    """High-level wrapper around ``claude_agent_sdk.query`` for skill execution."""

    def __init__(
        self,
        *,
        settings: AgentSDKSettings,
        workspace_mgr: WorkspaceManager,
    ) -> None:
        self._settings = settings
        self._workspace_mgr = workspace_mgr
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_builds)

    @contextmanager
    def _patched_env(self) -> Iterator[None]:
        """Inject ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL into env for the subprocess.

        Restores prior values on exit. Uses SecretStr.get_secret_value() so the
        key never appears in repr / __str__.
        """
        keys_to_restore: dict[str, Optional[str]] = {}

        def _set(env_key: str, value: Optional[str]) -> None:
            if value is None:
                return
            keys_to_restore[env_key] = os.environ.get(env_key)
            os.environ[env_key] = value

        api_key = (
            self._settings.anthropic_api_key.get_secret_value()
            if self._settings.anthropic_api_key
            else None
        )
        _set("ANTHROPIC_API_KEY", api_key)
        _set("ANTHROPIC_BASE_URL", self._settings.anthropic_base_url)

        try:
            yield
        finally:
            for k, v in keys_to_restore.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    async def _write_materials(self, ws: Workspace, materials: list[str]) -> None:
        """Persist each material chunk to a separate file inside the workspace."""
        loop = asyncio.get_running_loop()

        def _do() -> None:
            mat_dir = ws.path / "materials"
            for i, content in enumerate(materials):
                (mat_dir / f"{i}.txt").write_text(content, encoding="utf-8")

        await loop.run_in_executor(None, _do)

    def _build_prompt(
        self,
        materials: list[str],
        *,
        target_name: Optional[str] = None,
        target_role: Optional[str] = None,
        existing_profile: Optional[str] = None,
    ) -> str:
        """Build the prompt sent to the sub-agent.

        The skill itself contains the heavy instructions; this prompt just tells
        the agent to invoke it on the materials we placed in cwd/materials/.

        When ``existing_profile`` is provided (enhancement/merge mode), the agent
        is instructed to treat the existing profile as baseline context and merge
        new materials into it.
        """
        n = len(materials)
        parts = [
            "You have access to the `create-colleague` skill in this workspace's "
            "`.claude/skills/` directory. Use it to build a 5-layer persona from the "
            f"{n} material file(s) located in `materials/0.txt` through "
            f"`materials/{n - 1}.txt`. Read all materials first, then run the skill's "
            "7-step pipeline (intake → work_analyzer → persona_analyzer → "
            "work_builder → persona_builder → merger → correction_handler). "
            "Write the final markdown persona to `output/persona.md`.",
        ]

        if target_name:
            parts.append(
                f"\nIMPORTANT: The target person to model is 「{target_name}」"
                + (f" (role: {target_role})" if target_role else "")
                + ". Focus ONLY on this person's behavior, speech patterns, and "
                "decision style. Ignore other speakers' characteristics."
            )
        else:
            parts.append(
                "\nThe materials contain a multi-speaker transcript. Identify the "
                "most dominant and authoritative speaker — the one who gives orders, "
                "interrupts others, asks the toughest questions, and sets deadlines. "
                "Build the persona around THAT person. Include their real name in "
                "the persona frontmatter (name: field)."
            )

        if existing_profile:
            parts.append(
                "\n## ENHANCEMENT MODE — MERGE RUN\n"
                "This is an incremental enhancement of an existing persona profile. "
                "The existing profile JSON is provided below as context. Your task:\n"
                "- KEEP all existing traits, evidence, and rules as baseline\n"
                "- ADD new insights discovered from the new materials\n"
                "- For conflicting traits, let the NEW materials override\n"
                "- Accumulate lists (hard_rules, catchphrases, triggers) — deduplicate\n"
                "- Preserve existing evidence citations and add new ones\n\n"
                f"### Existing Profile\n```json\n{existing_profile}\n```"
            )

        parts.append(
            "\nUse Chinese for the persona output. 用中文输出画像。"
        )

        return "\n".join(parts)

    async def build_persona(
        self,
        *,
        user_id: str,
        materials: list[str],
        session_id: Optional[str] = None,
        target_name: Optional[str] = None,
        target_role: Optional[str] = None,
        existing_profile: Optional[str] = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run the colleague-skill pipeline against ``materials``, yielding events.

        Yields:
            ``AgentEvent`` instances as the sub-agent emits messages.

        Raises:
            ``AgentTimeoutError`` if the run exceeds ``agent_timeout_s``.
            ``AgentRunError`` if the SDK raises any other exception.
            ``WorkspaceError`` if workspace creation fails.
        """
        if not materials:
            raise AgentRunError("materials must be a non-empty list", cause_type="ValueError")

        # Limit concurrency BEFORE creating the workspace so we don't accumulate dirs.
        async with self._semaphore:
            ws = await self._workspace_mgr.create(user_id=user_id, session_id=session_id)
            seq = 0
            t0 = time.perf_counter()
            cleanup_delay = self._settings.cleanup_delay_s

            try:
                await self._write_materials(ws, materials)
                prompt = self._build_prompt(
                    materials,
                    target_name=target_name,
                    target_role=target_role,
                    existing_profile=existing_profile,
                )

                # Emit a synthesized workspace_ready event so downstream consumers
                # (e.g. PersonaBuilderService) can locate the cwd for reading
                # agent artifacts (output/persona.md) once the run completes.
                seq += 1
                yield AgentEvent(
                    seq=seq,
                    type=EVENT_WORKSPACE_READY,
                    payload={
                        "workspace_path": str(ws.path),
                        "user_id": ws.user_id,
                        "session_id": ws.session_id,
                    },
                )

                # Lazy import: keeps backend import-time cost down, and isolates
                # the SDK so it's only loaded by code that actually needs it.
                from claude_agent_sdk import ClaudeAgentOptions, query

                options = ClaudeAgentOptions(
                    cwd=str(ws.path),
                    setting_sources=["project"],
                    allowed_tools=list(self._settings.allowed_tools),
                )

                logger.info(
                    "agent.build_started",
                    user_id=user_id,
                    session_id=ws.session_id,
                    materials_count=len(materials),
                )

                with self._patched_env():
                    try:
                        async with asyncio.timeout(self._settings.agent_timeout_s):
                            async for raw in query(prompt=prompt, options=options):
                                seq += 1
                                event = adapt_event(raw, seq=seq)
                                yield event
                    except asyncio.TimeoutError as e:
                        elapsed = time.perf_counter() - t0
                        cleanup_delay = 0  # immediate cleanup on timeout
                        raise AgentTimeoutError(
                            timeout_s=self._settings.agent_timeout_s,
                            elapsed_s=elapsed,
                        ) from e

                elapsed = time.perf_counter() - t0
                logger.info(
                    "agent.build_completed",
                    user_id=user_id,
                    session_id=ws.session_id,
                    elapsed_s=round(elapsed, 2),
                    event_count=seq,
                )
            except AgentTimeoutError:
                raise
            except Exception as e:  # noqa: BLE001 — wrap unknown SDK errors uniformly
                cleanup_delay = 0
                logger.error(
                    "agent.build_failed",
                    user_id=user_id,
                    session_id=ws.session_id,
                    error_type=type(e).__name__,
                    error=str(e)[:200],
                )
                raise AgentRunError(
                    f"sub-agent failed: {type(e).__name__}",
                    cause_type=type(e).__name__,
                    original=e,
                ) from e
            finally:
                # Always schedule cleanup; delay=0 on error paths above.
                self._workspace_mgr.schedule_cleanup(ws, delay_s=cleanup_delay)


__all__ = ["AgentSkillClient", "EVENT_RESULT"]
