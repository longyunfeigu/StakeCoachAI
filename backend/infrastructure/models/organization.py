# input: SQLAlchemy Base 基类
# output: OrganizationModel, TeamModel, PersonaRelationshipModel ORM 模型
# owner: wanhua.gu
# pos: 基础设施层 - 组织上下文 ORM 模型（组织、团队、角色关系）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Organization context database model definitions."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from .base import Base


class OrganizationModel(Base):
    """ORM mapping for organizations table."""

    __tablename__ = "organizations"
    __table_args__ = {"comment": "组织/公司"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(255), nullable=False, comment="组织名称")
    industry = Column(String(255), default="", comment="行业")
    description = Column(Text, default="", comment="组织描述")
    context_prompt = Column(Text, default="", comment="注入角色 system prompt 的组织背景文本")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<OrganizationModel(id={self.id}, name='{self.name}')>"


class TeamModel(Base):
    """ORM mapping for teams table."""

    __tablename__ = "teams"
    __table_args__ = {"comment": "部门/团队"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属组织ID",
    )
    name = Column(String(255), nullable=False, comment="团队名称")
    description = Column(Text, default="", comment="团队职责描述")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<TeamModel(id={self.id}, name='{self.name}')>"


class PersonaRelationshipModel(Base):
    """ORM mapping for persona_relationships table."""

    __tablename__ = "persona_relationships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "from_persona_id",
            "to_persona_id",
            name="ux_persona_rel",
        ),
        {"comment": "角色间关系"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属组织ID",
    )
    from_persona_id = Column(String(50), nullable=False, comment="角色A的ID")
    to_persona_id = Column(String(50), nullable=False, comment="角色B的ID")
    relationship_type = Column(
        String(30), nullable=False, comment="关系类型: superior/subordinate/peer/cross_department"
    )
    description = Column(Text, default="", comment="关系描述")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<PersonaRelationshipModel(id={self.id}, {self.from_persona_id}->{self.to_persona_id})>"
