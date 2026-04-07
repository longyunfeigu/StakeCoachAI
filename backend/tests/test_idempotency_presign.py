from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from api.dependencies import get_file_asset_service, get_idempotency_service
from api.routes.storage import router as storage_router
from application.dto import FileAssetSummaryDTO
from application.ports.storage import PresignedURL
from application.services.idempotency_service import IdempotencyService
from application.ports.idempotency import IdempotencyRecord, IdempotencyStore
from core.exceptions import register_exception_handlers


class InMemoryIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self._locks: set[tuple[str, str]] = set()
        self._results: dict[tuple[str, str], IdempotencyRecord] = {}

    async def get(self, *, scope: str, key: str):
        return self._results.get((scope, key))

    async def try_start(self, *, scope: str, key: str, request_hash: str, ttl_seconds: int) -> bool:
        _ = ttl_seconds
        lk = (scope, key)
        if lk in self._locks:
            return False
        self._locks.add(lk)
        return True

    async def set_result(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        payload: dict,
        ttl_seconds: int,
    ) -> None:
        _ = ttl_seconds
        self._results[(scope, key)] = IdempotencyRecord(
            scope=scope,
            key=key,
            request_hash=request_hash,
            payload=payload,
        )

    async def release(self, *, scope: str, key: str) -> None:
        self._locks.discard((scope, key))


class FakeFileAssetService:
    def __init__(self) -> None:
        self.presign_calls = 0
        self.generate_calls = 0

    async def presign_upload(
        self,
        *,
        user_id,
        filename: str,
        mime_type,
        size_bytes: int,
        kind: str,
        method: str = "PUT",
        expires_in: int = 600,
    ):
        _ = (user_id, mime_type, kind, expires_in, size_bytes)
        self.presign_calls += 1
        file_summary = FileAssetSummaryDTO(
            id=self.presign_calls,
            key=f"test/{filename}",
            status="pending",
            original_filename=filename,
            content_type="text/plain",
            etag=None,
            size=0,
            url=None,
        )
        presigned = PresignedURL(
            url=f"https://example.test/upload/{self.presign_calls}", method=method, expires_in=600
        )
        return file_summary, presigned

    async def generate_upload_presign(
        self,
        *,
        key: str,
        method: str,
        content_type,
        expires_in: int,
    ) -> PresignedURL:
        _ = (content_type, expires_in)
        self.generate_calls += 1
        return PresignedURL(
            url=f"https://example.test/upload/replay/{self.generate_calls}",
            method=method,
            expires_in=600,
        )


def make_test_app(fake_service: FakeFileAssetService) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(storage_router, prefix="/api/v1")

    store = InMemoryIdempotencyStore()
    idem = IdempotencyService(store=store, lock_ttl_seconds=5, result_ttl_seconds=60)

    app.dependency_overrides[get_file_asset_service] = lambda: fake_service
    app.dependency_overrides[get_idempotency_service] = lambda: idem
    return app


@pytest.mark.asyncio
async def test_presign_upload_idempotent_replay() -> None:
    fake = FakeFileAssetService()
    app = make_test_app(fake)

    payload = {
        "filename": "a.txt",
        "mime_type": None,
        "size_bytes": 1,
        "kind": "uploads",
        "method": "PUT",
        "expires_in": 600,
    }
    headers = {"Idempotency-Key": "aaaaaaaa"}

    async with AsyncClient(app=app, base_url="http://test") as client:
        r1 = await client.post("/api/v1/storage/presign-upload", json=payload, headers=headers)
        r2 = await client.post("/api/v1/storage/presign-upload", json=payload, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["data"]["file"]["id"] == r2.json()["data"]["file"]["id"]
    assert fake.presign_calls == 1
    assert fake.generate_calls == 1


@pytest.mark.asyncio
async def test_presign_upload_idempotency_key_reused_with_different_payload() -> None:
    fake = FakeFileAssetService()
    app = make_test_app(fake)

    payload1 = {
        "filename": "a.txt",
        "mime_type": None,
        "size_bytes": 1,
        "kind": "uploads",
        "method": "PUT",
        "expires_in": 600,
    }
    payload2 = {
        "filename": "b.txt",
        "mime_type": None,
        "size_bytes": 1,
        "kind": "uploads",
        "method": "PUT",
        "expires_in": 600,
    }
    headers = {"Idempotency-Key": "bbbbbbbb"}

    async with AsyncClient(app=app, base_url="http://test") as client:
        r1 = await client.post("/api/v1/storage/presign-upload", json=payload1, headers=headers)
        r2 = await client.post("/api/v1/storage/presign-upload", json=payload2, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 422
    assert r2.json()["code"] == 10003
