"""Tests for src/providers/mock.py - Mock Model Providers."""

import pytest
from unittest.mock import patch


class TestMockProviderBasics:
    """Tests for MockProvider basic functionality."""

    def test_mock_provider_import(self):
        """MockProvider should be importable."""
        from src.providers.mock import MockProvider

        assert MockProvider is not None

    def test_mock_provider_init_defaults(self):
        """MockProvider should have sensible defaults."""
        from src.providers.mock import MockProvider

        provider = MockProvider()
        assert provider._quality_score == 0.85
        assert provider._latency_ms == 100.0
        assert provider._failure_rate == 0.0
        assert provider._call_count == 0

    def test_mock_provider_init_custom(self):
        """MockProvider should accept custom values."""
        from src.providers.mock import MockProvider

        provider = MockProvider(
            quality_score=0.95,
            latency_ms=500.0,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.05,
            model_id="custom-model",
            failure_rate=0.1,
        )
        assert provider._quality_score == 0.95
        assert provider._latency_ms == 500.0
        assert provider._model_id == "custom-model"
        assert provider._failure_rate == 0.1

    def test_mock_provider_name(self):
        """MockProvider.name should return 'mock'."""
        from src.providers.mock import MockProvider

        provider = MockProvider()
        assert provider.name == "mock"

    def test_mock_provider_model_id(self):
        """MockProvider.model_id should return model ID."""
        from src.providers.mock import MockProvider

        provider = MockProvider()
        assert provider.model_id == "mock-model-v1"

        provider2 = MockProvider(model_id="custom-v2")
        assert provider2.model_id == "custom-v2"


class TestMockProviderCapabilities:
    """Tests for MockProvider capabilities."""

    def test_get_capabilities_returns_object(self):
        """get_capabilities should return ModelCapabilities."""
        from src.providers.mock import MockProvider
        from src.providers.base import ModelCapabilities

        provider = MockProvider()
        caps = provider.get_capabilities()

        assert isinstance(caps, ModelCapabilities)

    def test_get_capabilities_includes_quality(self):
        """get_capabilities should include quality scores."""
        from src.providers.mock import MockProvider

        provider = MockProvider(quality_score=0.9)
        caps = provider.get_capabilities()

        assert caps.reasoning_quality == 0.9
        assert caps.coding_quality == 0.9
        assert caps.instruction_following == 0.9

    def test_get_capabilities_includes_costs(self):
        """get_capabilities should include cost info."""
        from src.providers.mock import MockProvider

        provider = MockProvider(
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.05,
        )
        caps = provider.get_capabilities()

        assert caps.cost_per_1k_input_tokens == 0.01
        assert caps.cost_per_1k_output_tokens == 0.05

    def test_get_capabilities_supports_all_features(self):
        """get_capabilities should support vision and function calling."""
        from src.providers.mock import MockProvider

        provider = MockProvider()
        caps = provider.get_capabilities()

        assert caps.supports_vision is True
        assert caps.supports_function_calling is True
        assert caps.supports_streaming is True


class TestMockProviderComplete:
    """Tests for MockProvider.complete method."""

    @pytest.mark.asyncio
    async def test_complete_returns_response(self):
        """complete should return ModelResponse."""
        from src.providers.mock import MockProvider
        from src.providers.base import ModelResponse

        provider = MockProvider(latency_ms=1)  # Fast for tests
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert isinstance(response, ModelResponse)
        assert response.model == "mock-model-v1"
        assert response.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_complete_increments_call_count(self):
        """complete should increment call count."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        assert provider._call_count == 0

        await provider.complete(messages=[{"role": "user", "content": "Test"}])
        assert provider._call_count == 1

        await provider.complete(messages=[{"role": "user", "content": "Test"}])
        assert provider._call_count == 2

    @pytest.mark.asyncio
    async def test_complete_includes_metadata(self):
        """complete should include metadata in response."""
        from src.providers.mock import MockProvider

        provider = MockProvider(quality_score=0.9, latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Test"}]
        )

        assert response.metadata["mock"] is True
        assert response.metadata["quality_score"] == 0.9
        assert response.metadata["call_count"] == 1

    @pytest.mark.asyncio
    async def test_complete_calculates_tokens(self):
        """complete should estimate token counts."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello world"}]
        )

        assert response.input_tokens > 0
        assert response.output_tokens > 0

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self):
        """complete should handle system prompt."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a helpful assistant.",
        )

        # System prompt should be included in input token calculation
        assert response.input_tokens > 0

    @pytest.mark.asyncio
    async def test_complete_failure_rate(self):
        """complete should fail based on failure_rate."""
        from src.providers.mock import MockProvider

        provider = MockProvider(failure_rate=1.0)  # Always fail

        with pytest.raises(RuntimeError, match="Simulated API failure"):
            await provider.complete(messages=[{"role": "user", "content": "Test"}])


class TestMockProviderStream:
    """Tests for MockProvider.stream method."""

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        """stream should yield string tokens."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        tokens = []

        async for token in provider.stream(
            messages=[{"role": "user", "content": "Hello"}]
        ):
            tokens.append(token)

        assert len(tokens) > 0
        # All tokens should be strings
        for token in tokens:
            assert isinstance(token, str)

    @pytest.mark.asyncio
    async def test_stream_complete_content(self):
        """stream should yield complete response when joined."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        tokens = []

        async for token in provider.stream(
            messages=[{"role": "user", "content": "Hello"}]
        ):
            tokens.append(token)

        full_response = "".join(tokens)
        assert len(full_response) > 0


class TestMockProviderResponses:
    """Tests for MockProvider response generation."""

    @pytest.mark.asyncio
    async def test_code_response(self):
        """should generate code-related response for code queries."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Write a Python function"}]
        )

        assert "code" in response.content.lower() or "implementation" in response.content.lower()

    @pytest.mark.asyncio
    async def test_explain_response(self):
        """should generate explanation for explain queries."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Explain how this works"}]
        )

        assert "explanation" in response.content.lower() or "concept" in response.content.lower()

    @pytest.mark.asyncio
    async def test_analyze_response(self):
        """should generate analysis for analyze queries."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Analyze the data"}]
        )

        assert "analysis" in response.content.lower() or "pattern" in response.content.lower()

    @pytest.mark.asyncio
    async def test_summarize_response(self):
        """should generate summary for summarize queries."""
        from src.providers.mock import MockProvider

        provider = MockProvider(latency_ms=1)
        response = await provider.complete(
            messages=[{"role": "user", "content": "Summarize the document"}]
        )

        assert "summary" in response.content.lower() or "point" in response.content.lower()


