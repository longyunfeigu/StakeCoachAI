"""SQLAlchemy base repository implementation."""

from __future__ import annotations

from typing import Any, Generic, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.common.exceptions import BusinessException
from domain.common.repository import BaseRepository

EntityT = TypeVar("EntityT")
ModelT = TypeVar("ModelT")
IdT = TypeVar("IdT")


class SQLAlchemyBaseRepository(BaseRepository[EntityT, IdT], Generic[EntityT, ModelT, IdT]):
    model_class: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_entity(self, model: ModelT) -> EntityT:
        raise NotImplementedError

    def _to_model(self, entity: EntityT) -> ModelT:
        raise NotImplementedError

    def _update_model(self, model: ModelT, entity: EntityT) -> None:
        raise NotImplementedError

    def _not_found_exception(self, identifier: IdT) -> BusinessException:
        raise NotImplementedError

    def _apply_filters(self, query: Any, **kwargs: Any) -> Any:
        return query

    def _default_order(self, query: Any) -> Any:
        return query

    def _raise_not_found(self, identifier: IdT) -> None:
        exc = self._not_found_exception(identifier)
        if not isinstance(exc, BusinessException):
            raise TypeError("_not_found_exception must return BusinessException")
        raise exc

    async def create(self, entity: EntityT) -> EntityT:
        model = self._to_model(entity)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: EntityT) -> EntityT:
        identifier = getattr(entity, "id", None)
        if identifier is None:
            self._raise_not_found(identifier)
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == identifier)
        )
        model = result.scalar_one_or_none()
        if model is None:
            self._raise_not_found(identifier)
        self._update_model(model, entity)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def delete(self, entity_id: IdT) -> None:
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == entity_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            self._raise_not_found(entity_id)
        await self.session.delete(model)
        await self.session.flush()

    async def get_by_id(self, entity_id: IdT) -> Optional[EntityT]:
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == entity_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(self, *, skip: int = 0, limit: int = 20, **filters: Any) -> list[EntityT]:
        query = select(self.model_class)
        query = self._apply_filters(query, **filters)
        query = self._default_order(query)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def count(self, **filters: Any) -> int:
        query = select(func.count()).select_from(self.model_class)
        query = self._apply_filters(query, **filters)
        result = await self.session.execute(query)
        return int(result.scalar() or 0)
