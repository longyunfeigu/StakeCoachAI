# input: SQLAlchemy Base 基类
# output: ChatRoomModel, StakeholderMessageModel, AnalysisReportModel, CoachingSessionModel, CoachingMessageModel ORM 模型
# owner: wanhua.gu
# pos: 基础设施层 - 利益相关者聊天 ORM 模型定义（含 Coaching 表）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Stakeholder chat aggregate database model definitions."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.sql import func

from .base import Base


class ChatRoomModel(Base):
    """ORM mapping for stakeholder_chat_rooms table."""

    __tablename__ = "stakeholder_chat_rooms"
    __table_args__ = (
        Index("ix_stakeholder_chat_rooms_last_message_at", "last_message_at"),
        {"comment": "利益相关者聊天室"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(255), nullable=False, comment="聊天室名称")
    type = Column(String(20), nullable=False, comment="类型：private/group")
    persona_ids = Column(JSON, nullable=False, default=list, comment="参与角色ID列表")
    scenario_id = Column(Integer, nullable=True, comment="关联场景模板ID")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )
    last_message_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后消息时间",
    )

    def __repr__(self) -> str:
        return f"<ChatRoomModel(id={self.id}, name='{self.name}', type='{self.type}')>"


class StakeholderMessageModel(Base):
    """ORM mapping for stakeholder_messages table."""

    __tablename__ = "stakeholder_messages"
    __table_args__ = (
        Index("ix_stakeholder_messages_room_id", "room_id"),
        Index("ix_stakeholder_messages_room_timestamp", "room_id", "timestamp"),
        {"comment": "利益相关者聊天消息"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    room_id = Column(
        Integer,
        ForeignKey("stakeholder_chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属聊天室ID",
    )
    sender_type = Column(String(20), nullable=False, comment="发送者类型：user/persona/system")
    sender_id = Column(String(100), nullable=False, comment="发送者ID")
    content = Column(Text, nullable=False, comment="消息内容")
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="消息时间",
    )
    emotion_score = Column(SmallInteger, nullable=True, comment="情绪分数 -5~+5")
    emotion_label = Column(String(20), nullable=True, comment="情绪标签")

    def __repr__(self) -> str:
        return (
            f"<StakeholderMessageModel(id={self.id}, room_id={self.room_id}, "
            f"sender_type='{self.sender_type}')>"
        )


class AnalysisReportModel(Base):
    """ORM mapping for stakeholder_analysis_reports table."""

    __tablename__ = "stakeholder_analysis_reports"
    __table_args__ = (
        Index("ix_stakeholder_analysis_reports_room_id", "room_id"),
        {"comment": "利益相关者对话分析报告"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    room_id = Column(
        Integer,
        ForeignKey("stakeholder_chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属聊天室ID",
    )
    summary = Column(Text, nullable=False, comment="分析摘要")
    content = Column(JSON, nullable=False, default=dict, comment="完整报告结构体")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="生成时间",
    )

    def __repr__(self) -> str:
        return f"<AnalysisReportModel(id={self.id}, room_id={self.room_id})>"


class CoachingSessionModel(Base):
    """ORM mapping for stakeholder_coaching_sessions table."""

    __tablename__ = "stakeholder_coaching_sessions"
    __table_args__ = (
        Index("ix_stakeholder_coaching_sessions_room_id", "room_id"),
        {"comment": "利益相关者复盘对话会话"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    room_id = Column(
        Integer,
        ForeignKey("stakeholder_chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属聊天室ID",
    )
    report_id = Column(
        Integer,
        ForeignKey("stakeholder_analysis_reports.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联分析报告ID",
    )
    status = Column(String(20), nullable=False, default="active", comment="状态：active/completed")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")

    def __repr__(self) -> str:
        return f"<CoachingSessionModel(id={self.id}, room_id={self.room_id}, report_id={self.report_id})>"


class CoachingMessageModel(Base):
    """ORM mapping for stakeholder_coaching_messages table."""

    __tablename__ = "stakeholder_coaching_messages"
    __table_args__ = (
        Index("ix_stakeholder_coaching_messages_session_id", "session_id"),
        {"comment": "利益相关者复盘对话消息"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    session_id = Column(
        Integer,
        ForeignKey("stakeholder_coaching_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属会话ID",
    )
    role = Column(String(20), nullable=False, comment="角色：user/coach")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="消息时间",
    )

    def __repr__(self) -> str:
        return f"<CoachingMessageModel(id={self.id}, session_id={self.session_id}, role='{self.role}')>"
