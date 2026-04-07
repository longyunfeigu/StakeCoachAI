"""Repository abstraction for file assets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entity import FileAsset


class FileAssetRepository(ABC):
    """Contract for persisting and querying file assets."""

    @abstractmethod
    async def create(self, asset: FileAsset) -> FileAsset: ...

    @abstractmethod
    async def update(self, asset: FileAsset) -> FileAsset: ...

    @abstractmethod
    async def delete(self, asset_id: int) -> None: ...

    @abstractmethod
    async def delete_by_key(self, key: str) -> None: ...

    @abstractmethod
    async def get_by_id(self, asset_id: int) -> Optional[FileAsset]: ...

    @abstractmethod
    async def get_by_key(self, key: str) -> Optional[FileAsset]: ...

    @abstractmethod
    async def list(
        self,
        *,
        owner_id: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[FileAsset]: ...

    @abstractmethod
    async def count(
        self,
        *,
        owner_id: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int: ...
