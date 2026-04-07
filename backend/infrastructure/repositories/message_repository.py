# input: SQLAlchemy AsyncSession, MessageModel ORM
# output: SQLAlchemyMessageRepository 仓储实现
# owner: unknown
# pos: 基础设施层 - 消息仓储 SQLAlchemy 实现；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SQLAlchemy-backed repository for messages."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.conversation.entity import Message
from domain.conversation.repository import MessageRepository
from infrastructure.models.conversation import MessageModel


class SQLAlchemyMessageRepository(MessageRepository):
    """Persist message entities using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: MessageModel) -> Message:
        return Message(
            id=model.id,
            conversation_id=model.conversation_id,
            role=model.role,
            content=model.content,
            run_id=model.run_id,
            token_count=model.token_count,
            metadata=dict(model.extra_metadata or {}),
            created_at=model.created_at,
        )

    async def create(self, message: Message) -> Message:
        model = MessageModel(
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            run_id=message.run_id,
            token_count=message.token_count,
            extra_metadata=message.metadata or {},
            created_at=message.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, message_id: int) -> Optional[Message]:
        result = await self.session.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Message]:
        query = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc(), MessageModel.id.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_conversation(self, conversation_id: int) -> int:
        query = (
            select(func.count())
            .select_from(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
        )
        result = await self.session.execute(query)
        return int(result.scalar() or 0)
