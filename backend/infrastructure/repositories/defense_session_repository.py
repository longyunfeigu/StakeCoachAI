# input: AsyncSession, DefenseSessionModel
# output: SQLAlchemyDefenseSessionRepository
# owner: wanhua.gu
# pos: 基础设施层 - 答辩准备会话仓储实现；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SQLAlchemy implementation of DefenseSessionRepository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.defense_prep.entity import DefenseSession, DefenseSessionStatus
from domain.defense_prep.repository import DefenseSessionRepository
from domain.defense_prep.scenario import ScenarioType
from domain.defense_prep.value_objects import (
    DocumentSummary,
    PlannedQuestion,
    QuestionStrategy,
    Section,
)
from infrastructure.models.defense_session import DefenseSessionModel


class SQLAlchemyDefenseSessionRepository(DefenseSessionRepository):
    """SQLAlchemy-backed defense session repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _to_entity(self, model: DefenseSessionModel) -> DefenseSession:
        doc_data = model.document_summary or {}
        summary = DocumentSummary(
            title=doc_data.get("title", ""),
            sections=[
                Section(
                    title=s.get("title", ""),
                    bullet_points=s.get("bullet_points", []),
                )
                for s in doc_data.get("sections", [])
            ],
            key_data=doc_data.get("key_data", []),
            raw_text=doc_data.get("raw_text", ""),
        )

        strategy: Optional[QuestionStrategy] = None
        if model.question_strategy:
            qs_data = model.question_strategy
            strategy = QuestionStrategy(
                questions=[
                    PlannedQuestion(
                        question=q.get("question", ""),
                        dimension=q.get("dimension", ""),
                        difficulty=q.get("difficulty", "basic"),
                        expected_direction=q.get("expected_direction", ""),
                        asked_by=q.get("asked_by", ""),
                    )
                    for q in qs_data.get("questions", [])
                ]
            )

        return DefenseSession(
            id=model.id,
            persona_ids=model.persona_ids,
            scenario_type=ScenarioType(model.scenario_type),
            document_summary=summary,
            question_strategy=strategy,
            room_id=model.room_id,
            status=model.status,
            created_at=model.created_at,
        )

    def _summary_to_dict(self, summary: DocumentSummary) -> dict:
        return {
            "title": summary.title,
            "sections": [
                {"title": s.title, "bullet_points": s.bullet_points} for s in summary.sections
            ],
            "key_data": summary.key_data,
            "raw_text": summary.raw_text,
        }

    def _strategy_to_dict(self, strategy: QuestionStrategy) -> dict:
        return {
            "questions": [
                {
                    "question": q.question,
                    "dimension": q.dimension,
                    "difficulty": q.difficulty,
                    "expected_direction": q.expected_direction,
                    "asked_by": q.asked_by,
                }
                for q in strategy.questions
            ]
        }

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(self, session: DefenseSession) -> DefenseSession:
        model = DefenseSessionModel(
            persona_ids=session.persona_ids,
            scenario_type=session.scenario_type.value,
            document_summary=self._summary_to_dict(session.document_summary),
            question_strategy=(
                self._strategy_to_dict(session.question_strategy)
                if session.question_strategy
                else None
            ),
            room_id=session.room_id,
            status=session.status,
        )
        self.session.add(model)
        await self.session.flush()
        session.id = model.id
        session.created_at = model.created_at
        return session

    async def get_by_id(self, session_id: int) -> Optional[DefenseSession]:
        result = await self.session.execute(
            select(DefenseSessionModel).where(DefenseSessionModel.id == session_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, session: DefenseSession) -> DefenseSession:
        result = await self.session.execute(
            select(DefenseSessionModel).where(DefenseSessionModel.id == session.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"DefenseSession {session.id} not found")
        model.status = session.status
        model.room_id = session.room_id
        model.question_strategy = (
            self._strategy_to_dict(session.question_strategy) if session.question_strategy else None
        )
        await self.session.flush()
        return session

    async def list_all(self, *, skip: int = 0, limit: int = 20) -> list[DefenseSession]:
        result = await self.session.execute(
            select(DefenseSessionModel)
            .order_by(DefenseSessionModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]
