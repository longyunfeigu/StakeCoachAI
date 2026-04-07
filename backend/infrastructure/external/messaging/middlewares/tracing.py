from __future__ import annotations

from typing import Optional

from ..base import ConsumeMiddleware, Envelope, HandleResult, PublishMiddleware, PublishResult


try:
    from opentelemetry import trace
    from opentelemetry.trace import Tracer
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.textmap import CarrierT, Getter, Setter
except Exception:  # pragma: no cover - optional dependency
    trace = None
    Tracer = None  # type: ignore


class _HdrGetter:
    def get(self, carrier: CarrierT, key: str) -> list[str]:  # type: ignore[override]
        v = carrier.get(key)
        return (
            [v.decode("utf-8")]
            if isinstance(v, (bytes, bytearray))
            else ([] if v is None else [str(v)])
        )

    def keys(self, carrier: CarrierT) -> list[str]:  # type: ignore[override]
        return list(carrier.keys())


class _HdrSetter:
    def set(self, carrier: CarrierT, key: str, value: str) -> None:  # type: ignore[override]
        carrier[key] = value.encode("utf-8")


class TracingMiddleware(PublishMiddleware, ConsumeMiddleware):
    def __init__(self, service_name: str = "messaging") -> None:
        self.enabled = trace is not None
        self.tracer: Optional[Tracer] = trace.get_tracer(service_name) if self.enabled else None
        self._getter = _HdrGetter()
        self._setter = _HdrSetter()

    def before_publish(self, topic: str, env: Envelope) -> Envelope:  # type: ignore[override]
        if not self.enabled or not self.tracer:
            return env
        with self.tracer.start_as_current_span("messaging.produce"):
            from opentelemetry.propagate import inject

            inject(env.headers, setter=self._setter)
        return env

    def after_publish(self, topic: str, env: Envelope, result: PublishResult) -> None:  # type: ignore[override]
        return

    def before_handle(self, topic: str, partition: int, offset: int, env: Envelope) -> Envelope:  # type: ignore[override]
        if not self.enabled or not self.tracer:
            return env
        from opentelemetry.propagate import extract

        ctx = extract(env.headers, getter=self._getter)
        _ = ctx
        return env

    def after_handle(
        self,
        topic: str,
        partition: int,
        offset: int,
        env: Envelope,
        result: HandleResult,
        exc: Optional[BaseException] = None,
    ) -> None:  # type: ignore[override]
        return
