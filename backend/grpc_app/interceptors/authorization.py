from __future__ import annotations

from typing import Callable, Awaitable

import grpc


class AuthorizationInterceptor(grpc.aio.ServerInterceptor):
    """Placeholder interceptor (user token based authorization removed)."""

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        return await continuation(handler_call_details)
