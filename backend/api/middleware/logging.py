"""
请求/响应日志中间件
记录所有HTTP请求和响应，包括耗时统计
"""

import time
from typing import Any
import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logging_config import get_logger
from core.config import settings


logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    日志记录中间件

    功能：
    1. 记录请求信息（方法、路径、参数等）
    2. 记录响应信息（状态码、耗时等）
    3. 记录异常信息
    4. 统计请求处理时间
    """

    # 跳过日志的路径
    SKIP_PATHS = {
        "/health",
        "/health/live",
        "/health/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # 敏感字段，日志中需要脱敏
    SENSITIVE_FIELDS = {"password", "secret", "api_key", "old_password", "new_password"}

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # 从配置读取可调参数
        self.enable_body_log_default: bool = settings.LOG_REQUEST_BODY_ENABLE_BY_DEFAULT
        self.max_body_log_bytes: int = settings.LOG_REQUEST_BODY_MAX_BYTES
        self.allow_multipart_body_log: bool = settings.LOG_REQUEST_BODY_ALLOW_MULTIPART

    async def dispatch(self, request: Request, call_next):
        # 检查是否需要跳过日志
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # 记录开始时间
        start_time = time.time()

        # 获取请求信息（不读 body，避免 BaseHTTPMiddleware + call_next 死锁）
        request_info = await self._get_request_info(request, skip_body=True)

        # 记录请求日志
        logger.info("request_started", **request_info)

        # 处理请求
        try:
            response = await call_next(request)

            # 计算耗时
            duration = time.time() - start_time

            # 记录响应日志
            self._log_response(response, duration, request_info)

            # 在响应头中添加处理时间
            response.headers["X-Process-Time"] = f"{duration:.3f}"

            return response

        except Exception as exc:
            # 计算耗时
            duration = time.time() - start_time

            # 记录异常日志
            logger.error(
                "request_failed",
                duration=duration,
                error=str(exc),
                error_type=type(exc).__name__,
                **request_info,
                exc_info=True,
            )

            # 重新抛出异常，让异常处理器处理
            raise

    async def _get_request_info(self, request: Request, *, skip_body: bool = False) -> dict:
        """
        获取请求信息

        Args:
            request: FastAPI请求对象

        Returns:
            请求信息字典
        """
        # 基本信息
        info = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
        }

        # 添加路径参数
        if hasattr(request, "path_params"):
            info["path_params"] = request.path_params

        # 添加请求体（按开关/限制/脱敏）
        # NOTE: skip_body=True 时跳过 body 读取，避免在 BaseHTTPMiddleware.dispatch 中
        # 调用 request.body() 导致 call_next() 死锁（body 流被消费后无法转发）
        if (
            not skip_body
            and request.method in ["POST", "PUT", "PATCH"]
            and self._should_log_body(request)
        ):
            body_snippet = await self._extract_and_sanitize_body(request)
            if body_snippet is not None:
                info["body"] = body_snippet
            else:
                info["has_body"] = True

        # 添加用户代理
        user_agent = request.headers.get("User-Agent")
        if user_agent:
            info["user_agent"] = user_agent

        # 添加来源
        referer = request.headers.get("Referer")
        if referer:
            info["referer"] = referer

        return info

    def _should_log_body(self, request: Request) -> bool:
        # 默认按配置与 DEBUG 开关，可通过请求头禁用/启用
        # X-Log-Body: true/false
        header = (request.headers.get("X-Log-Body") or "").lower()
        if header in {"true", "1", "yes"}:
            return True
        if header in {"false", "0", "no"}:
            return False
        # 按环境默认
        return bool(self.enable_body_log_default and settings.DEBUG)

    async def _extract_and_sanitize_body(self, request: Request) -> Any:
        # Fast-path: avoid buffering huge uploads or multipart bodies unless explicitly allowed.
        content_type = request.headers.get("content-type", "").lower()
        if "multipart/form-data" in content_type and not self.allow_multipart_body_log:
            return None

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
            except Exception:
                length = 0
            if length and length > self.max_body_log_bytes:
                return {"truncated": True, "content_length": length}

        try:
            body = await request.body()
        except Exception:
            return None

        if not body:
            return None

        # 限制大小
        snippet = body[: self.max_body_log_bytes]

        # 内容类型处理
        parsed: Any = None
        if "application/json" in content_type:
            try:
                parsed = json.loads(snippet.decode("utf-8", errors="ignore"))
            except Exception:
                parsed = snippet.decode("utf-8", errors="ignore")
        elif "application/x-www-form-urlencoded" in content_type:
            try:
                from urllib.parse import parse_qs

                parsed = {
                    k: v if len(v) > 1 else v[0]
                    for k, v in parse_qs(snippet.decode("utf-8", errors="ignore")).items()
                }
            except Exception:
                parsed = snippet.decode("utf-8", errors="ignore")
        elif "multipart/form-data" in content_type:
            # 避免解析文件；按配置决定是否记录提示
            if not self.allow_multipart_body_log:
                return None
            return {"multipart": True}
        else:
            # 其它类型按文本截断
            parsed = snippet.decode("utf-8", errors="ignore")

        return self._sanitize_data(parsed)

    def _sanitize_data(self, data: Any) -> Any:
        try:
            if isinstance(data, dict):
                return {
                    k: ("***" if k.lower() in self.SENSITIVE_FIELDS else self._sanitize_data(v))
                    for k, v in data.items()
                }
            if isinstance(data, list):
                return [self._sanitize_data(v) for v in data]
            if isinstance(data, tuple):
                return tuple(self._sanitize_data(v) for v in data)
            return data
        except Exception:
            return data

    def _log_response(self, response: Response, duration: float, request_info: dict):
        """
        记录响应日志

        Args:
            response: FastAPI响应对象
            duration: 请求处理时间
            request_info: 请求信息
        """
        # 根据状态码选择日志级别
        status_code = response.status_code

        log_data = {"status_code": status_code, "duration": duration, **request_info}

        if status_code < 400:
            # 成功响应
            logger.info("request_completed", **log_data)
        elif status_code < 500:
            # 客户端错误
            logger.warning("request_client_error", **log_data)
        else:
            # 服务器错误
            logger.error("request_server_error", **log_data)

    # _sanitize_data 未被使用，已删除以保持简洁


class AccessLogMiddleware:
    """
    访问日志中间件（轻量级）
    仅记录访问日志，不记录详细的请求/响应信息
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time

                # 记录访问日志
                logger.info(
                    "access",
                    method=scope["method"],
                    path=scope["path"],
                    status=message["status"],
                    duration=duration,
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)
