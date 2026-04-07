"""
Request ID 中间件
用于生成或透传追踪ID，并通过contextvars传递给日志系统
"""

import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import structlog

from core.config import settings
from core.observability.tracing import get_current_trace_id, set_request_span_attributes

# 定义context变量，用于在请求生命周期内共享request_id
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
client_ip_var: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Request ID 追踪中间件

    功能：
    1. 从请求头获取或生成新的request_id
    2. 将request_id存入contextvars，供日志系统使用
    3. 在响应头中返回request_id
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        # 从请求头获取request_id，如果不存在则生成新的
        request_id = request.headers.get(self.HEADER_NAME)
        if not request_id:
            request_id = str(uuid.uuid4())

        # 获取客户端IP
        client_ip = self._get_client_ip(request)

        # 设置到request.state以便在应用内部访问
        request.state.request_id = request_id
        request.state.client_ip = client_ip

        # 设置contextvars，这样structlog可以自动获取
        request_id_var.set(request_id)
        client_ip_var.set(client_ip)

        # 绑定到structlog上下文
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            client_ip=client_ip,
            method=request.method,
            path=request.url.path,
        )

        # 给当前 span 打标签（若 tracing 可用）
        set_request_span_attributes(
            request_id=request_id,
            client_ip=client_ip,
            http_method=request.method,
            http_path=request.url.path,
        )

        # 处理请求
        response = await call_next(request)

        # 在响应头中添加request_id
        response.headers[self.HEADER_NAME] = request_id

        trace_id = get_current_trace_id()
        if trace_id and settings.tracing.expose_trace_id:
            response.headers["X-Trace-ID"] = trace_id

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实IP

        Args:
            request: FastAPI请求对象

        Returns:
            客户端IP地址
        """
        # 尝试从X-Forwarded-For获取（考虑代理的情况）
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # 取第一个IP（原始客户端IP）
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            # 尝试从X-Real-IP获取
            client_ip = request.headers.get("X-Real-IP")
            if not client_ip:
                # 最后从client获取
                client_ip = request.client.host if request.client else "unknown"

        return client_ip


def get_request_id() -> Optional[str]:
    """
    获取当前请求的request_id

    Returns:
        当前请求的request_id，如果不在请求上下文中则返回None
    """
    return request_id_var.get()


def get_client_ip() -> Optional[str]:
    """
    获取当前请求的客户端IP

    Returns:
        当前请求的客户端IP，如果不在请求上下文中则返回None
    """
    return client_ip_var.get()
