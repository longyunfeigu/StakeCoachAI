# input: AbstractUnitOfWork, Conversation/AgentConfig 领域实体
# output: ConversationApplicationService 对话 CRUD 编排
# owner: unknown
# pos: 应用层服务 - 对话与 Agent 配置 CRUD 用例编排；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for conversation and agent config CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

from application.dto import (
    AgentConfigDTO,
    ConversationDTO,
    CreateAgentConfigDTO,
    CreateConversationDTO,
    MessageDTO_Agent,
    RunDTO,
    UpdateAgentConfigDTO,
    UpdateConversationDTO,
)
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.conversation.entity import AgentConfig, Conversation
from domain.conversation.exceptions import (
    AgentConfigNameExistsException,
    AgentConfigNotFoundException,
    ConversationNotFoundException,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationApplicationService:
    """High-level conversation workflows bridging API and domain layers."""

    def __init__(self, uow_factory: Callable[..., AbstractUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # ── Conversation CRUD ──────────────────────────────────────────

    async def create_conversation(self, dto: CreateConversationDTO) -> ConversationDTO:
        now = _utcnow()
        conv = Conversation(
            id=None,
            title=dto.title,
            system_prompt=dto.system_prompt,
            model=dto.model,
            metadata=dto.metadata or {},
            created_at=now,
            updated_at=now,
        )
        async with self._uow_factory() as uow:
            created = await uow.conversation_repository.create(conv)
            return ConversationDTO.model_validate(created)

    async def get_conversation(self, conversation_id: int) -> ConversationDTO:
        async with self._uow_factory(readonly=True) as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            return ConversationDTO.model_validate(conv)

    async def list_conversations(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[list[ConversationDTO], int]:
        async with self._uow_factory(readonly=True) as uow:
            items = await uow.conversation_repository.list(status=status, skip=skip, limit=limit)
            total = await uow.conversation_repository.count(status=status)
            return [ConversationDTO.model_validate(c) for c in items], total

    async def update_conversation(
        self, conversation_id: int, dto: UpdateConversationDTO
    ) -> ConversationDTO:
        async with self._uow_factory() as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            changed = False
            if dto.title is not None:
                conv.update_title(dto.title)
                changed = True
            if dto.system_prompt is not None:
                conv.system_prompt = dto.system_prompt
                changed = True
            if dto.model is not None:
                conv.model = dto.model
                changed = True
            if changed:
                conv._touch()
            updated = await uow.conversation_repository.update(conv)
            return ConversationDTO.model_validate(updated)

    async def delete_conversation(self, conversation_id: int) -> ConversationDTO:
        async with self._uow_factory() as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            conv.soft_delete()
            updated = await uow.conversation_repository.update(conv)
            return ConversationDTO.model_validate(updated)

    # ── Messages ───────────────────────────────────────────────────

    async def list_messages(
        self,
        conversation_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[list[MessageDTO_Agent], int]:
        async with self._uow_factory(readonly=True) as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            items = await uow.message_repository.list_by_conversation(
                conversation_id, skip=skip, limit=limit
            )
            total = await uow.message_repository.count_by_conversation(conversation_id)
            return [MessageDTO_Agent.model_validate(m) for m in items], total

    # ── Runs ───────────────────────────────────────────────────────

    async def list_runs(
        self,
        conversation_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[RunDTO]:
        async with self._uow_factory(readonly=True) as uow:
            conv = await uow.conversation_repository.get_by_id(conversation_id)
            if conv is None:
                raise ConversationNotFoundException(conversation_id)
            items = await uow.run_repository.list_by_conversation(
                conversation_id, skip=skip, limit=limit
            )
            return [RunDTO.model_validate(r) for r in items]

    # ── Agent Config CRUD ──────────────────────────────────────────

    async def create_agent_config(self, dto: CreateAgentConfigDTO) -> AgentConfigDTO:
        now = _utcnow()
        async with self._uow_factory() as uow:
            existing = await uow.agent_config_repository.get_by_name(dto.name)
            if existing is not None:
                raise AgentConfigNameExistsException(dto.name)
            config = AgentConfig(
                id=None,
                name=dto.name,
                system_prompt=dto.system_prompt,
                model=dto.model,
                temperature=dto.temperature,
                max_tokens=dto.max_tokens,
                metadata=dto.metadata or {},
                created_at=now,
                updated_at=now,
            )
            created = await uow.agent_config_repository.create(config)
            return AgentConfigDTO.model_validate(created)

    async def get_agent_config(self, config_id: int) -> AgentConfigDTO:
        async with self._uow_factory(readonly=True) as uow:
            config = await uow.agent_config_repository.get_by_id(config_id)
            if config is None:
                raise AgentConfigNotFoundException(config_id)
            return AgentConfigDTO.model_validate(config)

    async def list_agent_configs(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[list[AgentConfigDTO], int]:
        async with self._uow_factory(readonly=True) as uow:
            items = await uow.agent_config_repository.list(skip=skip, limit=limit)
            total = await uow.agent_config_repository.count()
            return [AgentConfigDTO.model_validate(c) for c in items], total

    async def update_agent_config(
        self, config_id: int, dto: UpdateAgentConfigDTO
    ) -> AgentConfigDTO:
        async with self._uow_factory() as uow:
            config = await uow.agent_config_repository.get_by_id(config_id)
            if config is None:
                raise AgentConfigNotFoundException(config_id)
            if dto.name is not None:
                # Check uniqueness
                existing = await uow.agent_config_repository.get_by_name(dto.name)
                if existing is not None and existing.id != config_id:
                    raise AgentConfigNameExistsException(dto.name)
                config.name = dto.name
            if dto.system_prompt is not None:
                config.system_prompt = dto.system_prompt
            if dto.model is not None:
                config.model = dto.model
            if dto.temperature is not None:
                config.temperature = dto.temperature
            if dto.max_tokens is not None:
                config.max_tokens = dto.max_tokens
            if dto.metadata is not None:
                config.metadata = dto.metadata
            config._touch()
            updated = await uow.agent_config_repository.update(config)
            return AgentConfigDTO.model_validate(updated)

    async def delete_agent_config(self, config_id: int) -> None:
        async with self._uow_factory() as uow:
            config = await uow.agent_config_repository.get_by_id(config_id)
            if config is None:
                raise AgentConfigNotFoundException(config_id)
            await uow.agent_config_repository.delete(config_id)
