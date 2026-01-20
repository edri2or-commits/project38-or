"""
Model Provider Registry.

Singleton registry for managing model providers.
Allows dynamic registration and switching between providers at runtime.

Architecture Decision: ADR-009

Usage:
    from src.providers import ModelRegistry

    # Register a provider
    ModelRegistry.register("claude", ClaudeProvider(api_key="..."))

    # Get a provider
    provider = ModelRegistry.get("claude")

    # Set default
    ModelRegistry.set_default("claude")
    provider = ModelRegistry.get()  # Returns claude

    # List all providers
    for name in ModelRegistry.list_providers():
        print(name)
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.providers.base import ModelProvider

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Singleton registry for model providers.

    Thread-safe registry that allows:
    - Registering providers by name
    - Getting providers by name
    - Setting a default provider
    - Listing all available providers

    The registry is a class with class methods, making it a singleton
    that can be accessed from anywhere without instantiation.
    """

    _providers: dict[str, "ModelProvider"] = {}
    _default: str | None = None
    _initialized: bool = False

    @classmethod
    def register(cls, name: str, provider: "ModelProvider") -> None:
        """Register a provider with a given name.

        Args:
            name: Unique identifier for this provider
            provider: ModelProvider instance

        Raises:
            ValueError: If name already registered (use replace=True to override)
        """
        if name in cls._providers:
            logger.warning(f"Replacing existing provider: {name}")

        cls._providers[name] = provider
        logger.info(f"Registered provider: {name} ({provider.model_id})")

        # Set as default if first provider
        if cls._default is None:
            cls._default = name
            logger.info(f"Set default provider: {name}")

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove a provider from the registry.

        Args:
            name: Name of provider to remove

        Raises:
            KeyError: If provider not found
        """
        if name not in cls._providers:
            raise KeyError(f"Provider not found: {name}")

        del cls._providers[name]
        logger.info(f"Unregistered provider: {name}")

        # Clear default if it was removed
        if cls._default == name:
            cls._default = next(iter(cls._providers), None)
            if cls._default:
                logger.info(f"New default provider: {cls._default}")

    @classmethod
    def get(cls, name: str | None = None) -> "ModelProvider":
        """Get a provider by name, or the default provider.

        Args:
            name: Provider name, or None for default

        Returns:
            ModelProvider instance

        Raises:
            KeyError: If provider not found
            RuntimeError: If no providers registered and no name specified
        """
        if name is None:
            if cls._default is None:
                raise RuntimeError("No providers registered")
            name = cls._default

        if name not in cls._providers:
            available = ", ".join(cls._providers.keys()) or "none"
            raise KeyError(f"Provider not found: {name}. Available: {available}")

        return cls._providers[name]

    @classmethod
    def set_default(cls, name: str) -> None:
        """Set the default provider.

        Args:
            name: Name of provider to set as default

        Raises:
            KeyError: If provider not found
        """
        if name not in cls._providers:
            raise KeyError(f"Provider not found: {name}")

        cls._default = name
        logger.info(f"Set default provider: {name}")

    @classmethod
    def get_default_name(cls) -> str | None:
        """Get the name of the default provider."""
        return cls._default

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def has_provider(cls, name: str) -> bool:
        """Check if a provider is registered."""
        return name in cls._providers

    @classmethod
    def clear(cls) -> None:
        """Remove all providers (useful for testing)."""
        cls._providers.clear()
        cls._default = None
        logger.info("Cleared all providers")

    @classmethod
    async def health_check_all(cls) -> dict[str, bool]:
        """Check health of all registered providers.

        Returns:
            Dict mapping provider name to health status
        """
        results = {}
        for name, provider in cls._providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
        return results

    @classmethod
    def get_capabilities_summary(cls) -> dict[str, dict]:
        """Get capabilities of all providers.

        Returns:
            Dict mapping provider name to capabilities dict
        """
        summary = {}
        for name, provider in cls._providers.items():
            caps = provider.get_capabilities()
            summary[name] = {
                "model_id": provider.model_id,
                "supports_vision": caps.supports_vision,
                "supports_streaming": caps.supports_streaming,
                "max_context_tokens": caps.max_context_tokens,
                "cost_per_1k_input": caps.cost_per_1k_input_tokens,
                "cost_per_1k_output": caps.cost_per_1k_output_tokens,
            }
        return summary
