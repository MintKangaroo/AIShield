"""Registry-specific errors independent of HTTP transport."""


class RegistryError(ValueError):
    """Raised when a registry request is unsafe or invalid."""


class RegistryNotFoundError(LookupError):
    """Raised when a requested in-memory registry entry does not exist."""
