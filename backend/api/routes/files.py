"""文件管理相关路由。"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies import (
    get_file_asset_service,
)
from application.dto import (
    FileAssetDTO,
    FileAccessURLRequestDTO,
)
from application.services.file_asset_service import FileAssetApplicationService
from core.response import (
    Response as ApiResponse,
    PaginatedData,
    paginated_response,
    success_response,
)
from core.config import settings
from core.i18n import t

router = APIRouter(
    prefix="/files",
    tags=["文件管理"],
)


@router.get(
    "",
    summary="文件列表",
    response_model=ApiResponse[PaginatedData[FileAssetDTO]],
)
async def list_files(
    page: int = Query(1, ge=1),
    size: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    kind: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default="active"),
    signed: bool = Query(False, description="是否返回带签名的临时URL"),
    expires_in: int = Query(600, ge=60, le=3600, description="签名URL有效期(秒)"),
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    owner_id = None  # No user filtering
    skip = (page - 1) * size
    assets, total = await service.list_assets(
        owner_id=owner_id,
        kind=kind,
        status=None if status in {None, "all"} else status,
        skip=skip,
        limit=size,
    )
    # 动态覆盖URL为签名URL（仅响应中，不入库）
    if signed:
        semaphore = asyncio.Semaphore(10)

        async def _sign_one(dto: FileAssetDTO) -> None:
            async with semaphore:
                filename = dto.original_filename or f"file-{dto.id}"
                content_type = dto.content_type  # avoid guessing at app layer if possible
                access = await service.generate_access_url_by_info(
                    key=dto.key,
                    content_type=content_type,
                    filename=filename,
                    expires_in=expires_in,
                    disposition_mode="inline",
                )
                dto.url = str(access.get("url", ""))

        await asyncio.gather(*(_sign_one(dto) for dto in assets))
    return paginated_response(
        items=assets,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{asset_id}",
    summary="文件详情",
    response_model=ApiResponse[FileAssetDTO],
)
async def get_file_detail(
    asset_id: int,
    signed: bool = Query(False, description="是否返回带签名的临时URL"),
    expires_in: int = Query(600, ge=60, le=3600, description="签名URL有效期(秒)"),
    filename: Optional[str] = Query(None, description="下载/预览文件名，默认原始文件名"),
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    asset = await service.get_asset_raw(asset_id)
    # No permission check
    dto = FileAssetDTO.model_validate(asset)
    if signed:
        fname = filename or dto.original_filename or f"file-{dto.id}"
        access = await service.generate_access_url_by_info(
            key=dto.key,
            content_type=dto.content_type,
            filename=fname,
            expires_in=expires_in,
            disposition_mode="inline",
        )
        dto.url = str(access.get("url", ""))
    return success_response(dto, message=t("ok"))


# Controller no longer handles storage orchestration; use service methods instead.


@router.post(
    "/{asset_id}/preview-url",
    summary="生成预览链接",
    response_model=ApiResponse[dict],
)
async def generate_preview_url(
    asset_id: int,
    payload: FileAccessURLRequestDTO,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    asset = await service.get_asset_raw(asset_id)
    # No permission check
    data = await service.generate_access_url_for_asset(
        asset=asset,
        expires_in=payload.expires_in,
        filename=payload.filename,
        disposition_mode="inline",
    )
    return success_response(data, message=t("ok"))


@router.post(
    "/{asset_id}/download-url",
    summary="生成下载链接",
    response_model=ApiResponse[dict],
)
async def generate_download_url(
    asset_id: int,
    payload: FileAccessURLRequestDTO,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    asset = await service.get_asset_raw(asset_id)
    # No permission check
    data = await service.generate_access_url_for_asset(
        asset=asset,
        expires_in=payload.expires_in,
        filename=payload.filename,
        disposition_mode="attachment",
    )
    return success_response(data, message=t("ok"))


@router.delete(
    "/{asset_id}",
    summary="删除文件（软删除）",
    response_model=ApiResponse[dict],
)
async def delete_file(
    asset_id: int,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    asset = await service.get_asset_raw(asset_id)
    # No permission check

    updated = await service.soft_delete(asset_id)
    return success_response(
        {"deleted": True, "status": updated.status}, message=t("file.delete.soft.success")
    )
