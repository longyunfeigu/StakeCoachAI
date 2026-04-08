# input: SQLAlchemy Base 基类
# output: CompetencyEvaluationModel ORM 模型
# owner: wanhua.gu
# pos: 基础设施层 - 能力评估 ORM 模型定义（LLM-as-Judge 6 维度评分）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Competency evaluation database model definition."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from .base import Base


class CompetencyEvaluationModel(Base):
    """ORM mapping for stakeholder_competency_evaluations table."""

    __tablename__ = "stakeholder_competency_evaluations"
    __table_args__ = (
        Index("ix_competency_eval_room_id", "room_id"),
        UniqueConstraint("report_id", name="uq_competency_eval_report_id"),
        {"comment": "利益相关者能力评估（LLM-as-Judge 6维度）"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    report_id = Column(
        Integer,
        ForeignKey("stakeholder_analysis_reports.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联分析报告ID（一对一）",
    )
    room_id = Column(
        Integer,
        ForeignKey("stakeholder_chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属聊天室ID",
    )
    scores = Column(JSON, nullable=False, default=dict, comment="6维度评分JSON")
    overall_score = Column(Float, nullable=False, default=0.0, comment="总体平均分")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="评估时间",
    )

    def __repr__(self) -> str:
        return f"<CompetencyEvaluationModel(id={self.id}, report_id={self.report_id}, overall={self.overall_score})>"
