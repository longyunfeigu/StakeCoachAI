# input: DefenseSession 领域实体
# output: DefenseSessionRepository ABC 仓储接口
# owner: wanhua.gu
# pos: 领域层 - 答辩准备会话仓储接口；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Repository abstraction for defense prep sessions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entity import DefenseSession


class DefenseSessionRepository(ABC):
    @abstractmethod
    async def create(self, session: DefenseSession) -> DefenseSession: ...

    @abstractmethod
    async def get_by_id(self, session_id: int) -> Optional[DefenseSession]: ...

    @abstractmethod
    async def update(self, session: DefenseSession) -> DefenseSession: ...

    @abstractmethod
    async def list_all(self, *, skip: int = 0, limit: int = 20) -> list[DefenseSession]: ...
