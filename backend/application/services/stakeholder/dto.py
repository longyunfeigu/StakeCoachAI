# input: Pydantic BaseModel
# output: CreateChatRoomDTO, ChatRoomDTO, ChatRoomDetailDTO, SendMessageDTO, CreatePersonaDTO(含 organization_id/team_id), UpdatePersonaDTO(含 organization_id/team_id), CreateScenarioDTO, ScenarioDTO, UpdateScenarioDTO, AnalysisReportDTO, AnalysisReportSummaryDTO, AnalysisContentDTO, Organization/Team/Relationship DTOs, Growth/Competency DTOs
# owner: wanhua.gu
# pos: 应用层 - 聊天室、消息、角色、场景数据传输对象；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""DTOs for stakeholder chat room and message operations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateChatRoomDTO(BaseModel):
    """Input DTO for creating a chat room."""

    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern=r"^(private|group)$")
    persona_ids: list[str] = Field(..., min_length=1)
    scenario_id: Optional[int] = None


class ChatRoomDTO(BaseModel):
    """Output DTO for chat room list/summary."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    type: str
    persona_ids: list[str]
    scenario_id: Optional[int] = None
    created_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None


class MessageDTO(BaseModel):
    """Output DTO for a single message."""

    model_config = {"from_attributes": True}

    id: int
    room_id: int
    sender_type: str
    sender_id: str
    content: str
    timestamp: Optional[datetime] = None
    emotion_score: Optional[int] = None
    emotion_label: Optional[str] = None


class ChatRoomDetailDTO(BaseModel):
    """Output DTO for room detail with messages."""

    room: ChatRoomDTO
    messages: list[MessageDTO] = []


class SendMessageDTO(BaseModel):
    """Input DTO for sending a message to a chat room."""

    content: str = Field(..., min_length=1, max_length=10000)


class CreatePersonaDTO(BaseModel):
    """Input DTO for creating a persona."""

    id: str = Field(..., pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$", min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    avatar_color: str = Field(default="#888888", pattern=r"^#[0-9a-fA-F]{6}$")
    content: str = Field(default="")
    organization_id: Optional[int] = None
    team_id: Optional[int] = None


class UpdatePersonaDTO(BaseModel):
    """Input DTO for updating a persona."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, min_length=1, max_length=200)
    avatar_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    content: Optional[str] = None
    organization_id: Optional[int] = None
    team_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Scenario DTOs
# ---------------------------------------------------------------------------


class CreateScenarioDTO(BaseModel):
    """Input DTO for creating a scenario template."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    context_prompt: str = Field(..., min_length=1)
    suggested_persona_ids: list[str] = Field(default_factory=list)


class ScenarioDTO(BaseModel):
    """Output DTO for a scenario template."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str
    context_prompt: str
    suggested_persona_ids: list[str]
    created_at: Optional[datetime] = None


class UpdateScenarioDTO(BaseModel):
    """Input DTO for updating a scenario template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    context_prompt: Optional[str] = None
    suggested_persona_ids: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Analysis Report DTOs
# ---------------------------------------------------------------------------


class ResistanceItem(BaseModel):
    """A single persona's resistance assessment."""

    persona_id: str
    persona_name: str
    score: int = Field(..., ge=-5, le=5, description="阻力分数 -5(强烈反对) 到 +5(强烈支持)")
    reason: str = Field(..., description="阻力原因分析")


class ArgumentItem(BaseModel):
    """A single effective argument identified."""

    argument: str = Field(..., description="有效论点内容")
    target_persona: str = Field(..., description="论点影响的目标 persona")
    effectiveness: str = Field(..., description="有效性说明")


class SuggestionItem(BaseModel):
    """A communication suggestion for a specific persona."""

    persona_id: str
    persona_name: str
    suggestion: str = Field(..., description="沟通建议")
    priority: str = Field(..., pattern=r"^(high|medium|low)$", description="优先级")


class AnalysisContentDTO(BaseModel):
    """Structured content of an analysis report."""

    resistance_ranking: list[ResistanceItem] = Field(default_factory=list)
    effective_arguments: list[ArgumentItem] = Field(default_factory=list)
    communication_suggestions: list[SuggestionItem] = Field(default_factory=list)


class AnalysisReportDTO(BaseModel):
    """Full output DTO for an analysis report."""

    model_config = {"from_attributes": True}

    id: int
    room_id: int
    summary: str
    content: AnalysisContentDTO
    created_at: Optional[datetime] = None


class AnalysisReportSummaryDTO(BaseModel):
    """Summary DTO for analysis report listing."""

    model_config = {"from_attributes": True}

    id: int
    room_id: int
    summary: str
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Coaching DTOs
# ---------------------------------------------------------------------------


