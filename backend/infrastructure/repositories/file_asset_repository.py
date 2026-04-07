"""SQLAlchemy-backed repository for file assets."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.file_asset import FileAsset, FileAssetRepository
from domain.common.exceptions import FileAssetNotFoundException
from infrastructure.models.file_asset import FileAssetModel
import hashlib


class SQLAlchemyFileAssetRepository(FileAssetRepository):
    """Persist file asset aggregates using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: FileAssetModel) -> FileAsset:
        return FileAsset(
            id=model.id,
            owner_id=model.owner_id,
            storage_type=model.storage_type,
            bucket=model.bucket,
            region=model.region,
            key=model.key,
            size=model.size,
            etag=model.etag,
            content_type=model.content_type,
            original_filename=model.original_filename,
            kind=model.kind,
            is_public=model.is_public,
            metadata=dict(model.extra_metadata or {}),
            url=model.url,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )

    @staticmethod
    def _calc_unique_hash(storage_type: str, bucket: Optional[str], key: str) -> str:
        raw = f"{storage_type}|{bucket or ''}|{key}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _apply_filters(
        self,
        query,
        *,
        owner_id: Optional[int],
        kind: Optional[str],
        status: Optional[str],
    ):
        if owner_id is not None:
            query = query.where(FileAssetModel.owner_id == owner_id)
        if kind:
            query = query.where(FileAssetModel.kind == kind)
        if status:
            query = query.where(FileAssetModel.status == status)
        return query

    async def create(self, asset: FileAsset) -> FileAsset:
        model = FileAssetModel(
            owner_id=asset.owner_id,
            storage_type=asset.storage_type,
            bucket=asset.bucket,
            region=asset.region,
            key=asset.key,
            unique_key_hash=self._calc_unique_hash(asset.storage_type, asset.bucket, asset.key),
            size=asset.size,
            etag=asset.etag,
            content_type=asset.content_type,
            original_filename=asset.original_filename,
            kind=asset.kind,
            is_public=asset.is_public,
            extra_metadata=asset.metadata or {},
            url=asset.url,
            status=asset.status,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            deleted_at=asset.deleted_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, asset: FileAsset) -> FileAsset:
        result = await self.session.execute(
            select(FileAssetModel).where(FileAssetModel.id == asset.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise FileAssetNotFoundException(asset.id)

        model.owner_id = asset.owner_id
        model.storage_type = asset.storage_type
        model.bucket = asset.bucket
        model.region = asset.region
        model.key = asset.key
        model.unique_key_hash = self._calc_unique_hash(asset.storage_type, asset.bucket, asset.key)
        model.size = asset.size
        model.etag = asset.etag
        model.content_type = asset.content_type
        model.original_filename = asset.original_filename
        model.kind = asset.kind
        model.is_public = asset.is_public
        model.extra_metadata = asset.metadata or {}
        model.url = asset.url
        model.status = asset.status
        model.created_at = asset.created_at
        model.updated_at = asset.updated_at
        model.deleted_at = asset.deleted_at

        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def delete(self, asset_id: int) -> None:
        result = await self.session.execute(
            select(FileAssetModel).where(FileAssetModel.id == asset_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise FileAssetNotFoundException(asset_id)
        await self.session.delete(model)
        await self.session.flush()

    async def delete_by_key(self, key: str) -> None:
        result = await self.session.execute(select(FileAssetModel).where(FileAssetModel.key == key))
        model = result.scalar_one_or_none()
        if model is None:
            raise FileAssetNotFoundException(key=key)
        await self.session.delete(model)
        await self.session.flush()

    async def get_by_id(self, asset_id: int) -> Optional[FileAsset]:
        result = await self.session.execute(
            select(FileAssetModel).where(FileAssetModel.id == asset_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_key(self, key: str) -> Optional[FileAsset]:
        result = await self.session.execute(select(FileAssetModel).where(FileAssetModel.key == key))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(
        self,
        *,
        owner_id: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[FileAsset]:
        query = select(FileAssetModel)
        query = self._apply_filters(
            query,
            owner_id=owner_id,
            kind=kind,
            status=status,
        )
        query = query.order_by(
            FileAssetModel.created_at.desc(),
            FileAssetModel.id.desc(),
        )
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def count(
        self,
        *,
        owner_id: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        query = select(func.count()).select_from(FileAssetModel)
        query = self._apply_filters(
            query,
            owner_id=owner_id,
            kind=kind,
            status=status,
        )
        result = await self.session.execute(query)
        return int(result.scalar() or 0)
