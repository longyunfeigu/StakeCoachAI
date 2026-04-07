from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from domain.common.entity import BaseEntity
from domain.common.exceptions import BusinessException
from infrastructure.repositories.base_repository import SQLAlchemyBaseRepository
from shared.codes import BusinessCode


class TestBase(DeclarativeBase):
    pass


class TagModel(TestBase):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@dataclass
class Tag(BaseEntity[int]):
    name: str = ""


class TagRepository(SQLAlchemyBaseRepository[Tag, TagModel, int]):
    model_class = TagModel

    def _to_entity(self, model: TagModel) -> Tag:
        return Tag(
            id=model.id,
            name=model.name,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )

    def _to_model(self, entity: Tag) -> TagModel:
        return TagModel(
            id=entity.id,
            name=entity.name,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )

    def _update_model(self, model: TagModel, entity: Tag) -> None:
        model.name = entity.name
        model.created_at = entity.created_at
        model.updated_at = entity.updated_at
        model.deleted_at = entity.deleted_at

    def _not_found_exception(self, identifier: int) -> BusinessException:
        return BusinessException(
            code=BusinessCode.NOT_FOUND,
            message="Tag not found",
            error_type="TagNotFound",
            details={"id": identifier},
            message_key="tag.not_found",
        )


@pytest.mark.asyncio
async def test_sqlalchemy_base_repository_crud() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)

    async with async_session() as session:
        repo = TagRepository(session)
        now = datetime.now(timezone.utc)
        created = await repo.create(Tag(name="alpha", created_at=now, updated_at=now))
        assert created.id is not None

        created.name = "beta"
        updated = await repo.update(created)
        assert updated.name == "beta"

        fetched = await repo.get_by_id(updated.id)
        assert fetched is not None
        assert fetched.name == "beta"

        await repo.create(Tag(name="gamma"))
        items = await repo.list(skip=0, limit=10)
        total = await repo.count()
        assert total == len(items)

        await repo.delete(updated.id)
        missing = await repo.get_by_id(updated.id)
        assert missing is None


@pytest.mark.asyncio
async def test_sqlalchemy_base_repository_not_found() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)

    async with async_session() as session:
        repo = TagRepository(session)
        with pytest.raises(BusinessException):
            await repo.delete(999)
