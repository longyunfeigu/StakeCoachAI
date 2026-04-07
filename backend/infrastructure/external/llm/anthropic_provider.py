# input: anthropic SDK, LLMPort 接口
# output: AnthropicProvider LLM 实现
# owner: wanhua.gu
# pos: 基础设施层 - Anthropic SDK LLM 提供者实现（Claude API）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Anthropic SDK implementation of LLMPort."""

from __future__ import annotations

from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic

from application.ports.llm import LLMChunk, LLMMessage, LLMPort, LLMResponse
from core.logging_config import get_logger

logger = get_logger(__name__)


class AnthropicProvider:
    """LLMPort implementation using the Anthropic Python SDK.

    Uses the Messages API for Claude models.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        default_model: str = "claude-opus-4-0-20250514",
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
    ) -> None:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**client_kwargs)
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens

    def _split_system_and_messages(
        self, messages: list[LLMMessage]
    ) -> tuple[Optional[str], list[dict]]:
        """Extract system message and convert remaining to Anthropic format.

        Anthropic API takes system as a top-level parameter, not in messages.
        """
        system_content = None
        api_messages = []
        for m in messages:
            if m.role == "system":
                system_content = m.content
            else:
                api_messages.append({"role": m.role, "content": m.content})
        return system_content, api_messages

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        system_content, api_messages = self._split_system_and_messages(messages)

        kwargs: dict = {
            "model": model or self._default_model,
            "messages": api_messages,
            "temperature": temperature if temperature is not None else self._default_temperature,
            "max_tokens": max_tokens or self._default_max_tokens,
        }
        if system_content:
            kwargs["system"] = system_content

        response = await self._client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMChunk]:
        system_content, api_messages = self._split_system_and_messages(messages)

        kwargs: dict = {
            "model": model or self._default_model,
            "messages": api_messages,
            "temperature": temperature if temperature is not None else self._default_temperature,
            "max_tokens": max_tokens or self._default_max_tokens,
        }
        if system_content:
            kwargs["system"] = system_content

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if hasattr(event, "type"):
                    if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                        yield LLMChunk(content=event.delta.text)
                    elif event.type == "message_stop":
                        final = await stream.get_final_message()
                        yield LLMChunk(
                            content="",
                            model=final.model,
                            finish_reason=final.stop_reason,
                            prompt_tokens=final.usage.input_tokens,
                            completion_tokens=final.usage.output_tokens,
                            total_tokens=final.usage.input_tokens + final.usage.output_tokens,
                        )
