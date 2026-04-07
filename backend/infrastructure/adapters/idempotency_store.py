"""Redis-backed idempotency store adapter."""

from __future__ import annotations

from typing import Any, Optional

from application.ports.idempotency import IdempotencyRecord, IdempotencyStore
from core.logging_config import get_logger
from infrastructure.external.cache import get_redis_client


logger = get_logger(__name__)


class RedisIdempotencyStore(IdempotencyStore):
    def __init__(self, *, prefix: str = "idem") -> None:
        self._prefix = prefix.strip(":") or "idem"

    def _lock_key(self, scope: str, key: str) -> str:
        return f"{self._prefix}:lock:{scope}:{key}"

    def _result_key(self, scope: str, key: str) -> str:
        return f"{self._prefix}:res:{scope}:{key}"

    async def get(self, *, scope: str, key: str) -> Optional[IdempotencyRecord]:
        cache = await get_redis_client()
        raw = await cache.get(self._result_key(scope, key))
        if not isinstance(raw, dict):
            return None
        request_hash = str(raw.get("request_hash") or "")
        payload = raw.get("payload")
        if not request_hash or not isinstance(payload, dict):
            return None
        return IdempotencyRecord(scope=scope, key=key, request_hash=request_hash, payload=payload)

    async def try_start(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        ttl_seconds: int,
    ) -> bool:
        cache = await get_redis_client()
        ok = await cache.set(
            self._lock_key(scope, key),
            {"request_hash": request_hash},
            ttl=int(ttl_seconds),
            nx=True,
        )
        return bool(ok)

    async def set_result(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        cache = await get_redis_client()
        await cache.set(
            self._result_key(scope, key),
            {"request_hash": request_hash, "payload": payload},
            ttl=int(ttl_seconds),
        )

    async def release(self, *, scope: str, key: str) -> None:
        cache = await get_redis_client()
        try:
            await cache.delete(self._lock_key(scope, key))
        except Exception as exc:
            logger.warning("idempotency_lock_release_failed", scope=scope, key=key, error=str(exc))
