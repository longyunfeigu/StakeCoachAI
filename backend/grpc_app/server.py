from __future__ import annotations

from typing import Sequence
import os
import sys
import grpc
from grpc_health.v1 import health, health_pb2_grpc, health_pb2

from core.config import settings
from core.logging_config import get_logger
from grpc_app.interceptors.request_id import RequestIdInterceptor
from grpc_app.interceptors.logging import LoggingInterceptor
from grpc_app.interceptors.exceptions import ExceptionMappingInterceptor

# Ensure generated root is importable as top-level package `forge`
# so that generated imports like `from forge.v1 import user_pb2` work.
_gen_root = os.path.join(os.path.dirname(__file__), "generated")
if _gen_root not in sys.path:
    sys.path.insert(0, _gen_root)

from grpc_app.generated.forge.v1 import profile_pb2_grpc
from grpc_app.services.profile_service import ProfileService


logger = get_logger(__name__)


async def create_server() -> grpc.aio.Server:
    interceptors: Sequence[grpc.aio.ServerInterceptor] = (
        RequestIdInterceptor(),
        LoggingInterceptor(),
        ExceptionMappingInterceptor(),  # maps business exceptions
    )

    options = [
        ("grpc.max_concurrent_streams", max(1, settings.grpc.max_concurrent_streams)),
    ]
    server = grpc.aio.server(interceptors=interceptors, options=options)

    # Register services
    profile_pb2_grpc.add_ProfileServiceServicer_to_server(ProfileService(), server)

    # Health service
    health_svc = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_svc, server)
    health_svc.set("", health_pb2.HealthCheckResponse.SERVING)
    health_svc.set("forge.v1.ProfileService", health_pb2.HealthCheckResponse.SERVING)

    # Bind address
    address = f"{settings.grpc.host}:{settings.grpc.port}"

    if settings.grpc.tls.enabled:
        if not (settings.grpc.tls.cert and settings.grpc.tls.key):
            raise RuntimeError("GRPC TLS enabled but cert/key not provided")
        with open(settings.grpc.tls.cert, "rb") as f:
            cert_chain = f.read()
        with open(settings.grpc.tls.key, "rb") as f:
            private_key = f.read()
        root_certificates = None
        if settings.grpc.tls.ca:
            with open(settings.grpc.tls.ca, "rb") as f:
                root_certificates = f.read()
        creds = grpc.ssl_server_credentials(
            [(private_key, cert_chain)],
            root_certificates=root_certificates,
            require_client_auth=bool(root_certificates),
        )
        server.add_secure_port(address, creds)
    else:
        server.add_insecure_port(address)

    return server
