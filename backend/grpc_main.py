import asyncio

from core.config import settings
from core.logging_config import configure_logging
from core.logging_config import get_logger
from grpc_app.server import create_server


logger = get_logger(__name__)


async def main() -> None:
    # Ensure logging configured for gRPC entrypoint
    configure_logging()
    if not settings.grpc.enabled:
        logger.warning("grpc_disabled", message="gRPC disabled by config (GRPC__ENABLED=false)")
        return

    server = await create_server()
    address = f"{settings.grpc.host}:{settings.grpc.port}"
    logger.info("grpc_starting", address=address)
    await server.start()
    logger.info("grpc_started", address=address)
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("grpc_stopping")
        await server.stop(grace=None)


if __name__ == "__main__":
    asyncio.run(main())
