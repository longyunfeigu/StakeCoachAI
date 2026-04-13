# input: claude_agent_sdk raw message types (SystemMessage / AssistantMessage / ResultMessage)
# output: AgentEvent dataclass + adapt_event() converter
# owner: wanhua.gu
# pos: 基础设施层 - Agent SDK 原生事件到统一 AgentEvent 的适配；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Adapter from claude-agent-sdk raw events to a unified ``AgentEvent`` envelope.

Why a separate adapter:
- Decouples application code from the SDK's evolving message types.
- Provides a stable ``seq`` counter for SSE / observability.
- Surfaces ``duration_ms`` / ``num_turns`` from ``ResultMessage`` to the top
  level so metrics don't need to introspect raw payload.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

# Event type strings (stable contract for downstream consumers; do not rename)
EVENT_WORKSPACE_READY = "workspace_ready"  # synthesized — meta event carrying workspace path
EVENT_SYSTEM = "system"
EVENT_ASSISTANT_TEXT = "assistant_text"
EVENT_TOOL_USE = "tool_use"
EVENT_TOOL_RESULT = "tool_result"
EVENT_RESULT = "result"
EVENT_UNKNOWN = "unknown"


@dataclass
class AgentEvent:
    """Unified event envelope yielded by ``AgentSkillClient``.

    Attributes:
        seq: monotonically increasing sequence number within one agent run.
        type: one of the ``EVENT_*`` constants.
        ts: unix timestamp (float seconds) when the adapter received the event.
        payload: structured fields extracted from the raw event.
        raw_subtype: original SDK subtype (for debugging / passthrough).
    """

    seq: int
    type: str
    ts: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)
    raw_subtype: Optional[str] = None


def _classify_system(subtype: Optional[str]) -> str:
    """System events map to a single 'system' type; subtype kept in raw_subtype."""
    return EVENT_SYSTEM


def adapt_event(raw: Any, *, seq: int) -> AgentEvent:
    """Convert one claude_agent_sdk message into an ``AgentEvent``.

    Unknown types fall through to ``EVENT_UNKNOWN`` with the repr in payload —
    this keeps the stream alive even if the SDK adds new message types.
    """
    cls_name = type(raw).__name__
    raw_subtype = getattr(raw, "subtype", None)

    # SystemMessage: hooks, init, etc.
    if cls_name == "SystemMessage":
        return AgentEvent(
            seq=seq,
            type=_classify_system(raw_subtype),
            payload={"data": getattr(raw, "data", {})},
            raw_subtype=raw_subtype,
        )

    # AssistantMessage: contains content blocks (TextBlock, ToolUseBlock, ...)
    if cls_name == "AssistantMessage":
        content = getattr(raw, "content", []) or []
        # Detect tool use vs. plain text. Yield one AgentEvent per block-collection
        # in the simplest case; callers can re-segment if they want per-block.
        text_parts: list[str] = []
        tool_uses: list[dict[str, Any]] = []
        for block in content:
            block_cls = type(block).__name__
            if block_cls == "TextBlock":
                text_parts.append(getattr(block, "text", ""))
            elif block_cls == "ToolUseBlock":
                tool_uses.append(
                    {
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "input": getattr(block, "input", None),
                    }
                )
        if tool_uses:
            return AgentEvent(
                seq=seq,
                type=EVENT_TOOL_USE,
                payload={
                    "tool_uses": tool_uses,
                    "model": getattr(raw, "model", None),
                    "text_parts": text_parts,  # any text alongside tool calls
                },
                raw_subtype=cls_name,
            )
        return AgentEvent(
            seq=seq,
            type=EVENT_ASSISTANT_TEXT,
            payload={
                "text": "".join(text_parts),
                "model": getattr(raw, "model", None),
            },
            raw_subtype=cls_name,
        )

    # UserMessage: tool_result blocks come back as user messages in SDK convention
    if cls_name == "UserMessage":
        content = getattr(raw, "content", []) or []
        results: list[dict[str, Any]] = []
        for block in content:
            block_cls = type(block).__name__
            if block_cls == "ToolResultBlock":
                results.append(
                    {
                        "tool_use_id": getattr(block, "tool_use_id", None),
                        "content": getattr(block, "content", None),
                        "is_error": getattr(block, "is_error", False),
                    }
                )
        if results:
            return AgentEvent(
                seq=seq,
                type=EVENT_TOOL_RESULT,
                payload={"results": results},
                raw_subtype=cls_name,
            )
        return AgentEvent(
            seq=seq,
            type=EVENT_UNKNOWN,
            payload={"raw_class": cls_name, "repr": repr(raw)[:200]},
            raw_subtype=cls_name,
        )

    # ResultMessage: terminal event with success/error + duration metrics
    if cls_name == "ResultMessage":
        return AgentEvent(
            seq=seq,
            type=EVENT_RESULT,
            payload={
                "subtype": raw_subtype,
                "is_error": getattr(raw, "is_error", False),
                "duration_ms": getattr(raw, "duration_ms", None),
                "duration_api_ms": getattr(raw, "duration_api_ms", None),
                "num_turns": getattr(raw, "num_turns", None),
                "session_id": getattr(raw, "session_id", None),
            },
            raw_subtype=raw_subtype,
        )

    # Unknown — keep the stream flowing but flag it
    return AgentEvent(
        seq=seq,
        type=EVENT_UNKNOWN,
        payload={"raw_class": cls_name, "repr": repr(raw)[:200]},
        raw_subtype=cls_name,
    )
