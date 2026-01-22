"""Tests for src/providers/registry.py - Model Provider Registry."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestModelRegistryBasics:
    """Tests for ModelRegistry basic operations."""

    def test_registry_import(self):
        """ModelRegistry should be importable."""
        from src.providers.registry import ModelRegistry

        assert ModelRegistry is not None

    def test_registry_has_class_methods(self):
        """ModelRegistry should have expected class methods."""
        from src.providers.registry import ModelRegistry

        assert hasattr(ModelRegistry, "register")
        assert hasattr(ModelRegistry, "unregister")
        assert hasattr(ModelRegistry, "get")
        assert hasattr(ModelRegistry, "set_default")
        assert hasattr(ModelRegistry, "list_providers")
        assert hasattr(ModelRegistry, "clear")

    def test_registry_clear(self):
        """ModelRegistry.clear should remove all providers."""
        from src.providers.registry import ModelRegistry

        # Start fresh
        ModelRegistry.clear()
        assert ModelRegistry.list_providers() == []
        assert ModelRegistry.get_default_name() is None


class TestModelRegistryRegister:
    """Tests for ModelRegistry.register method."""

    def test_register_provider(self):
        """register should add provider to registry."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test-model-v1"

        ModelRegistry.register("test", mock_provider)
        assert ModelRegistry.has_provider("test")

    def test_register_sets_first_as_default(self):
        """register should set first provider as default."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test-model-v1"

        ModelRegistry.register("test", mock_provider)
        assert ModelRegistry.get_default_name() == "test"

    def test_register_multiple_providers(self):
        """register should allow multiple providers."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock1 = MagicMock()
        mock1.model_id = "model-1"
        mock2 = MagicMock()
        mock2.model_id = "model-2"

        ModelRegistry.register("provider1", mock1)
        ModelRegistry.register("provider2", mock2)

        assert "provider1" in ModelRegistry.list_providers()
        assert "provider2" in ModelRegistry.list_providers()

    def test_register_replaces_existing(self):
        """register should replace existing provider with same name."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock1 = MagicMock()
        mock1.model_id = "model-v1"
        mock2 = MagicMock()
        mock2.model_id = "model-v2"

        ModelRegistry.register("test", mock1)
        ModelRegistry.register("test", mock2)  # Replace

        # Should have model-v2
        provider = ModelRegistry.get("test")
        assert provider.model_id == "model-v2"


class TestModelRegistryUnregister:
    """Tests for ModelRegistry.unregister method."""

    def test_unregister_removes_provider(self):
        """unregister should remove provider from registry."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test"

        ModelRegistry.register("test", mock_provider)
        ModelRegistry.unregister("test")

        assert not ModelRegistry.has_provider("test")

    def test_unregister_not_found_raises(self):
        """unregister should raise KeyError for unknown provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        with pytest.raises(KeyError, match="Provider not found"):
            ModelRegistry.unregister("unknown")

    def test_unregister_updates_default(self):
        """unregister should update default if removed was default."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock1 = MagicMock()
        mock1.model_id = "model-1"
        mock2 = MagicMock()
        mock2.model_id = "model-2"

        ModelRegistry.register("provider1", mock1)  # Becomes default
        ModelRegistry.register("provider2", mock2)

        assert ModelRegistry.get_default_name() == "provider1"

        ModelRegistry.unregister("provider1")

        # Default should change to provider2
        assert ModelRegistry.get_default_name() == "provider2"


class TestModelRegistryGet:
    """Tests for ModelRegistry.get method."""

    def test_get_by_name(self):
        """get should return provider by name."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test-model"

        ModelRegistry.register("test", mock_provider)
        provider = ModelRegistry.get("test")

        assert provider is mock_provider

    def test_get_default_provider(self):
        """get with no args should return default provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test-model"

        ModelRegistry.register("test", mock_provider)
        provider = ModelRegistry.get()

        assert provider is mock_provider

    def test_get_not_found_raises(self):
        """get should raise KeyError for unknown provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        with pytest.raises(KeyError, match="Provider not found"):
            ModelRegistry.get("unknown")

    def test_get_no_providers_raises(self):
        """get should raise RuntimeError when no providers registered."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        with pytest.raises(RuntimeError, match="No providers registered"):
            ModelRegistry.get()


