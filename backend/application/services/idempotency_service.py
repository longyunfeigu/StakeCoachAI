"""Application idempotency orchestration.

Implements generic Idempotency-Key behavior on top of the IdempotencyStore port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from application.ports.idempotency import IdempotencyStore
from domain.common.exceptions import DomainValidationException


@dataclass(frozen=True, slots=True)
class IdempotencyDecision:
    execute: bool
    payload: Optional[dict[str, Any]] = None


class IdempotencyService:
    def __init__(
        self,
        *,
        store: IdempotencyStore,
        lock_ttl_seconds: int = 30,
        result_ttl_seconds: int = 24 * 60 * 60,
    ) -> None:
        self._store = store
        self._lock_ttl_seconds = int(lock_ttl_seconds)
        self._result_ttl_seconds = int(result_ttl_seconds)

    async def decide(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
    ) -> IdempotencyDecision:
        record = await self._store.get(scope=scope, key=key)
        if record is not None:
            if record.request_hash != request_hash:
                raise DomainValidationException(
                    "Idempotency-Key reused with different request",
                    field="Idempotency-Key",
                    details={"scope": scope},
                    message_key="idempotency.key.reused",
                )
            return IdempotencyDecision(execute=False, payload=record.payload)

        acquired = await self._store.try_start(
            scope=scope,
            key=key,
            request_hash=request_hash,
            ttl_seconds=self._lock_ttl_seconds,
        )
        if not acquired:
            # Another in-flight request is executing; check if result appeared.
            record = await self._store.get(scope=scope, key=key)
            if record is not None and record.request_hash == request_hash:
                return IdempotencyDecision(execute=False, payload=record.payload)
            raise DomainValidationException(
                "Request with this Idempotency-Key is in progress",
                field="Idempotency-Key",
                details={"scope": scope},
                message_key="idempotency.in_progress",
            )

        return IdempotencyDecision(execute=True)

    async def persist_result(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        payload: dict[str, Any],
    ) -> None:
        await self._store.set_result(
            scope=scope,
            key=key,
            request_hash=request_hash,
            payload=payload,
            ttl_seconds=self._result_ttl_seconds,
        )
        await self._store.release(scope=scope, key=key)

    async def release(
        self,
        *,
        scope: str,
        key: str,
    ) -> None:
        await self._store.release(scope=scope, key=key)
