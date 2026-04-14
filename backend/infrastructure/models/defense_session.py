# input: SQLAlchemy Base 基类
# output: DefenseSessionModel ORM 模型
# owner: wanhua.gu
# pos: 基础设施层 - 答辩准备会话 ORM 模型；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Defense session database model."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from .base import Base


class DefenseSessionModel(Base):
    """ORM mapping for defense_sessions table."""

    __tablename__ = "defense_sessions"
    __table_args__ = {"comment": "答辩准备会话"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    persona_ids = Column(JSON, nullable=False, comment="答辩官 Persona ID 列表 (1-5)")
    scenario_type = Column(String(50), nullable=False, comment="场景类型")
    document_summary = Column(JSON, nullable=False, comment="文档摘要 (结构化)")
    question_strategy = Column(JSON, nullable=True, comment="提问策略 (LLM 生成)")
    room_id = Column(Integer, nullable=True, comment="关联聊天室 ID")
    status = Column(
        String(20),
        nullable=False,
        default="preparing",
        comment="状态: preparing/in_progress/completed",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )
