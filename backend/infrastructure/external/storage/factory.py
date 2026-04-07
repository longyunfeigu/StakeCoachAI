"""Storage provider factory with registry pattern."""

from typing import Callable, Awaitable, Optional
import importlib

from core.logging_config import get_logger
from .base import StorageProvider
from .config import StorageConfig, StorageType
from .exceptions import ConfigurationError

logger = get_logger(__name__)

# Provider builder type
ProviderBuilder = Callable[[StorageConfig], Awaitable[StorageProvider]]

# Global registry for storage providers
_provider_registry: dict[StorageType, ProviderBuilder] = {}


def register_provider(storage_type: StorageType, builder: ProviderBuilder) -> None:
    """Register a storage provider builder.

    Args:
        storage_type: Type of storage provider
        builder: Async function to build provider instance
    """
    _provider_registry[storage_type] = builder
    logger.info(f"Registered storage provider: {storage_type}")


async def create_provider(config: StorageConfig) -> StorageProvider:
    """Create storage provider instance based on config.

    Args:
        config: Storage configuration

    Returns:
        Configured storage provider instance

    Raises:
        ConfigurationError: If provider type not registered or creation fails
    """
    if config.type not in _provider_registry:
        # Try to auto-register built-in providers
        await _auto_register_providers()

        if config.type not in _provider_registry:
            raise ConfigurationError(
                f"Storage provider '{config.type}' not registered. "
                f"Available: {list(_provider_registry.keys())}"
            )

    builder = _provider_registry[config.type]

    try:
        provider = await builder(config)
        logger.info(f"Created storage provider", provider=config.type, bucket=config.bucket)
        return provider
    except Exception as e:
        logger.error(f"Failed to create storage provider", provider=config.type, error=str(e))
        raise ConfigurationError(f"Failed to create storage provider '{config.type}': {e}") from e


async def _auto_register_providers() -> None:
    """Auto-register built-in storage providers."""
    providers = [
        (StorageType.S3, "infrastructure.external.storage.providers.s3", "build_s3_provider"),
        (StorageType.OSS, "infrastructure.external.storage.providers.oss", "build_oss_provider"),
        (
            StorageType.LOCAL,
            "infrastructure.external.storage.providers.local",
            "build_local_provider",
        ),
    ]

    for storage_type, module_path, builder_name in providers:
        if storage_type in _provider_registry:
            continue

        try:
            module = importlib.import_module(module_path)
            builder = getattr(module, builder_name)
            register_provider(storage_type, builder)
        except (ImportError, AttributeError) as e:
            logger.debug(f"Provider {storage_type} not available: {e}")
