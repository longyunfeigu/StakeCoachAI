"""Storage service entry point and lifecycle management."""

from typing import Optional
from functools import lru_cache

from core.config import settings
from core.logging_config import get_logger
from .base import StorageProvider
from .config import StorageConfig, StorageType
from .factory import create_provider
from .utils import LoggingMiddleware, ValidationMiddleware, apply_middleware

logger = get_logger(__name__)

# Global storage client instance
_storage_client: Optional[StorageProvider] = None


@lru_cache
def get_storage_config() -> StorageConfig:
    """Get storage configuration from settings.

    Assembles StorageConfig from core.config.settings to maintain
    single source of truth for configuration.

    Returns:
        Storage configuration instance
    """
    s = settings.storage
    config_dict = {
        "type": s.type or StorageType.LOCAL,
        "bucket": s.bucket,
        "region": s.region,
        "endpoint": s.endpoint,
        "public_base_url": s.public_base_url,
        # S3 specific
        "aws_access_key_id": s.aws_access_key_id,
        "aws_secret_access_key": s.aws_secret_access_key,
        "s3_sse": s.s3_sse,
        "s3_acl": s.s3_acl,
        # OSS specific
        "oss_access_key_id": s.oss_access_key_id,
        "oss_access_key_secret": s.oss_access_key_secret,
        # Local specific
        "local_base_path": s.local_base_path,
        # Advanced settings
        "max_retry_attempts": s.max_retry_attempts,
        "timeout": s.timeout,
        "enable_ssl": s.enable_ssl,
        "presign_max_size": s.presign_max_size,
        "presign_content_types": s.presign_content_types
        or [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "application/pdf",
            "video/mp4",
            "audio/mpeg",
        ],
    }

    return StorageConfig(**config_dict)


async def init_storage_client() -> None:
    """Initialize storage client.

    Creates and configures the storage provider based on configuration.
    Similar pattern to redis_client.py for consistency.
    """
    global _storage_client

    if _storage_client is not None:
        logger.warning("Storage client already initialized")
        return

    try:
        config = get_storage_config()

        # Create provider
        provider = await create_provider(config)

        # Apply middleware
        middlewares = []

        # Add logging middleware
        middlewares.append(LoggingMiddleware())

        # Add validation middleware if configured
        s = settings.storage
        if s.validation_enabled:
            max_size = s.max_file_size
            allowed_types = s.allowed_types
            middlewares.append(ValidationMiddleware(max_size, allowed_types))

        # Apply middleware
        _storage_client = apply_middleware(provider, middlewares)

        logger.info("storage_client_initialized", provider=config.type, bucket=config.bucket)

    except Exception as e:
        logger.error("storage_client_init_failed", error=str(e))
        raise


def get_storage_client() -> Optional[StorageProvider]:
    """Get storage client instance.

    Returns:
        Storage provider instance or None if not initialized
    """
    return _storage_client


async def shutdown_storage_client() -> None:
    """Shutdown storage client.

    Performs cleanup for storage provider.
    """
    global _storage_client

    if _storage_client is None:
        return

    try:
        # Perform any cleanup if needed
        # Most providers don't need explicit cleanup
        logger.info("Storage client shutdown")
    except Exception as e:
        logger.error(f"Error during storage shutdown", error=str(e))
    finally:
        _storage_client = None


async def get_storage() -> StorageProvider:
    """FastAPI dependency for storage service.

    Returns:
        Storage provider instance

    Raises:
        RuntimeError: If storage not initialized
    """
    client = get_storage_client()
    if client is None:
        raise RuntimeError(
            "Storage client not initialized. " "Call init_storage_client() during startup."
        )
    return client


# Export public interface
__all__ = [
    # Lifecycle
    "init_storage_client",
    "get_storage_client",
    "shutdown_storage_client",
    "get_storage",
    # Configuration
    "get_storage_config",
    "StorageConfig",
    "StorageType",
    # Base types
    "StorageProvider",
    # Models
    "UploadResult",
    "StorageObject",
    "StorageMetadata",
    "PresignedRequest",
    # Exceptions
    "StorageError",
    "NotFoundError",
    "PermissionDeniedError",
    "TransientError",
    "ConfigurationError",
    "ValidationError",
    # Utils
    "key_builder",
    "guess_content_type",
    "safe_join",
]

# Import models and exceptions for easier access
from .models import UploadResult, StorageObject, StorageMetadata, PresignedRequest
from .exceptions import (
    StorageError,
    NotFoundError,
    PermissionDeniedError,
    TransientError,
    ConfigurationError,
    ValidationError,
)
from .utils import key_builder, guess_content_type, safe_join
