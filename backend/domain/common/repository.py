"""Generic repository interfaces for domain aggregates."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

EntityT = TypeVar("EntityT")
IdT = TypeVar("IdT")


class BaseRepository(ABC, Generic[EntityT, IdT]):
    @abstractmethod
    async def create(self, entity: EntityT) -> EntityT: ...

    @abstractmethod
    async def update(self, entity: EntityT) -> EntityT: ...

    @abstractmethod
    async def delete(self, entity_id: IdT) -> None: ...

    @abstractmethod
    async def get_by_id(self, entity_id: IdT) -> Optional[EntityT]: ...

    @abstractmethod
    async def list(self, *, skip: int = 0, limit: int = 20, **filters) -> list[EntityT]: ...

    @abstractmethod
    async def count(self, **filters) -> int: ...
