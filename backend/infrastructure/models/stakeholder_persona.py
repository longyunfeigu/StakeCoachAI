# input: SQLAlchemy Base 基类, TimestampMixin
# output: StakeholderPersonaModel ORM 模型 (stakeholder_personas 表, v1+v2 混合 schema)
# owner: wanhua.gu
# pos: 基础设施层 - 利益相关者画像 ORM 模型 (v2 5-layer persona)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Stakeholder persona database model (v2 5-layer structured)."""

from sqlalchemy import Column, Float, Integer, JSON, String, Text

from .base import Base
from .mixins import TimestampMixin


class StakeholderPersonaModel(Base, TimestampMixin):
    """ORM mapping for stakeholder_personas table.

    All personas use v2 5-layer structured format stored in structured_profile (JSON).
    """

    __tablename__ = "stakeholder_personas"
    __table_args__ = (
        {"comment": "利益相关者画像 (v2 5-layer 结构化)"},
    )

    id = Column(String(50), primary_key=True, comment="画像ID (与 markdown 文件名一致)")
    name = Column(String(255), nullable=False, comment="角色名")
    role = Column(String(255), nullable=False, comment="职位/角色")
    avatar_color = Column(String(20), nullable=True, comment="头像颜色")
    organization_id = Column(Integer, nullable=True, comment="所属组织ID")
    team_id = Column(Integer, nullable=True, comment="所属团队ID")
    profile_summary = Column(
        Text, nullable=False, default="", server_default="", comment="画像摘要"
    )
    voice_id = Column(String(100), nullable=True, comment="TTS voice id")
    voice_speed = Column(
        Float, nullable=False, default=1.0, server_default="1.0", comment="TTS 语速"
    )
    voice_style = Column(String(50), nullable=True, comment="TTS 风格")

    # v2 structured fields
    structured_profile = Column(
        JSON,
        nullable=True,
        comment="v2 5-layer 结构化数据 (hard_rules/identity/expression/decision/interpersonal)",
    )
    evidence_citations = Column(JSON, nullable=True, comment="v2 证据链 (list[Evidence])")
    source_materials = Column(JSON, nullable=True, comment="v2 原始素材 id/片段列表")

    def __repr__(self) -> str:
        return f"<StakeholderPersonaModel(id='{self.id}')>"
