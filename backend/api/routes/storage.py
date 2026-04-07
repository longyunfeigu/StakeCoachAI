"""存储/文件上传相关路由。"""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
    Request,
)

from api.dependencies import (
    get_file_asset_service,
    get_idempotency_service,
)
from application.dto import (
    PresignUploadRequestDTO,
    CompleteUploadRequestDTO,
    StorageUploadResponseDTO,
    PresignUploadResponseDTO,
    PresignUploadDetailDTO,
    FileAssetSummaryDTO,
)
from application.services.file_asset_service import FileAssetApplicationService
from application.services.idempotency_service import IdempotencyService
from core.response import (
    Response as ApiResponse,
    success_response,
)
from core.i18n import t
from core.logging_config import get_logger
from domain.common.exceptions import BusinessException
from api.utils.idempotency import (
    build_request_hash,
    pick_subject_from_request_headers,
    validate_idempotency_key,
)

logger = get_logger(__name__)


router = APIRouter(
    prefix="/storage",
    tags=["文件存储"],
)


@router.post(
    "/presign-upload",
    summary="生成直传预签名",
    response_model=ApiResponse[PresignUploadResponseDTO],
)
async def presign_upload(
    request: Request,
    payload: PresignUploadRequestDTO,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
    idempotency: IdempotencyService = Depends(get_idempotency_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    scope = f"{request.method}:{request.url.path}"
    subject = pick_subject_from_request_headers(dict(request.headers))
    request_hash = build_request_hash(
        scope=scope,
        subject=subject,
        body=payload.model_dump(by_alias=True, exclude_none=True),
    )
    idem_key = None
    if idempotency_key:
        try:
            idem_key = validate_idempotency_key(idempotency_key)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def _build_response_from_pending(
        file_payload: dict,
    ) -> ApiResponse[PresignUploadResponseDTO]:
        file_summary = FileAssetSummaryDTO.model_validate(file_payload)
        presigned = await service.generate_upload_presign(
            key=file_summary.key,
            method=payload.method,
            content_type=file_summary.content_type,
            expires_in=payload.expires_in,
        )
        response_data = PresignUploadResponseDTO(
            file=file_summary,
            upload=PresignUploadDetailDTO(
                url=presigned.url,
                method=presigned.method,
                headers=presigned.headers,
                fields=presigned.fields,
                expires_in=presigned.expires_in,
            ),
        )
        return success_response(data=response_data, message=t("storage.presign.success"))

    if idem_key:
        try:
            decision = await idempotency.decide(
                scope=scope, key=idem_key, request_hash=request_hash
            )
        except BusinessException:
            raise
        except Exception as exc:
            logger.warning(
                "idempotency_decide_failed",
                scope=scope,
                key=idem_key,
                error=str(exc),
            )
            decision = None
            idem_key = None
        if decision is not None and not decision.execute and decision.payload:
            return await _build_response_from_pending(decision.payload)

    try:
        file_summary, presigned = await service.presign_upload(
            user_id=None,  # No user tracking
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            kind=payload.kind,
            method=payload.method or "PUT",
            expires_in=payload.expires_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response_data = PresignUploadResponseDTO(
        file=file_summary,
        upload=PresignUploadDetailDTO(
            url=presigned.url,
            method=presigned.method,
            headers=presigned.headers,
            fields=presigned.fields,
            expires_in=presigned.expires_in,
        ),
    )
    if idem_key:
        try:
            await idempotency.persist_result(
                scope=scope,
                key=idem_key,
                request_hash=request_hash,
                payload=file_summary.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.warning(
                "idempotency_persist_failed",
                scope=scope,
                key=idem_key,
                error=str(exc),
            )
    return success_response(data=response_data, message=t("storage.presign.success"))


@router.post(
    "/complete",
    summary="直传完成确认",
    response_model=ApiResponse[dict],
)
async def confirm_presigned_upload(
    payload: CompleteUploadRequestDTO,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    try:
        payload.ensure_identifier()
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=t("file.identifier.missing")) from exc

    if payload.id is not None:
        asset = await service.get_asset_raw(payload.id)
    elif payload.key:
        asset = await service.get_asset_by_key_raw(payload.key)
    else:  # pragma: no cover - already guarded
        raise HTTPException(status_code=400, detail=t("file.identifier.missing"))

    # No permission check

    await service.confirm_direct_upload(asset_id=asset.id)

    return success_response(data={"ok": True}, message=t("file.activate.success"))


@router.post(
    "/upload",
    summary="中转上传单个文件",
    response_model=ApiResponse[StorageUploadResponseDTO],
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    kind: str = Query("uploads", description="业务分类（如 avatar、document 等）"),
    service: FileAssetApplicationService = Depends(get_file_asset_service),
):
    """由应用服务器中转上传文件到对象存储（编排已下沉到 Application Service）。"""

    async def _iter_chunks(
        upload: UploadFile, *, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            yield chunk

    resp = await service.relay_upload_stream(
        user_id=None,  # No user tracking
        file_stream=_iter_chunks(file),
        filename=file.filename or "upload.bin",
        kind=kind,
        content_type=file.content_type,
    )
    return success_response(data=resp, message=t("file.upload.success"))
