"""Tests for src/providers/base.py - Base classes for Model Providers."""

from collections.abc import AsyncIterator
from typing import Any

import pytest


class TestModelCapabilities:
    """Tests for ModelCapabilities dataclass."""

    def test_model_capabilities_import(self):
        """ModelCapabilities should be importable."""
        from src.providers.base import ModelCapabilities

        assert ModelCapabilities is not None

    def test_model_capabilities_defaults(self):
        """ModelCapabilities should have sensible defaults."""
        from src.providers.base import ModelCapabilities

        caps = ModelCapabilities()
        assert caps.supports_vision is False
        assert caps.supports_function_calling is False
        assert caps.supports_streaming is True
        assert caps.max_context_tokens == 100000
        assert caps.max_output_tokens == 4096
        assert caps.typical_latency_ms == 1000
        assert caps.cost_per_1k_input_tokens == 0.003
        assert caps.cost_per_1k_output_tokens == 0.015
        assert caps.reasoning_quality == 0.9
        assert caps.coding_quality == 0.9
        assert caps.instruction_following == 0.9

    def test_model_capabilities_custom_values(self):
        """ModelCapabilities should accept custom values."""
        from src.providers.base import ModelCapabilities

        caps = ModelCapabilities(
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=False,
            max_context_tokens=200000,
            max_output_tokens=8192,
            typical_latency_ms=500,
            cost_per_1k_input_tokens=0.015,
            cost_per_1k_output_tokens=0.075,
            reasoning_quality=0.95,
            coding_quality=0.98,
            instruction_following=0.92,
        )
        assert caps.supports_vision is True
        assert caps.supports_function_calling is True
        assert caps.max_context_tokens == 200000
        assert caps.cost_per_1k_output_tokens == 0.075


class TestModelResponse:
    """Tests for ModelResponse dataclass."""

    def test_model_response_import(self):
        """ModelResponse should be importable."""
        from src.providers.base import ModelResponse

        assert ModelResponse is not None

    def test_model_response_required_fields(self):
        """ModelResponse should require specific fields."""
        from src.providers.base import ModelResponse

        response = ModelResponse(
            content="Hello, world!",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=150.0,
        )
        assert response.content == "Hello, world!"
        assert response.model == "test-model"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.latency_ms == 150.0

    def test_model_response_defaults(self):
        """ModelResponse should have sensible defaults."""
        from src.providers.base import ModelResponse

        response = ModelResponse(
            content="Test",
            model="model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=100.0,
        )
        assert response.stop_reason is None
        assert response.metadata == {}
        # timestamp should be auto-generated
        assert response.timestamp is not None

    def test_model_response_total_tokens(self):
        """ModelResponse.total_tokens should sum input + output."""
        from src.providers.base import ModelResponse

        response = ModelResponse(
            content="Test",
            model="model",
            input_tokens=100,
            output_tokens=50,
            latency_ms=100.0,
        )
        assert response.total_tokens == 150

    def test_model_response_estimated_cost(self):
        """ModelResponse.estimated_cost should calculate cost."""
        from src.providers.base import ModelResponse

        response = ModelResponse(
            content="Test",
            model="model",
            input_tokens=1000,
            output_tokens=1000,
            latency_ms=100.0,
        )
        # Default: input $0.003/1K, output $0.015/1K
        expected = (1000 * 0.003 + 1000 * 0.015) / 1000
        assert response.estimated_cost == expected

    def test_model_response_to_dict(self):
        """ModelResponse.to_dict should return proper dictionary."""
        from src.providers.base import ModelResponse

        response = ModelResponse(
            content="Test content",
            model="test-model-v1",
            input_tokens=50,
            output_tokens=25,
            latency_ms=200.5,
            stop_reason="end_turn",
            metadata={"custom": "data"},
        )
        d = response.to_dict()
        assert d["content"] == "Test content"
        assert d["model"] == "test-model-v1"
        assert d["input_tokens"] == 50
        assert d["output_tokens"] == 25
        assert d["total_tokens"] == 75
        assert d["latency_ms"] == 200.5
        assert d["stop_reason"] == "end_turn"
        assert d["metadata"] == {"custom": "data"}
        assert "timestamp" in d

    def test_model_response_custom_metadata(self):
        """ModelResponse should store custom metadata."""
        from src.providers.base import ModelResponse

        response = ModelResponse(
            content="Test",
            model="model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=100.0,
            metadata={"cache_hit": True, "region": "us-west"},
        )
        assert response.metadata["cache_hit"] is True
        assert response.metadata["region"] == "us-west"


