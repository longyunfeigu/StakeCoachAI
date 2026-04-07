"""Storage service exceptions."""


class StorageError(Exception):
    """Base storage exception."""

    pass


class NotFoundError(StorageError):
    """File not found in storage."""

    pass


class PermissionDeniedError(StorageError):
    """Permission denied for storage operation."""

    pass


class TransientError(StorageError):
    """Transient error (network, rate limit, server error)."""

    pass


class ConfigurationError(StorageError):
    """Storage configuration error."""

    pass


class ValidationError(StorageError):
    """Storage validation error."""

    pass
