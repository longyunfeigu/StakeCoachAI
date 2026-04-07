"""
数据库模型基类（SQLAlchemy 2.0 风格）
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# 元数据对象用于数据库迁移
metadata = Base.metadata
