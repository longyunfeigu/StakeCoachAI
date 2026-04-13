# input: 无外部依赖（纯数据类型）
# output: BuildEvent dataclass + BUILD_* 事件类型常量（Story 2.4 / 2.5 消费）
# owner: wanhua.gu
# pos: 应用层 - persona 构建事件契约（供 PersonaBuilderService yield + API 层 SSE 序列化）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""BuildEvent envelope + canonical event type constants for persona build pipeline.

Story 2.4 requires 6 ordered happy-path events plus error/heartbeat auxiliary
types that Story 2.5's SSE API relays. Keeping the constants in one place
prevents string-drift between producer and consumer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# 6 canonical happy-path event types (order matters)
BUILD_WORKSPACE_READY = "workspace_ready"
BUILD_AGENT_TOOL_USE = "agent_tool_use"
BUILD_PARSE_DONE = "parse_done"
BUILD_ADVERSARIALIZE_START = "adversarialize_start"
BUILD_ADVERSARIALIZE_DONE = "adversarialize_done"
BUILD_PERSIST_DONE = "persist_done"

# Auxiliary types (emitted by Story 2.5 API layer; listed here for single source of truth)
BUILD_HEARTBEAT = "heartbeat"
BUILD_ERROR = "error"

BUILD_EVENT_TYPES: tuple[str, ...] = (
    BUILD_WORKSPACE_READY,
    BUILD_AGENT_TOOL_USE,
    BUILD_PARSE_DONE,
    BUILD_ADVERSARIALIZE_START,
    BUILD_ADVERSARIALIZE_DONE,
    BUILD_PERSIST_DONE,
    BUILD_HEARTBEAT,
    BUILD_ERROR,
)


@dataclass
class BuildEvent:
    """A single event emitted during a persona build run.

    Attributes:
        seq: 0-indexed monotonic counter within one build run (used by SSE clients
            to deduplicate on reconnect).
        type: one of the ``BUILD_*`` constants.
        ts: unix timestamp in seconds (float).
        data: event-specific payload; fields depend on ``type``:
            - workspace_ready: {"user_id", "workspace_path"}
            - agent_tool_use: {"tool_uses": [...]}
            - parse_done: {"persona_id", "claims"}
            - adversarialize_start: {}
            - adversarialize_done: {"hostile_applied": bool}
            - persist_done: {"persona_id", "hostile_applied", "from_cache"?}
            - error: {"error_code", "message"}
            - heartbeat: {}
    """

    seq: int
    type: str
    ts: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "BUILD_ADVERSARIALIZE_DONE",
    "BUILD_ADVERSARIALIZE_START",
    "BUILD_AGENT_TOOL_USE",
    "BUILD_ERROR",
    "BUILD_EVENT_TYPES",
    "BUILD_HEARTBEAT",
    "BUILD_PARSE_DONE",
    "BUILD_PERSIST_DONE",
    "BUILD_WORKSPACE_READY",
    "BuildEvent",
]
