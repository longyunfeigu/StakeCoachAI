"""Unit of Work 抽象定义"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


from domain.file_asset.repository import FileAssetRepository
from domain.conversation.repository import (
    ConversationRepository,
    MessageRepository,
    RunRepository,
    AgentConfigRepository,
)
from domain.stakeholder.repository import ScenarioRepository
from domain.defense_prep.repository import DefenseSessionRepository


class AbstractUnitOfWork(ABC):
    """应用层事务边界控制抽象"""

    file_asset_repository: FileAssetRepository
    conversation_repository: ConversationRepository
    message_repository: MessageRepository
    run_repository: RunRepository
    agent_config_repository: AgentConfigRepository

    def __init__(self, *, readonly: bool = False) -> None:
        self._committed = False
        self._readonly = readonly
        self._repositories: dict[str, Any] = {}
        self.user_repository = None  # type: ignore[assignment]
        self.file_asset_repository = None  # type: ignore[assignment]
        self.conversation_repository = None  # type: ignore[assignment]
        self.message_repository = None  # type: ignore[assignment]
        self.run_repository = None  # type: ignore[assignment]
        self.agent_config_repository = None  # type: ignore[assignment]
        self.scenario_repository: ScenarioRepository = None  # type: ignore[assignment]
        self.defense_session_repository: DefenseSessionRepository = None  # type: ignore[assignment]

    async def __aenter__(self) -> "AbstractUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc:
            await self.rollback()
        else:
            # 只在非只读且未显式提交时自动提交
            if not self._readonly and not self._committed:
                await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """提交事务"""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """回滚事务"""
        ...

    def register_repository(self, name: str, repo: Any) -> None:
        self._repositories[name] = repo

    def get_repository(self, name: str) -> Any:
        return self._repositories.get(name)
