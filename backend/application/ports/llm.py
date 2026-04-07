# input: LLM provider SDKs (OpenAI, Azure, vLLM)
# output: LLMPort Protocol, LLMMessage, LLMResponse, LLMChunk data types
# owner: unknown
# pos: 应用层端口 - LLM 调用抽象接口；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application-owned LLM port abstraction (hexagonal architecture).

Defines the minimal protocol needed by application use cases so that
the application layer does not depend on specific LLM provider details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Protocol, runtime_checkable


@dataclass
class LLMMessage:
    """A single message in a conversation sent to the LLM."""

    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    """Non-streaming LLM response."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: Optional[str] = None


@dataclass
class LLMChunk:
    """A single chunk from a streaming LLM response."""

    content: str = ""
    model: str = ""
    finish_reason: Optional[str] = None
    # Token usage is typically available only in the final chunk
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@runtime_checkable
class LLMPort(Protocol):
    """Port for interacting with a Large Language Model."""

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMChunk]: ...
