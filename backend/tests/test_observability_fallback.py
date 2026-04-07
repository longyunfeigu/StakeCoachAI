from __future__ import annotations

from fastapi import FastAPI

from core.observability import health, metrics, tracing


def test_metrics_noop_response() -> None:
    data, content_type = metrics.get_metrics_response()
    assert isinstance(data, (bytes, bytearray))
    assert isinstance(content_type, str)
    metrics.collect_db_pool_metrics(None)
    metrics.collect_redis_pool_metrics(None)


def test_tracing_noop_does_not_raise() -> None:
    ok = tracing.setup_tracing(
        service_name="test-service",
        exporter="console",
        otlp_endpoint=None,
        sample_rate=1.0,
    )
    assert ok in (True, False)
    tracing.instrument_app(FastAPI())
    assert tracing.get_current_trace_id() is None
    tracing.shutdown_tracing()


def test_health_report_readiness() -> None:
    ok_report = health.HealthReport(
        status=health.DependencyStatus.OK,
        checks=[
            health.DependencyHealth(
                name="redis",
                status=health.DependencyStatus.UNCONFIGURED,
                latency_ms=0.0,
                detail="not configured",
            )
        ],
    )
    assert ok_report.is_ready is True

    bad_report = health.HealthReport(
        status=health.DependencyStatus.FAILED,
        checks=[
            health.DependencyHealth(
                name="database",
                status=health.DependencyStatus.FAILED,
                latency_ms=5.0,
                detail="failed",
            )
        ],
    )
    assert bad_report.is_ready is False
