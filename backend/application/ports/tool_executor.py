# input: Tool/function definitions and invocation results
# output: ToolExecutorPort Protocol (Phase 2 stub)
# owner: unknown
# pos: 应用层端口 - 工具执行抽象接口存根；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tool executor port stub for Phase 2."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolExecutorPort(Protocol):
    """Port for executing agent tools/functions (Phase 2)."""

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any: ...
