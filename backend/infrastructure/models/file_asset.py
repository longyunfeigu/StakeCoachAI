"""File asset database model definitions."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    text,
)
from sqlalchemy.sql import func

from .base import Base


class FileAssetModel(Base):
    """ORM mapping for file_assets table."""

    __tablename__ = "file_assets"
    __table_args__ = (
        Index("ix_file_assets_created_at", "created_at"),
        Index("ix_file_assets_owner_created", "owner_id", "created_at"),
        {
            "comment": "文件资源表，记录对象存储中的文件元数据",
        },
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    owner_id = Column(
        Integer,
        nullable=True,
        comment="归属用户ID（可为空；示例项目未强制外键约束）",
    )
    storage_type = Column(
        String(16),
        nullable=False,
        default="local",
        server_default=text("'local'"),
        comment="存储类型：local/s3/oss",
    )
    bucket = Column(
        String(255),
        nullable=True,
        comment="存储桶/容器名称",
    )
    region = Column(
        String(64),
        nullable=True,
        comment="区域名（可为空）",
    )
    key = Column(
        String(512),
        nullable=False,
        comment="对象存储中的Key（路径）",
    )
    unique_key_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="唯一键哈希：SHA-256(storage_type|bucket|key)",
    )
    size = Column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="文件大小（字节）",
    )
    etag = Column(
        String(64),
        nullable=True,
        comment="存储返回的ETag/校验值",
    )
    content_type = Column(
        String(100),
        nullable=True,
        comment="MIME类型",
    )
    original_filename = Column(
        String(255),
        nullable=True,
        comment="原始文件名",
    )
    kind = Column(
        String(50),
        nullable=True,
        comment="业务分类，如 avatar/document",
    )
    is_public = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="是否公共可读",
    )
    extra_metadata = Column(
        "metadata",
        JSON,
        nullable=True,
        default=dict,
        comment="扩展元数据（JSON）",
    )
    url = Column(
        String(1024),
        nullable=True,
        comment="公共/CDN URL快照（可选）",
    )
    status = Column(
        String(20),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="文件状态：pending/active/deleted",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="删除时间（软删除）",
    )

    def __repr__(self) -> str:
        return (
            "<FileAssetModel(id={id}, key='{key}', status='{status}', "
            "storage_type='{storage_type}')>"
        ).format(
            id=self.id,
            key=self.key,
            status=self.status,
            storage_type=self.storage_type,
        )