class TestMockProviderHealthCheck:
    """Tests for MockProvider.health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """health_check should return True when healthy."""
        from src.providers.mock import MockProvider

        provider = MockProvider(failure_rate=0.0)
        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_always_failing(self):
        """health_check should return False when failure_rate is 1.0."""
        from src.providers.mock import MockProvider

        provider = MockProvider(failure_rate=1.0)
        result = await provider.health_check()
        assert result is False


class TestMockOpusProvider:
    """Tests for MockOpusProvider."""

    def test_mock_opus_import(self):
        """MockOpusProvider should be importable."""
        from src.providers.mock import MockOpusProvider

        assert MockOpusProvider is not None

    def test_mock_opus_characteristics(self):
        """MockOpusProvider should have Opus-like characteristics."""
        from src.providers.mock import MockOpusProvider

        provider = MockOpusProvider()
        assert provider.name == "mock-opus"
        assert provider.model_id == "mock-opus-v1"
        assert provider._quality_score == 0.95  # High quality
        assert provider._latency_ms == 800.0  # Higher latency
        assert provider._cost_per_1k_output == 0.075  # Higher cost


class TestMockSonnetProvider:
    """Tests for MockSonnetProvider."""

    def test_mock_sonnet_import(self):
        """MockSonnetProvider should be importable."""
        from src.providers.mock import MockSonnetProvider

        assert MockSonnetProvider is not None

    def test_mock_sonnet_characteristics(self):
        """MockSonnetProvider should have Sonnet-like characteristics."""
        from src.providers.mock import MockSonnetProvider

        provider = MockSonnetProvider()
        assert provider.name == "mock-sonnet"
        assert provider.model_id == "mock-sonnet-v1"
        assert provider._quality_score == 0.85  # Balanced quality
        assert provider._latency_ms == 300.0  # Moderate latency
        assert provider._cost_per_1k_output == 0.015  # Moderate cost


class TestMockHaikuProvider:
    """Tests for MockHaikuProvider."""

    def test_mock_haiku_import(self):
        """MockHaikuProvider should be importable."""
        from src.providers.mock import MockHaikuProvider

        assert MockHaikuProvider is not None

    def test_mock_haiku_characteristics(self):
        """MockHaikuProvider should have Haiku-like characteristics."""
        from src.providers.mock import MockHaikuProvider

        provider = MockHaikuProvider()
        assert provider.name == "mock-haiku"
        assert provider.model_id == "mock-haiku-v1"
        assert provider._quality_score == 0.75  # Lower quality
        assert provider._latency_ms == 100.0  # Fastest
        assert provider._cost_per_1k_output == 0.00125  # Cheapest


class TestRegisterMockProviders:
    """Tests for register_mock_providers function."""

    def test_register_mock_providers_import(self):
        """register_mock_providers should be importable."""
        from src.providers.mock import register_mock_providers

        assert register_mock_providers is not None

    def test_register_mock_providers_adds_all(self):
        """register_mock_providers should add all mock providers."""
        from src.providers.mock import register_mock_providers
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()
        register_mock_providers()

        providers = ModelRegistry.list_providers()
        assert "mock" in providers
        assert "mock-opus" in providers
        assert "mock-sonnet" in providers
        assert "mock-haiku" in providers

    def test_register_mock_providers_default(self):
        """register_mock_providers should set mock as default."""
        from src.providers.mock import register_mock_providers
        from src.providers.registry import ModelRegistry

        ModelRegistry.clear()
        register_mock_providers()

        # First registered should be default
        assert ModelRegistry.get_default_name() == "mock"
