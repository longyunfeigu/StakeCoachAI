"""
数据库配置和连接管理
"""

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from alembic.config import Config
from core.config import settings
from infrastructure.models import Base


# 创建异步引擎
def _build_async_url(database_url: str) -> str:
    """确保数据库URL使用异步驱动"""
    url = make_url(database_url)
    drivername = url.drivername

    if "+" in drivername:
        return database_url

    driver_map = {
        "postgresql": "postgresql+asyncpg",
        "postgres": "postgresql+asyncpg",
        "mysql": "mysql+aiomysql",
        "sqlite": "sqlite+aiosqlite",
    }

    if drivername not in driver_map:
        raise ValueError(
            f"不支持的数据库驱动: {drivername}. 请使用 async 驱动或更新数据库连接字符串"
        )

    async_driver = driver_map[drivername]
    return str(url.set(drivername=async_driver))


engine = create_async_engine(
    _build_async_url(settings.database.url), echo=settings.DEBUG, future=True
)

# 创建异步会话工厂 (SQLAlchemy 1.4 兼容)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（不自动提交，由调用方控制事务）

    使用异步上下文管理器自动关闭会话，无需显式 close。
    """
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    """
    创建所有表

    根据models中定义的所有模型创建对应的数据库表
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """
    删除所有表

    警告：仅用于测试环境，会删除所有数据！
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _run_alembic_upgrade_to_head() -> None:
    """同步执行 Alembic 迁移到最新版本。"""
    project_root = Path(__file__).resolve().parent.parent
    alembic_ini_path = project_root / "alembic.ini"
    alembic_script_path = project_root / "alembic"

    alembic_config = Config(str(alembic_ini_path))
    alembic_config.set_main_option("script_location", str(alembic_script_path))

    # 确保 env.py 能读取到当前进程的数据库配置
    os.environ["DATABASE__URL"] = settings.database.url
    command.upgrade(alembic_config, "head")


async def upgrade_schema_to_head() -> None:
    """在线程池中执行 Alembic，避免阻塞事件循环。"""
    await asyncio.to_thread(_run_alembic_upgrade_to_head)
