"""Generic application service scaffolding."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar, cast, runtime_checkable

from domain.common.exceptions import BusinessException
from shared.codes import BusinessCode

EntityT = TypeVar("EntityT")
DTOType = TypeVar("DTOType")
SummaryDTOType = TypeVar("SummaryDTOType")
IdT = TypeVar("IdT")


class RepositoryProtocol(Protocol[EntityT, IdT]):
    async def get_by_id(self, entity_id: IdT) -> Optional[EntityT]: ...

    async def list(self, *, skip: int = 0, limit: int = 20, **filters: Any) -> list[EntityT]: ...

    async def count(self, **filters: Any) -> int: ...

    async def update(self, entity: EntityT) -> EntityT: ...

    async def delete(self, entity_id: IdT) -> None: ...


@runtime_checkable
class NotFoundExceptionProvider(Protocol[IdT]):
    def _not_found_exception(self, identifier: IdT) -> BusinessException: ...


class UnitOfWorkProtocol(Protocol):
    async def __aenter__(self) -> "UnitOfWorkProtocol": ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    def get_repository(self, name: str) -> object | None: ...


class BaseApplicationService(Generic[EntityT, DTOType, SummaryDTOType, IdT]):
    _repository_attr: str

    def __init__(self, uow_factory: Callable[..., UnitOfWorkProtocol], **kwargs: Any) -> None:
        _ = kwargs
        self._uow_factory = uow_factory

    def _get_repository(self, uow: UnitOfWorkProtocol) -> RepositoryProtocol[EntityT, IdT]:
        repo = getattr(uow, self._repository_attr, None)
        if repo is None:
            repo = uow.get_repository(self._repository_attr)
        if repo is None:
            raise RuntimeError(f"Repository not found: {self._repository_attr}")
        return cast(RepositoryProtocol[EntityT, IdT], repo)

    def _to_dto(self, entity: EntityT) -> DTOType:
        raise NotImplementedError

    def _to_summary(self, entity: EntityT) -> SummaryDTOType:
        raise NotImplementedError

    def _raise_not_found(self, repo: RepositoryProtocol[EntityT, IdT], entity_id: IdT) -> None:
        if isinstance(repo, NotFoundExceptionProvider):
            exc = repo._not_found_exception(entity_id)
            if isinstance(exc, BusinessException):
                raise exc
        raise BusinessException(
            code=BusinessCode.NOT_FOUND,
            message="Resource not found",
            error_type="NotFound",
            details={"id": entity_id},
            message_key="resource.not_found",
        )

    async def get(self, entity_id: IdT) -> DTOType:
        async with self._uow_factory() as uow:
            repo = self._get_repository(uow)
            entity = await repo.get_by_id(entity_id)
            if entity is None:
                self._raise_not_found(repo, entity_id)
            return self._to_dto(entity)

    async def list(
        self, *, skip: int = 0, limit: int = 20, **filters: Any
    ) -> tuple[list[SummaryDTOType], int]:
        async with self._uow_factory(readonly=True) as uow:
            repo = self._get_repository(uow)
            items = await repo.list(skip=skip, limit=limit, **filters)
            total = await repo.count(**filters)
            return [self._to_summary(item) for item in items], total

    async def soft_delete(self, entity_id: IdT) -> DTOType:
        async with self._uow_factory() as uow:
            repo = self._get_repository(uow)
            entity = await repo.get_by_id(entity_id)
            if entity is None:
                self._raise_not_found(repo, entity_id)
            if hasattr(entity, "mark_deleted") and callable(getattr(entity, "mark_deleted")):
                entity.mark_deleted()
            else:
                now = datetime.now(timezone.utc)
                setattr(entity, "deleted_at", now)
                if hasattr(entity, "updated_at"):
                    setattr(entity, "updated_at", now)
            updated = await repo.update(entity)
            return self._to_dto(updated)

    async def purge(self, entity_id: IdT) -> None:
        async with self._uow_factory() as uow:
            repo = self._get_repository(uow)
            await repo.delete(entity_id)
