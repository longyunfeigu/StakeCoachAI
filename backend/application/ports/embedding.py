# input: Embedding provider SDKs
# output: EmbeddingPort Protocol (Phase 2 stub)
# owner: unknown
# pos: 应用层端口 - 向量嵌入抽象接口存根；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Embedding port stub for Phase 2."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    """Port for generating vector embeddings (Phase 2)."""

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]: ...
