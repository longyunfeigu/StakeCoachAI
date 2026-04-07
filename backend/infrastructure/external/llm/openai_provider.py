# input: openai SDK, LLMPort 接口
# output: OpenAIProvider LLM 实现
# owner: unknown
# pos: 基础设施层 - OpenAI SDK LLM 提供者实现（兼容 Azure/vLLM）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""OpenAI SDK implementation of LLMPort."""

from __future__ import annotations

from typing import AsyncIterator, Optional

from openai import AsyncOpenAI

from application.ports.llm import LLMChunk, LLMMessage, LLMPort, LLMResponse
from core.logging_config import get_logger

logger = get_logger(__name__)


class OpenAIProvider:
    """LLMPort implementation using the OpenAI Python SDK.

    Compatible with OpenAI, Azure OpenAI, vLLM, and other
    OpenAI-API-compatible providers via base_url.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        default_model: str = "gpt-4o-mini",
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
        timeout: int = 60,
        max_retries: int = 2,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens

    def _build_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=model or self._default_model,
            messages=self._build_messages(messages),
            temperature=temperature if temperature is not None else self._default_temperature,
            max_tokens=max_tokens or self._default_max_tokens,
            stream=False,
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            finish_reason=choice.finish_reason,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMChunk]:
        response = await self._client.chat.completions.create(
            model=model or self._default_model,
            messages=self._build_messages(messages),
            temperature=temperature if temperature is not None else self._default_temperature,
            max_tokens=max_tokens or self._default_max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in response:
            if not chunk.choices and chunk.usage:
                # Final chunk with usage stats only
                yield LLMChunk(
                    content="",
                    model=chunk.model or "",
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            yield LLMChunk(
                content=delta.content or "",
                model=chunk.model or "",
                finish_reason=chunk.choices[0].finish_reason,
            )
