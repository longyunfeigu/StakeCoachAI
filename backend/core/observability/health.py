"""Health check utilities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any

from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


class DependencyStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    UNCONFIGURED = "unconfigured"


@dataclass
class DependencyHealth:
    name: str
    status: DependencyStatus
    latency_ms: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "detail": self.detail,
        }


@dataclass
class HealthReport:
    status: DependencyStatus
    checks: list[DependencyHealth]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": [check.to_dict() for check in self.checks],
        }

    @property
    def is_ready(self) -> bool:
        return all(check.status != DependencyStatus.FAILED for check in self.checks)


async def check_database(timeout: float = 5.0) -> DependencyHealth:
    start = perf_counter()
    try:
        from sqlalchemy import text
        from infrastructure.database import engine

        async def _ping() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_ping(), timeout=timeout)
        status = DependencyStatus.OK
        detail = "ok"
    except asyncio.TimeoutError:
        status = DependencyStatus.FAILED
        detail = "timeout"
    except Exception as exc:
        status = DependencyStatus.FAILED
        detail = exc.__class__.__name__
    latency = (perf_counter() - start) * 1000.0
    return DependencyHealth(name="database", status=status, latency_ms=latency, detail=detail)


async def check_redis(timeout: float = 3.0) -> DependencyHealth:
    start = perf_counter()
    if not settings.redis.url:
        return DependencyHealth(
            name="redis",
            status=DependencyStatus.UNCONFIGURED,
            latency_ms=0.0,
            detail="redis url not configured",
        )
    try:
        from infrastructure.external.cache import get_redis_client

        async def _ping() -> bool:
            client = await get_redis_client()
            return await client.health_check()

        ok = await asyncio.wait_for(_ping(), timeout=timeout)
        status = DependencyStatus.OK if ok else DependencyStatus.FAILED
        detail = "ok" if ok else "health_check_failed"
    except asyncio.TimeoutError:
        status = DependencyStatus.FAILED
        detail = "timeout"
    except Exception as exc:
        status = DependencyStatus.FAILED
        detail = exc.__class__.__name__
    latency = (perf_counter() - start) * 1000.0
    return DependencyHealth(name="redis", status=status, latency_ms=latency, detail=detail)


async def check_storage(timeout: float = 5.0) -> DependencyHealth:
    start = perf_counter()
    try:
        from infrastructure.external.storage import get_storage_client, get_storage_config

        config = get_storage_config()
        if not getattr(config, "type", None):
            return DependencyHealth(
                name="storage",
                status=DependencyStatus.UNCONFIGURED,
                latency_ms=0.0,
                detail="storage not configured",
            )

        client = get_storage_client()
        if client is None:
            return DependencyHealth(
                name="storage",
                status=DependencyStatus.FAILED,
                latency_ms=0.0,
                detail="storage client not initialized",
            )

        async def _ping() -> bool:
            return await client.health_check()

        ok = await asyncio.wait_for(_ping(), timeout=timeout)
        status = DependencyStatus.OK if ok else DependencyStatus.FAILED
        detail = "ok" if ok else "health_check_failed"
    except asyncio.TimeoutError:
        status = DependencyStatus.FAILED
        detail = "timeout"
    except Exception as exc:
        status = DependencyStatus.FAILED
        detail = exc.__class__.__name__
    latency = (perf_counter() - start) * 1000.0
    return DependencyHealth(name="storage", status=status, latency_ms=latency, detail=detail)


async def full_health_check(**timeouts: float) -> HealthReport:
    db_timeout = float(timeouts.get("db_timeout", settings.health.db_timeout_seconds))
    redis_timeout = float(timeouts.get("redis_timeout", settings.health.redis_timeout_seconds))
    storage_timeout = float(
        timeouts.get("storage_timeout", settings.health.storage_timeout_seconds)
    )

    results = await asyncio.gather(
        check_database(timeout=db_timeout),
        check_redis(timeout=redis_timeout),
        check_storage(timeout=storage_timeout),
        return_exceptions=True,
    )
    names = ["database", "redis", "storage"]
    checks: list[DependencyHealth] = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            checks.append(
                DependencyHealth(
                    name=name,
                    status=DependencyStatus.FAILED,
                    latency_ms=0.0,
                    detail=result.__class__.__name__,
                )
            )
        else:
            checks.append(result)

    overall_status = (
        DependencyStatus.FAILED
        if any(check.status == DependencyStatus.FAILED for check in checks)
        else DependencyStatus.OK
    )
    report = HealthReport(status=overall_status, checks=checks)
    if not report.is_ready:
        logger.warning("health_check_failed", checks=[c.to_dict() for c in checks])
    return report
