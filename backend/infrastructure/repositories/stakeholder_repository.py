# input: SQLAlchemy AsyncSession, ChatRoomModel/StakeholderMessageModel/ScenarioModel/AnalysisReportModel/CoachingSessionModel/CoachingMessageModel ORM
# output: SQLAlchemyChatRoomRepository, SQLAlchemyStakeholderMessageRepository, SQLAlchemyScenarioRepository, SQLAlchemyAnalysisReportRepository, SQLAlchemyCoachingSessionRepository, SQLAlchemyCoachingMessageRepository 仓储实现
# owner: wanhua.gu
# pos: 基础设施层 - 利益相关者聊天、场景、分析、复盘仓储 SQLAlchemy 实现；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SQLAlchemy-backed repositories for stakeholder chat aggregate."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain.stakeholder.entity import (
    AnalysisReport,
    ChatRoom,
    CoachingMessage,
    CoachingSession,
    Message,
)
from domain.stakeholder.repository import (
    AnalysisReportRepository,
    ChatRoomRepository,
    CoachingMessageRepository,
    CoachingSessionRepository,
    MessageRepository,
    ScenarioRepository,
)
from domain.stakeholder.scenario_entity import Scenario
from infrastructure.models.scenario import ScenarioModel
from infrastructure.models.stakeholder import (
    AnalysisReportModel,
    ChatRoomModel,
    CoachingMessageModel,
    CoachingSessionModel,
    StakeholderMessageModel,
)


