"""OpenTelemetry tracing helpers (optional)."""

from __future__ import annotations

from typing import Any, Optional

from core.logging_config import get_logger

logger = get_logger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    HAS_OTEL = True
except Exception:  # pragma: no cover - optional dependency
    trace = None
    Resource = TracerProvider = BatchSpanProcessor = ConsoleSpanExporter = TraceIdRatioBased = None
    HAS_OTEL = False


_tracer_provider: Optional[Any] = None
_span_processor: Optional[Any] = None
_instrumented: bool = False


def setup_tracing(
    *,
    service_name: str,
    exporter: str | None = None,
    otlp_endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> bool:
    if not HAS_OTEL:
        logger.warning("tracing_disabled", reason="opentelemetry not installed")
        return False

    global _tracer_provider, _span_processor
    if _tracer_provider is not None:
        return True

    try:
        rate = min(max(float(sample_rate), 0.0), 1.0)
    except Exception:
        rate = 1.0

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=TraceIdRatioBased(rate))

    span_exporter = None
    if exporter == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            span_exporter = (
                OTLPSpanExporter(endpoint=otlp_endpoint) if otlp_endpoint else OTLPSpanExporter()
            )
        except Exception as exc:
            logger.warning("tracing_exporter_unavailable", exporter="otlp", error=str(exc))
    elif exporter == "console":
        span_exporter = ConsoleSpanExporter()

    if span_exporter is None:
        span_exporter = ConsoleSpanExporter()

    processor = BatchSpanProcessor(span_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    _tracer_provider = provider
    _span_processor = processor
    return True


def instrument_app(app: Any) -> bool:
    if not HAS_OTEL:
        return False
    global _instrumented
    if _instrumented:
        return True

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("fastapi_instrumentation_failed", error=str(exc))

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.warning("httpx_instrumentation_failed", error=str(exc))

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception as exc:
        logger.warning("redis_instrumentation_failed", error=str(exc))

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from infrastructure.database import engine

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except Exception as exc:
        logger.warning("sqlalchemy_instrumentation_failed", error=str(exc))

    _instrumented = True
    return True


def get_current_trace_id() -> Optional[str]:
    if not HAS_OTEL:
        return None
    try:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if not ctx or not ctx.is_valid:
            return None
        return format(ctx.trace_id, "032x")
    except Exception:
        return None


def get_current_span_id() -> Optional[str]:
    if not HAS_OTEL:
        return None
    try:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if not ctx or not ctx.is_valid:
            return None
        return format(ctx.span_id, "016x")
    except Exception:
        return None


def set_request_span_attributes(**attrs: Any) -> None:
    if not HAS_OTEL:
        return
    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            for key, value in attrs.items():
                if value is not None:
                    span.set_attribute(key, value)
    except Exception:
        return


def shutdown_tracing() -> None:
    if not HAS_OTEL:
        return
    global _tracer_provider, _span_processor
    try:
        if _tracer_provider is not None:
            _tracer_provider.shutdown()
    except Exception as exc:
        logger.warning("tracing_shutdown_failed", error=str(exc))
    finally:
        _tracer_provider = None
        _span_processor = None
