"""
统一响应格式定义
"""

from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field, field_serializer

from shared.codes import BusinessCode

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """错误详情"""

    type: str
    details: Optional[dict] = None
    field: Optional[str] = None
    request_id: Optional[str] = None
    locale: Optional[str] = None
    message_key: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime) -> str:
        """序列化时间戳为 UTC ISO8601，统一使用 Z 结尾"""
        ts = timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        s = ts.isoformat()
        return s.replace("+00:00", "Z")


class Response(BaseModel, Generic[T]):
    """统一响应模型"""

    code: int
    message: str
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None


class PaginatedData(BaseModel, Generic[T]):
    """分页数据模型"""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


def success_response(
    data: Any = None, message: str = "Success", code: int = BusinessCode.SUCCESS
) -> Response:
    """
    创建成功响应

    Args:
        data: 返回数据
        message: 成功消息
        code: 业务状态码

    Returns:
        Response: 统一响应对象
    """
    return Response(code=code, message=message, data=data, error=None)


def error_response(
    code: int,
    message: str,
    error_type: str = "BusinessError",
    details: Optional[dict] = None,
    field: Optional[str] = None,
    request_id: Optional[str] = None,
    *,
    locale: Optional[str] = None,
    message_key: Optional[str] = None,
) -> Response:
    """
    创建错误响应

    Args:
        code: 业务状态码
        message: 错误消息
        error_type: 错误类型
        details: 错误详情
        field: 错误字段
        request_id: 请求ID

    Returns:
        Response: 统一响应对象
    """
    return Response(
        code=code,
        message=message,
        data=None,
        error=ErrorDetail(
            type=error_type,
            details=details,
            field=field,
            request_id=request_id,
            locale=locale,
            message_key=message_key,
        ),
    )


def paginated_response(
    items: list, total: int, page: int, size: int, message: str = "Success"
) -> Response[PaginatedData]:
    """
    创建分页响应

    Args:
        items: 数据列表
        total: 总数
        page: 当前页
        size: 每页大小
        message: 成功消息

    Returns:
        Response: 统一响应对象
    """
    pages = (total + size - 1) // size if size > 0 else 0

    return Response(
        code=BusinessCode.SUCCESS,
        message=message,
        data=PaginatedData(items=items, total=total, page=page, size=size, pages=pages),
        error=None,
    )