class SQLAlchemyChatRoomRepository(ChatRoomRepository):
    """Persist stakeholder chat rooms using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: ChatRoomModel) -> ChatRoom:
        return ChatRoom(
            id=model.id,
            name=model.name,
            type=model.type,
            persona_ids=list(model.persona_ids or []),
            scenario_id=model.scenario_id,
            created_at=model.created_at,
            last_message_at=model.last_message_at,
        )

    async def create(self, room: ChatRoom) -> ChatRoom:
        model = ChatRoomModel(
            name=room.name,
            type=room.type,
            persona_ids=room.persona_ids,
            scenario_id=room.scenario_id,
            created_at=room.created_at,
            last_message_at=room.last_message_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, room_id: int) -> Optional[ChatRoom]:
        result = await self.session.execute(
            select(ChatRoomModel).where(ChatRoomModel.id == room_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_rooms(self, *, skip: int = 0, limit: int = 50) -> list[ChatRoom]:
        query = (
            select(ChatRoomModel)
            .order_by(ChatRoomModel.last_message_at.desc().nullslast(), ChatRoomModel.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_last_message_at(self, room_id: int, timestamp: datetime) -> None:
        await self.session.execute(
            update(ChatRoomModel)
            .where(ChatRoomModel.id == room_id)
            .values(last_message_at=timestamp)
        )
        await self.session.flush()

    async def delete(self, room_id: int) -> bool:
        result = await self.session.execute(
            delete(ChatRoomModel).where(ChatRoomModel.id == room_id)
        )
        await self.session.flush()
        return result.rowcount > 0


class SQLAlchemyStakeholderMessageRepository(MessageRepository):
    """Persist stakeholder chat messages using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: StakeholderMessageModel) -> Message:
        return Message(
            id=model.id,
            room_id=model.room_id,
            sender_type=model.sender_type,
            sender_id=model.sender_id,
            content=model.content,
            timestamp=model.timestamp,
            emotion_score=model.emotion_score,
            emotion_label=model.emotion_label,
        )

    async def create(self, message: Message) -> Message:
        model = StakeholderMessageModel(
            room_id=message.room_id,
            sender_type=message.sender_type,
            sender_id=message.sender_id,
            content=message.content,
            timestamp=message.timestamp,
            emotion_score=message.emotion_score,
            emotion_label=message.emotion_label,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[Message]:
        query = (
            select(StakeholderMessageModel)
            .where(StakeholderMessageModel.room_id == room_id)
            .order_by(StakeholderMessageModel.timestamp.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]


class SQLAlchemyScenarioRepository(ScenarioRepository):
    """Persist scenario templates using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: ScenarioModel) -> Scenario:
        return Scenario(
            id=model.id,
            name=model.name,
            description=model.description or "",
            context_prompt=model.context_prompt or "",
            suggested_persona_ids=list(model.suggested_persona_ids or []),
            created_at=model.created_at,
        )

    async def create(self, scenario: Scenario) -> Scenario:
        model = ScenarioModel(
            name=scenario.name,
            description=scenario.description,
            context_prompt=scenario.context_prompt,
            suggested_persona_ids=scenario.suggested_persona_ids,
            created_at=scenario.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, scenario_id: int) -> Optional[Scenario]:
        result = await self.session.execute(
            select(ScenarioModel).where(ScenarioModel.id == scenario_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, *, skip: int = 0, limit: int = 50) -> list[Scenario]:
        query = select(ScenarioModel).order_by(ScenarioModel.id.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, scenario: Scenario) -> Scenario:
        result = await self.session.execute(
            select(ScenarioModel).where(ScenarioModel.id == scenario.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Scenario {scenario.id} not found")
        model.name = scenario.name
        model.description = scenario.description
        model.context_prompt = scenario.context_prompt
        model.suggested_persona_ids = scenario.suggested_persona_ids
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def delete(self, scenario_id: int) -> bool:
        # Nullify scenario_id on rooms referencing this scenario
        await self.session.execute(
            update(ChatRoomModel)
            .where(ChatRoomModel.scenario_id == scenario_id)
            .values(scenario_id=None)
        )
        result = await self.session.execute(
            delete(ScenarioModel).where(ScenarioModel.id == scenario_id)
        )
        await self.session.flush()
        return result.rowcount > 0


class SQLAlchemyAnalysisReportRepository(AnalysisReportRepository):
    """Persist stakeholder analysis reports using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: AnalysisReportModel) -> AnalysisReport:
        return AnalysisReport(
            id=model.id,
            room_id=model.room_id,
            summary=model.summary,
            content=model.content or {},
            created_at=model.created_at,
        )

    async def create(self, report: AnalysisReport) -> AnalysisReport:
        model = AnalysisReportModel(
            room_id=report.room_id,
            summary=report.summary,
            content=report.content,
            created_at=report.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, report_id: int) -> Optional[AnalysisReport]:
        result = await self.session.execute(
            select(AnalysisReportModel).where(AnalysisReportModel.id == report_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[AnalysisReport]:
        query = (
            select(AnalysisReportModel)
            .where(AnalysisReportModel.room_id == room_id)
            .order_by(AnalysisReportModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]


class SQLAlchemyCoachingSessionRepository(CoachingSessionRepository):
    """Persist coaching sessions using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: CoachingSessionModel) -> CoachingSession:
        return CoachingSession(
            id=model.id,
            room_id=model.room_id,
            report_id=model.report_id,
            status=model.status,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )

    async def create(self, cs: CoachingSession) -> CoachingSession:
        model = CoachingSessionModel(
            room_id=cs.room_id,
            report_id=cs.report_id,
            status=cs.status,
            created_at=cs.created_at,
            completed_at=cs.completed_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, session_id: int) -> Optional[CoachingSession]:
        result = await self.session.execute(
            select(CoachingSessionModel).where(CoachingSessionModel.id == session_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[CoachingSession]:
        query = (
            select(CoachingSessionModel)
            .where(CoachingSessionModel.room_id == room_id)
            .order_by(CoachingSessionModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]


class SQLAlchemyCoachingMessageRepository(CoachingMessageRepository):
    """Persist coaching messages using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: CoachingMessageModel) -> CoachingMessage:
        return CoachingMessage(
            id=model.id,
            session_id=model.session_id,
            role=model.role,
            content=model.content,
            created_at=model.created_at,
        )

    async def create(self, msg: CoachingMessage) -> CoachingMessage:
        model = CoachingMessageModel(
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def list_by_session_id(
        self, session_id: int, *, skip: int = 0, limit: int = 200
    ) -> list[CoachingMessage]:
        query = (
            select(CoachingMessageModel)
            .where(CoachingMessageModel.session_id == session_id)
            .order_by(CoachingMessageModel.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]
