# input: 领域实体 ChatRoom, Message, Scenario, AnalysisReport, CoachingSession, CoachingMessage, Organization, Team, PersonaRelationship, CompetencyEvaluation
# output: ChatRoomRepository, MessageRepository, ScenarioRepository, AnalysisReportRepository, CoachingSessionRepository, CoachingMessageRepository, OrganizationRepository, TeamRepository, PersonaRelationshipRepository, CompetencyEvaluationRepository ABC 仓储接口
# owner: wanhua.gu
# pos: 领域层 - 利益相关者聊天仓储接口定义；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Repository abstractions for stakeholder chat aggregate."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .competency_entity import CompetencyEvaluation
from .entity import AnalysisReport, ChatRoom, CoachingMessage, CoachingSession, Message
from .organization_entity import Organization, PersonaRelationship, Team
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


class OrganizationRepository(ABC):
    """Contract for persisting and querying organizations."""

    @abstractmethod
    async def create(self, org: Organization) -> Organization: ...

    @abstractmethod
    async def get_by_id(self, org_id: int) -> Optional[Organization]: ...

    @abstractmethod
    async def list_all(self, *, skip: int = 0, limit: int = 50) -> list[Organization]: ...

    @abstractmethod
    async def update(self, org: Organization) -> Organization: ...

    @abstractmethod
    async def delete(self, org_id: int) -> bool: ...


class TeamRepository(ABC):
    """Contract for persisting and querying teams."""

    @abstractmethod
    async def create(self, team: Team) -> Team: ...

    @abstractmethod
    async def get_by_id(self, team_id: int) -> Optional[Team]: ...

    @abstractmethod
    async def list_by_organization(self, org_id: int) -> list[Team]: ...

    @abstractmethod
    async def update(self, team: Team) -> Team: ...

    @abstractmethod
    async def delete(self, team_id: int) -> bool: ...


class PersonaRelationshipRepository(ABC):
    """Contract for persisting and querying persona relationships."""

    @abstractmethod
    async def create(self, rel: PersonaRelationship) -> PersonaRelationship: ...

    @abstractmethod
    async def get_by_id(self, rel_id: int) -> Optional[PersonaRelationship]: ...

    @abstractmethod
    async def list_by_organization(self, org_id: int) -> list[PersonaRelationship]: ...

    @abstractmethod
    async def list_by_persona(self, org_id: int, persona_id: str) -> list[PersonaRelationship]: ...

    @abstractmethod
    async def update(self, rel: PersonaRelationship) -> PersonaRelationship: ...

    @abstractmethod
    async def delete(self, rel_id: int) -> bool: ...


class CompetencyEvaluationRepository(ABC):
    """Contract for persisting and querying competency evaluations."""

    @abstractmethod
    async def create(self, evaluation: CompetencyEvaluation) -> CompetencyEvaluation: ...

    @abstractmethod
    async def get_by_report_id(self, report_id: int) -> Optional[CompetencyEvaluation]: ...

    @abstractmethod
    async def list_all(self, *, skip: int = 0, limit: int = 500) -> list[CompetencyEvaluation]: ...
