# input: AbstractUnitOfWork, LLMPort, Conversation/Message/Run 领域实体
# output: ChatApplicationService 聊天用例编排（流式 + 非流式）
# owner: unknown
# pos: 应用层服务 - 核心聊天流程编排，发消息→创建Run→调LLM→流式返回；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for the chat workflow (send message → LLM → stream response)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Optional

from application.dto import ChatRequestDTO, MessageDTO_Agent, RunDTO
from application.ports.llm import LLMChunk, LLMMessage, LLMPort, LLMResponse
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.conversation.entity import Message, Run
from domain.conversation.exceptions import (
    ConversationArchivedException,
    ConversationNotFoundException,
    LLMProviderException,
)
from core.logging_config import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChatApplicationService:
    """Orchestrates sending a message to LLM and streaming the response."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        llm: LLMPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm

    async def _load_history(self, uow, conversation_id: int) -> list[LLMMessage]:
        """Load conversation messages as LLMMessage list."""
        messages = await uow.message_repository.list_by_conversation(conversation_id, limit=200)
        return [LLMMessage(role=m.role, content=m.content) for m in messages]

    async def send_message_stream(
        self,
        conversation_id: int,
        dto: ChatRequestDTO,
    ) -> AsyncIterator[str]:
        """Send a user message and stream the assistant response as SSE events.

        Yields SSE-formatted strings: `data: {...}\\n\\n`
        """
        # Phase 1: persist user message and create run
        async with self._uow_factory() as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            if not conv.is_active():
                raise ConversationArchivedException(conversation_id)

            model = dto.model or conv.model
            now = _utcnow()

            # Create user message
            user_msg = Message(
                id=None,
                conversation_id=conversation_id,
                role="user",
                content=dto.message,
                created_at=now,
            )
            user_msg = await uow.message_repository.create(user_msg)

            # Create run
            run = Run(
                id=None,
                conversation_id=conversation_id,
                status="running",
                model=model,
                started_at=now,
                created_at=now,
            )
            run = await uow.run_repository.create(run)

            # Load history for LLM context
            history = await self._load_history(uow, conversation_id)

            await uow.commit()

        run_id = run.id
        user_msg_id = user_msg.id

        # Build LLM messages
        llm_messages: list[LLMMessage] = []
        # Add system prompt if present
        if conv.system_prompt:
            llm_messages.append(LLMMessage(role="system", content=conv.system_prompt))
        llm_messages.extend(history)

        # Yield user message event
        yield _sse_event(
            "message_created",
            {
                "message_id": user_msg_id,
                "role": "user",
            },
        )

        # Phase 2: stream LLM response
        full_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        try:
            async for chunk in self._llm.stream(
                llm_messages,
                model=model,
                temperature=dto.temperature,
                max_tokens=dto.max_tokens,
            ):
                if chunk.content:
                    full_content += chunk.content
                    yield _sse_event(
                        "message_delta",
                        {
                            "content": chunk.content,
                        },
                    )
                # Capture usage from final chunk
                if chunk.total_tokens > 0:
                    prompt_tokens = chunk.prompt_tokens
                    completion_tokens = chunk.completion_tokens
                    total_tokens = chunk.total_tokens

        except Exception as exc:
            logger.error("llm_stream_failed", error=str(exc), run_id=run_id)
            # Persist failure
            async with self._uow_factory() as uow:
                run_entity = await uow.run_repository.get_by_id(run_id)
                if run_entity:
                    run_entity.mark_failed(str(exc))
                    await uow.run_repository.update(run_entity)
                await uow.commit()

            yield _sse_event(
                "error", {"message": "An error occurred while generating the response."}
            )
            yield _sse_event("done", {})
            return

        # Phase 3: persist assistant message and complete run
        async with self._uow_factory() as uow:
            assistant_msg = Message(
                id=None,
                conversation_id=conversation_id,
                role="assistant",
                content=full_content,
                run_id=run_id,
                token_count=completion_tokens,
                created_at=_utcnow(),
            )
            assistant_msg = await uow.message_repository.create(assistant_msg)

            run_entity = await uow.run_repository.get_by_id(run_id)
            if run_entity:
                run_entity.mark_completed(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
                await uow.run_repository.update(run_entity)

            await uow.commit()

        yield _sse_event(
            "message_complete",
            {
                "message_id": assistant_msg.id,
                "role": "assistant",
                "content": full_content,
            },
        )
        yield _sse_event(
            "run_complete",
            {
                "run_id": run_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        )
        yield _sse_event("done", {})

    async def send_message_sync(
        self,
        conversation_id: int,
        dto: ChatRequestDTO,
    ) -> dict:
        """Send a user message and return the full assistant response (non-streaming)."""
        # Phase 1: persist user message and create run
        async with self._uow_factory() as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            if not conv.is_active():
                raise ConversationArchivedException(conversation_id)

            model = dto.model or conv.model
            now = _utcnow()

            user_msg = Message(
                id=None,
                conversation_id=conversation_id,
                role="user",
                content=dto.message,
                created_at=now,
            )
            user_msg = await uow.message_repository.create(user_msg)

            run = Run(
                id=None,
                conversation_id=conversation_id,
                status="running",
                model=model,
                started_at=now,
                created_at=now,
            )
            run = await uow.run_repository.create(run)

            history = await self._load_history(uow, conversation_id)
            await uow.commit()

        run_id = run.id

        llm_messages: list[LLMMessage] = []
        if conv.system_prompt:
            llm_messages.append(LLMMessage(role="system", content=conv.system_prompt))
        llm_messages.extend(history)

        # Phase 2: call LLM
        try:
            response: LLMResponse = await self._llm.generate(
                llm_messages,
                model=model,
                temperature=dto.temperature,
                max_tokens=dto.max_tokens,
            )
        except Exception as exc:
            logger.error("llm_generate_failed", error=str(exc), run_id=run_id)
            async with self._uow_factory() as uow:
                run_entity = await uow.run_repository.get_by_id(run_id)
                if run_entity:
                    run_entity.mark_failed(str(exc))
                    await uow.run_repository.update(run_entity)
                await uow.commit()
            raise LLMProviderException(str(exc))

        # Phase 3: persist assistant message and complete run
        async with self._uow_factory() as uow:
            assistant_msg = Message(
                id=None,
                conversation_id=conversation_id,
                role="assistant",
                content=response.content,
                run_id=run_id,
                token_count=response.completion_tokens,
                created_at=_utcnow(),
            )
            assistant_msg = await uow.message_repository.create(assistant_msg)

            run_entity = await uow.run_repository.get_by_id(run_id)
            if run_entity:
                run_entity.mark_completed(
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                )
                await uow.run_repository.update(run_entity)

            await uow.commit()

        return {
            "message": MessageDTO_Agent.model_validate(assistant_msg).model_dump(),
            "run": RunDTO.model_validate(run_entity).model_dump() if run_entity else None,
        }


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
