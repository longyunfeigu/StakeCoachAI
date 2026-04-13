# input: 领域实体 ChatRoom, Message, Scenario, AnalysisReport, CoachingSession, CoachingMessage, Organization, Team, PersonaRelationship, CompetencyEvaluation, Persona, Evidence
# output: ChatRoomRepository, MessageRepository, ScenarioRepository, AnalysisReportRepository, CoachingSessionRepository, CoachingMessageRepository, OrganizationRepository, TeamRepository, PersonaRelationshipRepository, CompetencyEvaluationRepository, StakeholderPersonaRepository ABC 仓储接口
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
from .persona_entity import Evidence, Persona
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

    @abstractmethod
    async def update_context_summary(
        self, room_id: int, summary: str, up_to_message_id: int
    ) -> None: ...


class MessageRepository(ABC):
    """Contract for persisting and querying stakeholder chat messages."""

    @abstractmethod
    async def create(self, message: Message) -> Message: ...

    @abstractmethod
    async def list_by_room_id(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[Message]: ...

    @abstractmethod
    async def count_by_room_id(self, room_id: int) -> int: ...


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


class StakeholderPersonaRepository(ABC):
    """Contract for persisting and querying structured (5-layer) personas.

    Story 2.2: v2 结构化 persona 的 DB 持久化；v1 markdown persona 仍由
    PersonaLoader 从磁盘加载，不经此仓储。
    """

    @abstractmethod
    async def save_structured_persona(self, persona: Persona) -> Persona:
        """Upsert a structured persona (schema_version=2 expected).

        - 若 id 不存在则 INSERT；存在则 UPDATE
        - 证据链 (evidence_citations) 同时持久化
        """
        ...

    @abstractmethod
    async def get_by_id(self, persona_id: str) -> Optional[Persona]: ...

    @abstractmethod
    async def get_with_evidence(self, persona_id: str) -> Optional[tuple[Persona, list[Evidence]]]:
        """Return persona + its evidence citations.

        Returns None if persona not found.
        """
        ...

    @abstractmethod
    async def list_all(self, *, schema_version: Optional[int] = None) -> list[Persona]:
        """List personas, optionally filtered by schema_version."""
        ...

    @abstractmethod
    async def save_migration_error(
        self,
        persona_id: str,
        error: str,
        *,
        legacy_markdown: Optional[str] = None,
        name: str = "",
        role: str = "",
    ) -> None:
        """Record a v1→v2 migration failure (Story 2.3 AC4).

        Behaviour:
        - 若 persona 不存在 → 插入一条 schema_version=1 的 stub 记录 (full_content=legacy_markdown)
        - 若 persona 已存在 → 保持 schema_version 和 full_content 不变
        - 在 structured_profile 写入 ``{"_error": error, "_attempted_at": iso}``，绝不升级 schema_version

        实现方应保证此方法不抛异常即使记录已 v2（应作为 no-op 或保留原状）。
        """
        ...
