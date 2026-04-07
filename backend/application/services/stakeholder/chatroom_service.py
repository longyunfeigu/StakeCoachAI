# input: AbstractUnitOfWork, ChatRoomDomainService, PersonaLoader, DTOs
# output: ChatRoomApplicationService 聊天室 CRUD 用例编排
# owner: wanhua.gu
# pos: 应用层服务 - 聊天室创建/查询/列表用例编排；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for stakeholder chat room CRUD."""

from __future__ import annotations

from typing import Callable

from application.services.stakeholder.dto import (
    ChatRoomDTO,
    ChatRoomDetailDTO,
    CreateChatRoomDTO,
    MessageDTO,
)
from domain.common.exceptions import BusinessException, DomainValidationException
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.entity import ChatRoom
from domain.stakeholder.service import ChatRoomDomainService
from shared.codes import BusinessCode


class ChatRoomApplicationService:
    """Orchestrates chat room creation, listing, and detail retrieval."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        persona_loader,
    ) -> None:
        self._uow_factory = uow_factory
        self._persona_loader = persona_loader
        self._domain_service = ChatRoomDomainService()

    async def create_room(self, dto: CreateChatRoomDTO) -> ChatRoomDTO:
        # 1. Validate persona_ids count per room type (domain rule)
        self._domain_service.validate_room_creation(dto.type, dto.persona_ids)

        # 2. Validate all persona_ids exist
        for pid in dto.persona_ids:
            if self._persona_loader.get_persona(pid) is None:
                raise DomainValidationException(
                    f"Persona '{pid}' not found",
                    field="persona_ids",
                    details={"persona_id": pid},
                )

        # 3. Create and persist
        room = ChatRoom(
            id=None,
            name=dto.name,
            type=dto.type,
            persona_ids=dto.persona_ids,
            scenario_id=dto.scenario_id,
        )
        async with self._uow_factory() as uow:
            created = await uow.chat_room_repository.create(room)
            return ChatRoomDTO.model_validate(created)

    async def list_rooms(self, *, skip: int = 0, limit: int = 50) -> list[ChatRoomDTO]:
        async with self._uow_factory(readonly=True) as uow:
            rooms = await uow.chat_room_repository.list_rooms(skip=skip, limit=limit)
            return [ChatRoomDTO.model_validate(r) for r in rooms]

    async def delete_room(self, room_id: int) -> bool:
        async with self._uow_factory() as uow:
            deleted = await uow.chat_room_repository.delete(room_id)
            return deleted

    async def get_room_detail(self, room_id: int, *, message_limit: int = 50) -> ChatRoomDetailDTO:
        async with self._uow_factory(readonly=True) as uow:
            room = await uow.chat_room_repository.get_by_id(room_id)
            if room is None:
                raise BusinessException(
                    code=BusinessCode.CHATROOM_NOT_FOUND,
                    message=f"Chat room {room_id} not found",
                    error_type="ChatRoomNotFound",
                    details={"room_id": room_id},
                )
            messages = await uow.stakeholder_message_repository.list_by_room_id(
                room_id, limit=message_limit
            )
            return ChatRoomDetailDTO(
                room=ChatRoomDTO.model_validate(room),
                messages=[MessageDTO.model_validate(m) for m in messages],
            )
