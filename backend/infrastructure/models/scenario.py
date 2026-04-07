# input: SQLAlchemy Base 基类
# output: ScenarioModel ORM 模型
# owner: wanhua.gu
# pos: 基础设施层 - 场景模板 ORM 模型；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Scenario template database model definition."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from .base import Base


class ScenarioModel(Base):
    """ORM mapping for stakeholder_scenarios table."""

    __tablename__ = "stakeholder_scenarios"
    __table_args__ = {"comment": "利益相关者对话场景模板"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(255), nullable=False, comment="场景名称")
    description = Column(Text, default="", comment="场景描述")
    context_prompt = Column(Text, nullable=False, default="", comment="场景上下文 prompt")
    suggested_persona_ids = Column(JSON, default=list, comment="建议角色ID列表")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<ScenarioModel(id={self.id}, name='{self.name}')>"