class CoachingMessageDTO(BaseModel):
    """A single coaching message (user or coach)."""

    model_config = {"from_attributes": True}

    id: int
    session_id: int
    role: str  # user | coach
    content: str
    created_at: Optional[datetime] = None


class CoachingSessionDTO(BaseModel):
    """Full coaching session with message history."""

    model_config = {"from_attributes": True}

    id: int
    room_id: int
    report_id: int
    status: str
    messages: list[CoachingMessageDTO] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CoachingSessionSummaryDTO(BaseModel):
    """Summary DTO for coaching session listing."""

    model_config = {"from_attributes": True}

    id: int
    room_id: int
    report_id: int
    status: str
    created_at: Optional[datetime] = None


class CoachingSendDTO(BaseModel):
    """Input DTO for sending a coaching message."""

    content: str = Field(..., min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# Organization DTOs
# ---------------------------------------------------------------------------


class CreateOrganizationDTO(BaseModel):
    """Input DTO for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(default="")
    description: str = Field(default="")
    context_prompt: str = Field(default="")


class OrganizationDTO(BaseModel):
    """Output DTO for an organization."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    industry: str
    description: str
    context_prompt: str
    created_at: Optional[datetime] = None


class UpdateOrganizationDTO(BaseModel):
    """Input DTO for updating an organization."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = None
    description: Optional[str] = None
    context_prompt: Optional[str] = None


class OrganizationDetailDTO(BaseModel):
    """Organization with teams."""

    organization: OrganizationDTO
    teams: list["TeamDTO"] = []


# ---------------------------------------------------------------------------
# Team DTOs
# ---------------------------------------------------------------------------


class CreateTeamDTO(BaseModel):
    """Input DTO for creating a team."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")


class TeamDTO(BaseModel):
    """Output DTO for a team."""

    model_config = {"from_attributes": True}

    id: int
    organization_id: int
    name: str
    description: str
    created_at: Optional[datetime] = None


class UpdateTeamDTO(BaseModel):
    """Input DTO for updating a team."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Persona Relationship DTOs
# ---------------------------------------------------------------------------


class CreateRelationshipDTO(BaseModel):
    """Input DTO for creating a persona relationship."""

    from_persona_id: str = Field(..., min_length=1, max_length=50)
    to_persona_id: str = Field(..., min_length=1, max_length=50)
    relationship_type: str = Field(..., pattern=r"^(superior|subordinate|peer|cross_department)$")
    description: str = Field(default="")


class RelationshipDTO(BaseModel):
    """Output DTO for a persona relationship."""

    model_config = {"from_attributes": True}

    id: int
    organization_id: int
    from_persona_id: str
    to_persona_id: str
    relationship_type: str
    description: str
    created_at: Optional[datetime] = None


class UpdateRelationshipDTO(BaseModel):
    """Input DTO for updating a persona relationship."""

    relationship_type: Optional[str] = Field(
        None, pattern=r"^(superior|subordinate|peer|cross_department)$"
    )
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Competency Evaluation / Growth DTOs
# ---------------------------------------------------------------------------


class DimensionScoreDTO(BaseModel):
    """A single dimension score from LLM-as-Judge evaluation."""

    score: int = Field(..., ge=1, le=5)
    evidence: str = Field(default="")
    suggestion: str = Field(default="")


class CompetencyEvaluationDTO(BaseModel):
    """Output DTO for a competency evaluation."""

    model_config = {"from_attributes": True}

    id: int
    report_id: int
    room_id: int
    room_name: str = ""
    scores: dict[str, DimensionScoreDTO] = Field(default_factory=dict)
    overall_score: float
    created_at: Optional[datetime] = None


class GrowthOverviewDTO(BaseModel):
    """Summary statistics for the growth dashboard."""

    total_sessions: int = 0
    total_evaluations: int = 0
    avg_overall_score: float = 0.0
    latest_score: float = 0.0


class DimensionTrendPointDTO(BaseModel):
    """A single point in a dimension's trend line."""

    date: Optional[datetime] = None
    score: int = 0


class GrowthDashboardDTO(BaseModel):
    """Full growth dashboard response."""

    overview: GrowthOverviewDTO
    evaluations: list[CompetencyEvaluationDTO] = Field(default_factory=list)
    dimension_trends: dict[str, list[DimensionTrendPointDTO]] = Field(default_factory=dict)


class GrowthInsightDTO(BaseModel):
    """LLM-generated cross-session growth insight."""

    insight: str = ""
