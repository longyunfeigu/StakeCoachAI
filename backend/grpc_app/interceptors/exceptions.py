from __future__ import annotations

from typing import Callable, Awaitable
import contextvars

import grpc

from core.logging_config import get_logger
from grpc_app.interceptors.request_id import get_request_id
from domain.common.exceptions import BusinessException
from shared.codes import BusinessCode


logger = get_logger(__name__)

# Mark that the current request has been mapped to a gRPC status
_mapped_error: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "grpc_mapped_error", default=False
)


def set_mapped_error() -> None:
    try:
        _mapped_error.set(True)
    except Exception:
        pass


def is_mapped_error() -> bool:
    try:
        return bool(_mapped_error.get())
    except Exception:
        return False


def _business_code_to_grpc_status(code: int) -> grpc.StatusCode:
    try:
        bc = BusinessCode(code)
    except Exception:
        return grpc.StatusCode.FAILED_PRECONDITION

    mapping = {
        BusinessCode.PARAM_VALIDATION_ERROR: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.PARAM_ERROR: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.PARAM_MISSING: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.PARAM_TYPE_ERROR: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.USER_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        BusinessCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        BusinessCode.USER_ALREADY_EXISTS: grpc.StatusCode.ALREADY_EXISTS,
        BusinessCode.PASSWORD_ERROR: grpc.StatusCode.UNAUTHENTICATED,
        BusinessCode.UNAUTHORIZED: grpc.StatusCode.UNAUTHENTICATED,
        BusinessCode.FORBIDDEN: grpc.StatusCode.PERMISSION_DENIED,
        BusinessCode.PERMISSION_ERROR: grpc.StatusCode.PERMISSION_DENIED,
        BusinessCode.TOO_MANY_REQUESTS: grpc.StatusCode.RESOURCE_EXHAUSTED,
        BusinessCode.RATE_LIMIT_ERROR: grpc.StatusCode.RESOURCE_EXHAUSTED,
        BusinessCode.SERVICE_UNAVAILABLE: grpc.StatusCode.UNAVAILABLE,
        BusinessCode.SYSTEM_ERROR: grpc.StatusCode.INTERNAL,
        BusinessCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
        BusinessCode.NETWORK_ERROR: grpc.StatusCode.UNAVAILABLE,
    }

    return mapping.get(bc, grpc.StatusCode.FAILED_PRECONDITION)


class ExceptionMappingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        async def _unary_unary(request, context: grpc.aio.ServicerContext):
            try:
                return await handler.unary_unary(request, context)
            except BusinessException as exc:
                status = _business_code_to_grpc_status(exc.code)
                try:
                    context.set_trailing_metadata(
                        (
                            ("x-biz-code", str(exc.code)),
                            ("x-error-type", exc.error_type or "BusinessError"),
                        )
                    )
                except Exception:
                    pass
                set_mapped_error()
                # Concise business error log (no stack)
                logger.error(
                    "grpc_mapped_error",
                    method=handler_call_details.method,
                    code=str(exc.code),
                    status=str(status),
                    message=exc.message,
                    request_id=get_request_id(),
                )
                await context.abort(status, exc.message)
            except Exception as exc:
                try:
                    context.set_trailing_metadata(
                        (
                            ("x-biz-code", str(BusinessCode.SYSTEM_ERROR.value)),
                            ("x-error-type", "SystemError"),
                        )
                    )
                except Exception:
                    pass
                set_mapped_error()
                logger.error(
                    "grpc_mapped_error",
                    method=handler_call_details.method,
                    code=str(BusinessCode.SYSTEM_ERROR.value),
                    status=str(grpc.StatusCode.INTERNAL),
                    message=str(exc),
                    request_id=get_request_id(),
                )
                await context.abort(grpc.StatusCode.INTERNAL, "系统内部错误")

        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                _unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
