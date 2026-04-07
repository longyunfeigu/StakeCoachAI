"""
REST API客户端基类

提供通用的HTTP请求功能，包括：
- 自动重试
- 错误处理
- 请求/响应日志
- 认证支持
- 超时控制
"""

import json
from typing import Dict, Any, Optional, Union, Type, TypeVar
from dataclasses import dataclass
from enum import Enum
import httpx
from pydantic import BaseModel
from core.logging_config import get_logger
from datetime import datetime

from httpx_retries import RetryTransport, Retry

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class HTTPMethod(Enum):
    """HTTP方法枚举"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class APIResponse:
    """API响应封装"""

    status_code: int
    headers: Dict[str, str]
    data: Any
    raw_content: bytes
    elapsed_ms: float
    request_id: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """判断请求是否成功"""
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        """判断请求是否失败"""
        return self.status_code >= 400

    def json(self) -> Any:
        """获取JSON响应"""
        if self.data is not None:
            return self.data
        return json.loads(self.raw_content)

    def text(self) -> str:
        """获取文本响应"""
        return self.raw_content.decode("utf-8")


class APIError(Exception):
    """API错误基类"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[APIResponse] = None,
        request_id: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        self.request_id = request_id
        super().__init__(self.message)

    def __str__(self):
        parts = [self.message]
        if self.status_code:
            parts.append(f"Status: {self.status_code}")
        if self.request_id:
            parts.append(f"Request ID: {self.request_id}")
        return " | ".join(parts)


class RateLimitError(APIError):
    """速率限制错误"""

    pass


class AuthenticationError(APIError):
    """认证错误"""

    pass


class NotFoundError(APIError):
    """资源未找到错误"""

    pass


class ServerError(APIError):
    """服务器错误"""

    pass


# Retry logic is handled by httpx-retries transport


