"""Prometheus metrics helpers (optional)."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from core.logging_config import get_logger

logger = get_logger(__name__)

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

    HAS_PROMETHEUS = True
except Exception:  # pragma: no cover - optional dependency
    Counter = Gauge = Histogram = None
    generate_latest = None
    CONTENT_TYPE_LATEST = None
    HAS_PROMETHEUS = False


class NoopMetric:
    def labels(self, *args: Any, **kwargs: Any) -> "NoopMetric":
        return self

    def observe(self, value: Any) -> None:
        _ = value

    def inc(self, value: Any = 1) -> None:
        _ = value

    def dec(self, value: Any = 1) -> None:
        _ = value

    def set(self, value: Any) -> None:
        _ = value


if HAS_PROMETHEUS:
    HTTP_REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path", "status"],
    )
    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    HTTP_REQUESTS_IN_FLIGHT = Gauge(
        "http_requests_in_flight",
        "In-flight HTTP requests",
        ["method", "path"],
    )

    DB_POOL_SIZE = Gauge("db_pool_size", "DB pool size", ["pool"])
    DB_POOL_CHECKED_IN = Gauge("db_pool_checked_in", "DB pool checked in", ["pool"])
    DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "DB pool checked out", ["pool"])
    DB_POOL_OVERFLOW = Gauge("db_pool_overflow", "DB pool overflow", ["pool"])

    REDIS_POOL_ACTIVE = Gauge("redis_pool_active", "Redis pool active", ["pool"])
    REDIS_POOL_AVAILABLE = Gauge("redis_pool_available", "Redis pool available", ["pool"])

    BUSINESS_OPERATIONS_TOTAL = Counter(
        "business_operations_total",
        "Business operation totals",
        ["operation", "status"],
    )
else:  # pragma: no cover - optional dependency
    HTTP_REQUEST_DURATION = NoopMetric()
    HTTP_REQUESTS_TOTAL = NoopMetric()
    HTTP_REQUESTS_IN_FLIGHT = NoopMetric()

    DB_POOL_SIZE = NoopMetric()
    DB_POOL_CHECKED_IN = NoopMetric()
    DB_POOL_CHECKED_OUT = NoopMetric()
    DB_POOL_OVERFLOW = NoopMetric()

    REDIS_POOL_ACTIVE = NoopMetric()
    REDIS_POOL_AVAILABLE = NoopMetric()

    BUSINESS_OPERATIONS_TOTAL = NoopMetric()


def _get_engine_pool(engine: Any) -> Any:
    if engine is None:
        return None
    pool = getattr(engine, "pool", None)
    if pool is None and hasattr(engine, "sync_engine"):
        pool = getattr(engine.sync_engine, "pool", None)
    return pool


def collect_db_pool_metrics(engine: Any, *, pool_name: str = "default") -> None:
    if not HAS_PROMETHEUS:
        return
    try:
        pool = _get_engine_pool(engine)
        if pool is None:
            return
        size = getattr(pool, "size", None)
        checkedin = getattr(pool, "checkedin", None)
        checkedout = getattr(pool, "checkedout", None)
        overflow = getattr(pool, "overflow", None)
        if callable(size):
            DB_POOL_SIZE.labels(pool_name).set(size())
        if callable(checkedin):
            DB_POOL_CHECKED_IN.labels(pool_name).set(checkedin())
        if callable(checkedout):
            DB_POOL_CHECKED_OUT.labels(pool_name).set(checkedout())
        if callable(overflow):
            DB_POOL_OVERFLOW.labels(pool_name).set(overflow())
    except Exception as exc:
        logger.debug("db_pool_metrics_failed", error=str(exc))


def _get_redis_pool(redis_client: Any) -> Optional[Any]:
    if redis_client is None:
        return None
    raw = getattr(redis_client, "client", None) or getattr(redis_client, "_client", None)
    raw = raw or redis_client
    return getattr(raw, "connection_pool", None)


def collect_redis_pool_metrics(redis_client: Any, *, pool_name: str = "default") -> None:
    if not HAS_PROMETHEUS:
        return
    try:
        pool = _get_redis_pool(redis_client)
        if pool is None:
            return
        in_use = getattr(pool, "_in_use_connections", None)
        available = getattr(pool, "_available_connections", None)
        active_count = len(in_use) if isinstance(in_use, (set, list)) else None
        available_count = len(available) if isinstance(available, list) else None
        max_connections = getattr(pool, "max_connections", None)
        if active_count is None and hasattr(pool, "in_use_connections"):
            active_count = len(getattr(pool, "in_use_connections"))
        if max_connections is not None and active_count is not None:
            available_count = max(max_connections - active_count, 0)
        if active_count is not None:
            REDIS_POOL_ACTIVE.labels(pool_name).set(active_count)
        if available_count is not None:
            REDIS_POOL_AVAILABLE.labels(pool_name).set(available_count)
    except Exception as exc:
        logger.debug("redis_pool_metrics_failed", error=str(exc))


def get_metrics_response() -> Tuple[bytes, str]:
    if not HAS_PROMETHEUS or generate_latest is None or CONTENT_TYPE_LATEST is None:
        return b"", CONTENT_TYPE
    try:
        return generate_latest(), CONTENT_TYPE_LATEST
    except Exception as exc:
        logger.debug("metrics_generate_failed", error=str(exc))
        return b"", CONTENT_TYPE
