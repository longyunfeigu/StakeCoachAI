# input: SQLAlchemy AsyncSession, CompetencyEvaluationModel ORM
# output: SQLAlchemyCompetencyEvaluationRepository 仓储实现
# owner: wanhua.gu
# pos: 基础设施层 - 能力评估仓储 SQLAlchemy 实现；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SQLAlchemy-backed repository for competency evaluations."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.stakeholder.competency_entity import CompetencyEvaluation
from domain.stakeholder.repository import CompetencyEvaluationRepository
from infrastructure.models.competency import CompetencyEvaluationModel


class SQLAlchemyCompetencyEvaluationRepository(CompetencyEvaluationRepository):
    """Persist competency evaluations using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: CompetencyEvaluationModel) -> CompetencyEvaluation:
        return CompetencyEvaluation(
            id=model.id,
            report_id=model.report_id,
            room_id=model.room_id,
            scores=model.scores or {},
            overall_score=model.overall_score,
            created_at=model.created_at,
        )

    async def create(self, evaluation: CompetencyEvaluation) -> CompetencyEvaluation:
        model = CompetencyEvaluationModel(
            report_id=evaluation.report_id,
            room_id=evaluation.room_id,
            scores=evaluation.scores,
            overall_score=evaluation.overall_score,
            created_at=evaluation.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_report_id(self, report_id: int) -> Optional[CompetencyEvaluation]:
        result = await self.session.execute(
            select(CompetencyEvaluationModel).where(
                CompetencyEvaluationModel.report_id == report_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, *, skip: int = 0, limit: int = 500) -> list[CompetencyEvaluation]:
        query = (
            select(CompetencyEvaluationModel)
            .order_by(CompetencyEvaluationModel.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]
