# input: 领域实体 ChatRoom, Message, Scenario, AnalysisReport, CoachingSession, CoachingMessage
# output: ChatRoomRepository, MessageRepository, ScenarioRepository, AnalysisReportRepository, CoachingSessionRepository, CoachingMessageRepository ABC 仓储接口
# owner: wanhua.gu
# pos: 领域层 - 利益相关者聊天仓储接口定义；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Repository abstractions for stakeholder chat aggregate."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .entity import AnalysisReport, ChatRoom, CoachingMessage, CoachingSession, Message
from .scenario_entity import Scenario


class ChatRoomRepository(ABC):
    """Contract for persisting and querying stakeholder chat rooms."""

    @abstractmethod
    async def create(self, room: ChatRoom) -> ChatRoom: ...

    @abstractmethod
    async def get_by_id(self, room_id: int) -> Optional[ChatRoom]: ...

    @abstractmethod
    async def list_rooms(self, *, skip: int = 0, limit: int = 50) -> list[ChatRoom]: ...

    @abstractmethod
    async def update_last_message_at(self, room_id: int, timestamp: datetime) -> None: ...

    @abstractmethod
    async def delete(self, room_id: int) -> bool: ...


class MessageRepository(ABC):
    """Contract for persisting and querying stakeholder chat messages."""

    @abstractmethod
    async def create(self, message: Message) -> Message: ...

    @abstractmethod
    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[Message]: ...


class ScenarioRepository(ABC):
    """Contract for persisting and querying conversation scenario templates."""

    @abstractmethod
    async def create(self, scenario: Scenario) -> Scenario: ...

    @abstractmethod
    async def get_by_id(self, scenario_id: int) -> Optional[Scenario]: ...

    @abstractmethod
    async def list_all(self, *, skip: int = 0, limit: int = 50) -> list[Scenario]: ...

    @abstractmethod
    async def update(self, scenario: Scenario) -> Scenario: ...

    @abstractmethod
    async def delete(self, scenario_id: int) -> bool: ...


class AnalysisReportRepository(ABC):
    """Contract for persisting and querying stakeholder analysis reports."""

    @abstractmethod
    async def create(self, report: AnalysisReport) -> AnalysisReport: ...

    @abstractmethod
    async def get_by_id(self, report_id: int) -> Optional[AnalysisReport]: ...

    @abstractmethod
    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[AnalysisReport]: ...


class CoachingSessionRepository(ABC):
    """Contract for persisting and querying coaching sessions."""

    @abstractmethod
    async def create(self, session: CoachingSession) -> CoachingSession: ...

    @abstractmethod
    async def get_by_id(self, session_id: int) -> Optional[CoachingSession]: ...

    @abstractmethod
    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[CoachingSession]: ...


class CoachingMessageRepository(ABC):
    """Contract for persisting and querying coaching messages."""

    @abstractmethod
    async def create(self, message: CoachingMessage) -> CoachingMessage: ...

    @abstractmethod
    async def list_by_session_id(
        self, session_id: int, *, skip: int = 0, limit: int = 200
    ) -> list[CoachingMessage]: ...