class TestModelRegistrySetDefault:
    """Tests for ModelRegistry.set_default method."""

    def test_set_default_changes_default(self):
        """set_default should change the default provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock1 = MagicMock()
        mock1.model_id = "model-1"
        mock2 = MagicMock()
        mock2.model_id = "model-2"

        ModelRegistry.register("provider1", mock1)
        ModelRegistry.register("provider2", mock2)

        ModelRegistry.set_default("provider2")

        assert ModelRegistry.get_default_name() == "provider2"

    def test_set_default_not_found_raises(self):
        """set_default should raise KeyError for unknown provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        with pytest.raises(KeyError, match="Provider not found"):
            ModelRegistry.set_default("unknown")


class TestModelRegistryListProviders:
    """Tests for ModelRegistry.list_providers method."""

    def test_list_providers_empty(self):
        """list_providers should return empty list when no providers."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()
        assert ModelRegistry.list_providers() == []

    def test_list_providers_returns_names(self):
        """list_providers should return provider names."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock1 = MagicMock()
        mock1.model_id = "m1"
        mock2 = MagicMock()
        mock2.model_id = "m2"

        ModelRegistry.register("alpha", mock1)
        ModelRegistry.register("beta", mock2)

        names = ModelRegistry.list_providers()
        assert "alpha" in names
        assert "beta" in names


class TestModelRegistryHasProvider:
    """Tests for ModelRegistry.has_provider method."""

    def test_has_provider_true(self):
        """has_provider should return True for registered provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test"

        ModelRegistry.register("test", mock_provider)
        assert ModelRegistry.has_provider("test") is True

    def test_has_provider_false(self):
        """has_provider should return False for unknown provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()
        assert ModelRegistry.has_provider("unknown") is False


class TestModelRegistryHealthCheckAll:
    """Tests for ModelRegistry.health_check_all method."""

    @pytest.mark.asyncio
    async def test_health_check_all_empty(self):
        """health_check_all should return empty dict when no providers."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()
        results = await ModelRegistry.health_check_all()
        assert results == {}

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        """health_check_all should return health status for each provider."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock1 = MagicMock()
        mock1.model_id = "m1"
        mock1.health_check = AsyncMock(return_value=True)

        mock2 = MagicMock()
        mock2.model_id = "m2"
        mock2.health_check = AsyncMock(return_value=True)

        ModelRegistry.register("healthy1", mock1)
        ModelRegistry.register("healthy2", mock2)

        results = await ModelRegistry.health_check_all()

        assert results["healthy1"] is True
        assert results["healthy2"] is True

    @pytest.mark.asyncio
    async def test_health_check_all_mixed(self):
        """health_check_all should handle mixed health states."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_healthy = MagicMock()
        mock_healthy.model_id = "healthy"
        mock_healthy.health_check = AsyncMock(return_value=True)

        mock_unhealthy = MagicMock()
        mock_unhealthy.model_id = "unhealthy"
        mock_unhealthy.health_check = AsyncMock(return_value=False)

        ModelRegistry.register("healthy", mock_healthy)
        ModelRegistry.register("unhealthy", mock_unhealthy)

        results = await ModelRegistry.health_check_all()

        assert results["healthy"] is True
        assert results["unhealthy"] is False

    @pytest.mark.asyncio
    async def test_health_check_all_exception(self):
        """health_check_all should handle exceptions."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "failing"
        mock_provider.health_check = AsyncMock(side_effect=Exception("Connection failed"))

        ModelRegistry.register("failing", mock_provider)

        results = await ModelRegistry.health_check_all()

        assert results["failing"] is False


class TestModelRegistryGetCapabilitiesSummary:
    """Tests for ModelRegistry.get_capabilities_summary method."""

    def test_get_capabilities_summary_empty(self):
        """get_capabilities_summary should return empty dict when no providers."""
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()
        summary = ModelRegistry.get_capabilities_summary()
        assert summary == {}

    def test_get_capabilities_summary_returns_data(self):
        """get_capabilities_summary should return capabilities for all providers."""
        from src.providers.base import ModelCapabilities
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()

        mock_provider = MagicMock()
        mock_provider.model_id = "test-model-v1"
        mock_provider.get_capabilities.return_value = ModelCapabilities(
            supports_vision=True,
            supports_streaming=True,
            max_context_tokens=100000,
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
        )

        ModelRegistry.register("test", mock_provider)
        summary = ModelRegistry.get_capabilities_summary()

        assert "test" in summary
        assert summary["test"]["model_id"] == "test-model-v1"
        assert summary["test"]["supports_vision"] is True
        assert summary["test"]["max_context_tokens"] == 100000
