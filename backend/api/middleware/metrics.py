"""Prometheus HTTP metrics middleware (ASGI)."""

from __future__ import annotations

import time
from typing import Any

from core.observability import metrics


class PrometheusMiddleware:
    SKIP_PREFIXES = ("/metrics", "/health", "/docs", "/redoc", "/openapi.json")

    def __init__(self, app: Any):
        self.app = app

    def _normalize_path(self, path: str, scope: dict) -> str:
        route = scope.get("route")
        if route is not None:
            path_format = getattr(route, "path_format", None)
            if path_format:
                return path_format
            route_path = getattr(route, "path", None)
            if route_path:
                return route_path
        return "/_unknown"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(self.SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        normalized = self._normalize_path(path, scope)
        metrics.HTTP_REQUESTS_IN_FLIGHT.labels(method, normalized).inc()

        start_time = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code, normalized
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                new_normalized = self._normalize_path(path, scope)
                if new_normalized != normalized:
                    metrics.HTTP_REQUESTS_IN_FLIGHT.labels(method, normalized).dec()
                    normalized = new_normalized
                    metrics.HTTP_REQUESTS_IN_FLIGHT.labels(method, normalized).inc()
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            status_label = str(status_code)
            metrics.HTTP_REQUEST_DURATION.labels(method, normalized, status_label).observe(duration)
            metrics.HTTP_REQUESTS_TOTAL.labels(method, normalized, status_label).inc()
            metrics.HTTP_REQUESTS_IN_FLIGHT.labels(method, normalized).dec()
