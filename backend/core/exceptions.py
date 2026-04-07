"""
自定义异常映射与全局异常处理器
"""

from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
import traceback
import uuid
from datetime import datetime
from starlette import status as http_status

from .response import error_response
from shared.codes import BusinessCode
from core.logging_config import get_logger
from domain.common.exceptions import BusinessException
from core.i18n import t, get_locale


class RateLimitException(BusinessException):
    """限流异常"""

    def __init__(self, retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            code=BusinessCode.TOO_MANY_REQUESTS,
            message="Too many requests, please try again later",
            error_type="RateLimit",
            details=details,
            message_key="rate.limited",
            format_params=details or {},
        )


def register_exception_handlers(app: FastAPI):
    """
    注册全局异常处理器

    Args:
        app: FastAPI应用实例
    """

    # logger
    logger = get_logger(__name__)

    def _business_code_to_http_status(code: int) -> int:
        """根据业务码映射HTTP状态码（默认400）。"""
        mapping = {
            BusinessCode.PARAM_ERROR: http_status.HTTP_400_BAD_REQUEST,
            BusinessCode.PARAM_MISSING: http_status.HTTP_400_BAD_REQUEST,
            BusinessCode.PARAM_TYPE_ERROR: http_status.HTTP_400_BAD_REQUEST,
            BusinessCode.PARAM_VALIDATION_ERROR: http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            BusinessCode.BUSINESS_ERROR: http_status.HTTP_400_BAD_REQUEST,
            BusinessCode.USER_NOT_FOUND: http_status.HTTP_404_NOT_FOUND,
            BusinessCode.NOT_FOUND: http_status.HTTP_404_NOT_FOUND,
            BusinessCode.USER_ALREADY_EXISTS: http_status.HTTP_409_CONFLICT,
            BusinessCode.PASSWORD_ERROR: http_status.HTTP_401_UNAUTHORIZED,
            BusinessCode.PERMISSION_ERROR: http_status.HTTP_403_FORBIDDEN,
            BusinessCode.UNAUTHORIZED: http_status.HTTP_401_UNAUTHORIZED,
            BusinessCode.FORBIDDEN: http_status.HTTP_403_FORBIDDEN,
            BusinessCode.SYSTEM_ERROR: http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            BusinessCode.DATABASE_ERROR: http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            BusinessCode.NETWORK_ERROR: http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            BusinessCode.SERVICE_UNAVAILABLE: http_status.HTTP_503_SERVICE_UNAVAILABLE,
            BusinessCode.RATE_LIMIT_ERROR: http_status.HTTP_429_TOO_MANY_REQUESTS,
            BusinessCode.TOO_MANY_REQUESTS: http_status.HTTP_429_TOO_MANY_REQUESTS,
            BusinessCode.CHATROOM_NOT_FOUND: http_status.HTTP_404_NOT_FOUND,
            BusinessCode.SCENARIO_NOT_FOUND: http_status.HTTP_404_NOT_FOUND,
        }
        try:
            bc = BusinessCode(code)
            return mapping.get(bc, http_status.HTTP_400_BAD_REQUEST)
        except Exception:
            return http_status.HTTP_400_BAD_REQUEST

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        """处理业务异常"""
        request_id = getattr(getattr(request, "state", object()), "request_id", None) or str(
            uuid.uuid4()
        )
        locale = get_locale()
        # Render i18n message if message_key is provided, otherwise fallback to original message
        fmt_params = getattr(exc, "format_params", None)
        params = fmt_params if isinstance(fmt_params, dict) else (exc.details or {})
        translated = t(getattr(exc, "message_key", "") or exc.message, **params)
        response = error_response(
            code=exc.code,
            message=translated,
            error_type=exc.error_type,
            details=exc.details,
            field=exc.field,
            request_id=request_id,
            locale=locale,
            message_key=getattr(exc, "message_key", None),
        )
        status_code = _business_code_to_http_status(exc.code)
        # 对于401可选地返回WWW-Authenticate，但仅对需要的场景添加
        headers = (
            {"WWW-Authenticate": "Bearer"}
            if status_code == http_status.HTTP_401_UNAUTHORIZED
            else None
        )
        return JSONResponse(
            status_code=status_code, content=response.model_dump(mode="json"), headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理参数验证异常"""
        request_id = getattr(getattr(request, "state", object()), "request_id", None) or str(
            uuid.uuid4()
        )
        errors = exc.errors()

        # 提取第一个错误的详细信息
        first_error = errors[0] if errors else {}
        field = ".".join(str(loc) for loc in first_error.get("loc", [])[1:])

        locale = get_locale()
        response = error_response(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message=t("validation.failed", reason=first_error.get("msg", "unknown")),
            error_type="ValidationError",
            details={"errors": errors},
            field=field,
            request_id=request_id,
            locale=locale,
            message_key="validation.failed",
        )
        return JSONResponse(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.model_dump(mode="json"),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理HTTP异常"""
        request_id = getattr(getattr(request, "state", object()), "request_id", None) or str(
            uuid.uuid4()
        )

        # 映射HTTP状态码到业务码
        code_mapping = {
            401: BusinessCode.UNAUTHORIZED,
            403: BusinessCode.FORBIDDEN,
            404: BusinessCode.NOT_FOUND,
            429: BusinessCode.TOO_MANY_REQUESTS,
            500: BusinessCode.SYSTEM_ERROR,
            503: BusinessCode.SERVICE_UNAVAILABLE,
        }
        code = code_mapping.get(exc.status_code, BusinessCode.SYSTEM_ERROR)

        locale = get_locale()
        response = error_response(
            code=code,
            message=str(exc.detail),
            error_type="HTTPError",
            details={"status_code": exc.status_code},
            request_id=request_id,
            locale=locale,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        request_id = getattr(getattr(request, "state", object()), "request_id", None) or str(
            uuid.uuid4()
        )

        # 在开发环境可以返回详细错误信息
        details = None
        if app.debug:
            details = {"exception": str(exc), "traceback": traceback.format_exc()}

        locale = get_locale()
        response = error_response(
            code=BusinessCode.SYSTEM_ERROR,
            message=t("error.internal"),
            error_type="SystemError",
            details=details,
            request_id=request_id,
            locale=locale,
            message_key="error.internal",
        )

        # 记录日志（使用结构化日志）
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            error=str(exc),
            exc_info=True,
        )

        return JSONResponse(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(mode="json"),
        )
