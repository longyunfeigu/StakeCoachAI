"""Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import Response

from core.config import settings
from core.observability import metrics
from infrastructure.database import engine

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint(request: Request):
    if not settings.metrics.enabled or not metrics.HAS_PROMETHEUS:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    token = settings.metrics.access_token
    if token:
        header = request.headers.get("Authorization") or request.headers.get("X-Access-Token")
        if header and header.lower().startswith("bearer "):
            header = header[7:]
        if header != token:
            raise HTTPException(status_code=403, detail="Forbidden")

    try:
        metrics.collect_db_pool_metrics(engine)
    except Exception:
        pass

    if settings.redis.url:
        try:
            from infrastructure.external.cache import get_redis_client

            client = await get_redis_client()
            metrics.collect_redis_pool_metrics(client)
        except Exception:
            pass

    data, content_type = metrics.get_metrics_response()
    return Response(content=data, media_type=content_type)