class BaseAPIClient:
    """
    REST API客户端基类

    提供通用的HTTP请求功能，子类可以继承并实现具体的API调用
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None,
        verify_ssl: bool = True,
        debug: bool = False,
    ):
        """
        初始化API客户端

        Args:
            base_url: API基础URL
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            headers: 默认请求头
            auth_token: 认证令牌
            verify_ssl: 是否验证SSL证书
            debug: 是否开启调试模式
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.verify_ssl = verify_ssl
        self.debug = debug

        # 设置默认请求头
        self.default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FastAPI-Forge/1.0",
        }
        if headers:
            self.default_headers.update(headers)

        # 设置认证
        if auth_token:
            self.set_auth_token(auth_token)

        # 创建HTTP客户端
        self._client: Optional[httpx.AsyncClient] = None

    def set_auth_token(
        self, token: str, header_name: str = "Authorization", prefix: str = "Bearer"
    ):
        """设置认证令牌"""
        self.default_headers[header_name] = f"{prefix} {token}" if prefix else token

    def remove_auth_token(self, header_name: str = "Authorization"):
        """移除认证令牌"""
        self.default_headers.pop(header_name, None)

    @property
    async def client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                verify=self.verify_ssl,
                follow_redirects=True,
                transport=RetryTransport(
                    retry=Retry(total=self.max_retries, backoff_factor=self.retry_delay)
                ),
            )
        return self._client

    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    def _build_url(self, endpoint: str) -> str:
        """构建完整URL"""
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"

    def _log_request(self, method: str, url: str, **kwargs):
        """记录请求日志（结构化字段）。"""
        if self.debug:
            headers = kwargs.get("headers", {}) or {}
            redacted = {k: v for k, v in headers.items() if k.lower() != "authorization"}
            logger.debug(
                "api_request",
                method=method,
                url=url,
                params=kwargs.get("params"),
                json=kwargs.get("json"),
                headers=redacted,
            )

    def _log_response(self, response: APIResponse):
        """记录响应日志（结构化字段）。"""
        if self.debug:
            logger.debug(
                "api_response",
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                request_id=response.request_id,
                data=(response.data if response.status_code < 400 else None),
            )

    def _handle_error_response(self, status_code: int, response: APIResponse):
        """处理错误响应"""
        error_map = {
            400: APIError,
            401: AuthenticationError,
            403: AuthenticationError,
            404: NotFoundError,
            429: RateLimitError,
            500: ServerError,
            502: ServerError,
            503: ServerError,
            504: ServerError,
        }

        error_class = error_map.get(status_code, APIError)

        # 尝试从响应中提取错误消息
        error_message = f"API request failed with status {status_code}"
        try:
            if response.data and isinstance(response.data, dict):
                error_message = (
                    response.data.get("message")
                    or response.data.get("error")
                    or response.data.get("detail")
                    or error_message
                )
        except Exception:
            pass

        raise error_class(
            message=error_message,
            status_code=status_code,
            response=response,
            request_id=response.request_id,
        )

    async def _request(
        self,
        method: Union[str, HTTPMethod],
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Union[Dict[str, Any], BaseModel]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> APIResponse:
        """
        发送HTTP请求

        Args:
            method: HTTP方法
            endpoint: API端点
            params: 查询参数
            json_data: JSON数据
            data: 表单数据
            headers: 请求头
            files: 上传文件
            **kwargs: 其他httpx参数

        Returns:
            APIResponse: API响应

        Raises:
            APIError: API错误
        """
        # 处理方法
        if isinstance(method, HTTPMethod):
            method = method.value

        # 构建URL
        url = self._build_url(endpoint)

        # 合并请求头
        request_headers = {**self.default_headers}
        if headers:
            request_headers.update(headers)

        # 处理JSON数据
        if json_data:
            if isinstance(json_data, BaseModel):
                json_data = json_data.model_dump(exclude_unset=True)

        # 记录请求
        self._log_request(method, url, params=params, json=json_data, headers=request_headers)

        # 发送请求
        async def _send_once() -> APIResponse:
            start_time = datetime.now()
            client = await self.client
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                data=data,
                headers=request_headers,
                files=files,
                **kwargs,
            )

            elapsed = (datetime.now() - start_time).total_seconds() * 1000

            content_type = response.headers.get("content-type", "")
            response_data = None

            if "application/json" in content_type:
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = None

            api_response = APIResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                data=response_data,
                raw_content=response.content,
                elapsed_ms=elapsed,
                request_id=response.headers.get("x-request-id"),
            )

            self._log_response(api_response)

            # Transient retryable responses are handled by httpx-retries transport

            if api_response.is_error:
                self._handle_error_response(api_response.status_code, api_response)

            return api_response

        try:
            return await _send_once()
        except httpx.TimeoutException as exc:
            raise APIError(f"Request timeout after {self.timeout}s") from exc
        except httpx.RequestError as exc:
            raise APIError(f"Network error: {exc}") from exc
        except Exception as exc:
            logger.error(f"Unexpected error during API request: {exc}")
            raise APIError(f"Unexpected error: {exc}") from exc

    async def get(self, endpoint: str, **kwargs) -> APIResponse:
        """GET请求"""
        return await self._request(HTTPMethod.GET, endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> APIResponse:
        """POST请求"""
        return await self._request(HTTPMethod.POST, endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> APIResponse:
        """PUT请求"""
        return await self._request(HTTPMethod.PUT, endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> APIResponse:
        """PATCH请求"""
        return await self._request(HTTPMethod.PATCH, endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> APIResponse:
        """DELETE请求"""
        return await self._request(HTTPMethod.DELETE, endpoint, **kwargs)

    async def get_typed(self, endpoint: str, response_model: Type[T], **kwargs) -> T:
        """发送GET请求并返回类型化响应"""
        response = await self.get(endpoint, **kwargs)
        return response_model(**response.json())

    async def post_typed(self, endpoint: str, response_model: Type[T], **kwargs) -> T:
        """发送POST请求并返回类型化响应"""
        response = await self.post(endpoint, **kwargs)
        return response_model(**response.json())