class TestModelProvider:
    """Tests for ModelProvider abstract base class."""

    def test_model_provider_import(self):
        """ModelProvider should be importable."""
        from src.providers.base import ModelProvider

        assert ModelProvider is not None

    def test_model_provider_is_abstract(self):
        """ModelProvider should be abstract."""
        from abc import ABC

        from src.providers.base import ModelProvider

        assert issubclass(ModelProvider, ABC)

    def test_model_provider_abstract_methods(self):
        """ModelProvider should have abstract methods."""
        from src.providers.base import ModelProvider

        # These should be abstract
        abstract_methods = ModelProvider.__abstractmethods__
        assert "name" in abstract_methods or hasattr(ModelProvider, "name")
        assert "model_id" in abstract_methods or hasattr(ModelProvider, "model_id")
        assert "get_capabilities" in abstract_methods
        assert "complete" in abstract_methods
        assert "stream" in abstract_methods

    def test_model_provider_cannot_instantiate(self):
        """ModelProvider should not be directly instantiable."""
        from src.providers.base import ModelProvider

        with pytest.raises(TypeError):
            ModelProvider()

    def test_model_provider_health_check_method(self):
        """ModelProvider should have health_check method."""
        from src.providers.base import ModelProvider

        assert hasattr(ModelProvider, "health_check")

    def test_concrete_provider_implementation(self):
        """Concrete provider implementation should work."""
        from src.providers.base import ModelCapabilities, ModelProvider, ModelResponse

        class TestProvider(ModelProvider):
            @property
            def name(self) -> str:
                return "test"

            @property
            def model_id(self) -> str:
                return "test-model-v1"

            def get_capabilities(self) -> ModelCapabilities:
                return ModelCapabilities()

            async def complete(
                self,
                messages: list[dict[str, str]],
                system: str | None = None,
                max_tokens: int = 4096,
                temperature: float = 0.7,
                **kwargs: Any,
            ) -> ModelResponse:
                return ModelResponse(
                    content="Test response",
                    model=self.model_id,
                    input_tokens=10,
                    output_tokens=5,
                    latency_ms=100.0,
                )

            async def stream(
                self,
                messages: list[dict[str, str]],
                system: str | None = None,
                max_tokens: int = 4096,
                temperature: float = 0.7,
                **kwargs: Any,
            ) -> AsyncIterator[str]:
                yield "Test "
                yield "stream"

        provider = TestProvider()
        assert provider.name == "test"
        assert provider.model_id == "test-model-v1"


class TestProviderExceptions:
    """Tests for provider exception classes."""

    def test_provider_error_import(self):
        """ProviderError should be importable."""
        from src.providers.base import ProviderError

        assert ProviderError is not None

    def test_provider_error_is_exception(self):
        """ProviderError should be an Exception subclass."""
        from src.providers.base import ProviderError

        assert issubclass(ProviderError, Exception)

    def test_provider_error_message(self):
        """ProviderError should store message."""
        from src.providers.base import ProviderError

        error = ProviderError("API call failed")
        assert str(error) == "API call failed"

    def test_rate_limit_error_import(self):
        """RateLimitError should be importable."""
        from src.providers.base import RateLimitError

        assert RateLimitError is not None

    def test_rate_limit_error_is_provider_error(self):
        """RateLimitError should be a ProviderError subclass."""
        from src.providers.base import ProviderError, RateLimitError

        assert issubclass(RateLimitError, ProviderError)

    def test_rate_limit_error_retry_after(self):
        """RateLimitError should store retry_after."""
        from src.providers.base import RateLimitError

        error = RateLimitError("Rate limited", retry_after=60.0)
        assert str(error) == "Rate limited"
        assert error.retry_after == 60.0

    def test_rate_limit_error_no_retry_after(self):
        """RateLimitError should work without retry_after."""
        from src.providers.base import RateLimitError

        error = RateLimitError("Rate limited")
        assert error.retry_after is None

    def test_authentication_error_import(self):
        """AuthenticationError should be importable."""
        from src.providers.base import AuthenticationError

        assert AuthenticationError is not None

    def test_authentication_error_is_provider_error(self):
        """AuthenticationError should be a ProviderError subclass."""
        from src.providers.base import AuthenticationError, ProviderError

        assert issubclass(AuthenticationError, ProviderError)

    def test_authentication_error_message(self):
        """AuthenticationError should store message."""
        from src.providers.base import AuthenticationError

        error = AuthenticationError("Invalid API key")
        assert str(error) == "Invalid API key"

    def test_model_not_found_error_import(self):
        """ModelNotFoundError should be importable."""
        from src.providers.base import ModelNotFoundError

        assert ModelNotFoundError is not None

    def test_model_not_found_error_is_provider_error(self):
        """ModelNotFoundError should be a ProviderError subclass."""
        from src.providers.base import ModelNotFoundError, ProviderError

        assert issubclass(ModelNotFoundError, ProviderError)

    def test_model_not_found_error_message(self):
        """ModelNotFoundError should store message."""
        from src.providers.base import ModelNotFoundError

        error = ModelNotFoundError("Model 'xyz' not found")
        assert str(error) == "Model 'xyz' not found"
