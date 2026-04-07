from __future__ import annotations

import time
from typing import Optional
import contextvars

from ..base import ConsumeMiddleware, Envelope, HandleResult, PublishMiddleware, PublishResult


try:
    from prometheus_client import Counter, Histogram
except Exception:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore
    Histogram = None  # type: ignore


class MetricsMiddleware(PublishMiddleware, ConsumeMiddleware):
    def __init__(self, namespace: str = "messaging") -> None:
        if Counter and Histogram:
            self.pub_counter = Counter(
                f"{namespace}_publish_total", "Publish attempts", ["topic", "result"]
            )
            self.pub_latency = Histogram(
                f"{namespace}_publish_latency_ms",
                "Publish latency ms",
                buckets=(1, 5, 10, 50, 100, 500, 1000),
            )
            self.con_counter = Counter(
                f"{namespace}_consume_total", "Consume results", ["topic", "result"]
            )
            self.con_latency = Histogram(
                f"{namespace}_handle_latency_ms",
                "Handle latency ms",
                buckets=(1, 5, 10, 50, 100, 500, 1000),
            )
        else:
            self.pub_counter = None
            self.pub_latency = None
            self.con_counter = None
            self.con_latency = None
        # Use context-local storage to avoid cross-request interference
        self._pub_start: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar(
            "messaging_pub_start_ts", default=None
        )
        self._con_start: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar(
            "messaging_con_start_ts", default=None
        )

    def before_publish(self, topic: str, env: Envelope) -> Envelope:  # type: ignore[override]
        self._pub_start.set(time.perf_counter())
        return env

    def after_publish(self, topic: str, env: Envelope, result: PublishResult) -> None:  # type: ignore[override]
        if self.pub_counter:
            self.pub_counter.labels(topic=topic, result="ok").inc()
        if self.pub_latency:
            ts = self._pub_start.get()
            if ts is not None:
                self.pub_latency.observe((time.perf_counter() - ts) * 1000)
                self._pub_start.set(None)

    def before_handle(self, topic: str, partition: int, offset: int, env: Envelope) -> Envelope:  # type: ignore[override]
        self._con_start.set(time.perf_counter())
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
        if self.con_counter:
            label = "error" if exc else result.value.lower()
            self.con_counter.labels(topic=topic, result=label).inc()
        if self.con_latency:
            ts = self._con_start.get()
            if ts is not None:
                self.con_latency.observe((time.perf_counter() - ts) * 1000)
                self._con_start.set(None)
