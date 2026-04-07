from __future__ import annotations

import time
from typing import Callable, Awaitable

import grpc

from core.logging_config import get_logger
from grpc_app.interceptors.request_id import get_request_id
from grpc_app.interceptors.exceptions import is_mapped_error


logger = get_logger(__name__)


class LoggingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        method = handler_call_details.method

        async def _unary_unary(request, context: grpc.aio.ServicerContext):
            start = time.perf_counter()
            try:
                peer = context.peer() if hasattr(context, "peer") else None
                logger.info("grpc_request", method=method, peer=peer, request_id=get_request_id())
                resp = await handler.unary_unary(request, context)
                return resp
            except grpc.RpcError:
                # Already mapped/aborted by exception interceptor; avoid duplicate error logs here
                raise
            except Exception as exc:
                # Normalize gRPC abort errors (with code/details) vs truly unhandled exceptions.
                if is_mapped_error():
                    # Exception has been mapped to a gRPC status already; avoid duplicate logs here
                    raise
                code = None
                details = None
                # Many server-side aborts raise grpc.RpcError / AbortError with code()/details()
                try:
                    if hasattr(exc, "code") and callable(getattr(exc, "code")):
                        code = exc.code()  # type: ignore[attr-defined]
                    if hasattr(exc, "details") and callable(getattr(exc, "details")):
                        details = exc.details()  # type: ignore[attr-defined]
                except Exception:
                    pass

                if (
                    code is not None
                ):  # Already mapped/aborted by exception interceptor; avoid duplicate logs
                    raise

                # Unknown/unexpected exception -> log with stack
                logger.error(
                    "grpc_unhandled_error",
                    method=method,
                    error=str(exc),
                    exc_info=True,
                    request_id=get_request_id(),
                )
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "grpc_request_done",
                    method=method,
                    elapsed_ms=round(elapsed_ms, 2),
                    request_id=get_request_id(),
                )

        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                _unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
