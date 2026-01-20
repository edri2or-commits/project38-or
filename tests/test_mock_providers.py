"""Tests for Mock Providers.

Tests the MockProvider and MockOpusProvider implementations
to ensure they work correctly with the evaluation framework.

Architecture Decision: ADR-009
"""

import pytest

from src.providers import (
    MockOpusProvider,
    MockProvider,
    ModelRegistry,
    register_mock_providers,
)


class TestMockProvider:
    """Tests for MockProvider class."""

    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()

    def test_provider_name(self):
        """Test provider name property."""
        provider = MockProvider()
        assert provider.name == "mock"

    def test_provider_model_id(self):
        """Test provider model_id property."""
        provider = MockProvider()
        assert provider.model_id == "mock-v1"

    def test_custom_name(self):
        """Test custom provider name."""
        provider = MockProvider(name="custom-mock", model_id="custom-v1")
        assert provider.name == "custom-mock"
        assert provider.model_id == "custom-v1"

    def test_capabilities(self):
        """Test provider capabilities."""
        provider = MockProvider()
        caps = provider.get_capabilities()

        assert caps.supports_streaming is True
        assert caps.supports_function_calling is True
        assert caps.max_context_tokens == 100000
        assert caps.cost_per_1k_input_tokens == 0.001
        assert caps.cost_per_1k_output_tokens == 0.002

    @pytest.mark.asyncio
    async def test_complete_basic(self):
        """Test basic completion."""
        provider = MockProvider()
        response = await provider.complete(messages=[{"role": "user", "content": "Hello"}])

        assert response.content is not None
        assert len(response.content) > 0
        assert response.model == "mock-v1"
        assert response.input_tokens > 0
        assert response.output_tokens > 0

    @pytest.mark.asyncio
    async def test_complete_hello(self):
        """Test hello response contains expected keywords."""
        provider = MockProvider()
        response = await provider.complete(messages=[{"role": "user", "content": "Say hello"}])

        content_lower = response.content.lower()
        assert "hello" in content_lower
        assert "assistant" in content_lower or "help" in content_lower

    @pytest.mark.asyncio
    async def test_complete_prime(self):
        """Test prime number response contains code."""
        provider = MockProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Write a function to check if a number is prime"}]
        )

        assert "def" in response.content
        assert "prime" in response.content.lower()
        assert "return" in response.content

    @pytest.mark.asyncio
    async def test_complete_math_multiply(self):
        """Test math multiplication response."""
        provider = MockProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "What is 15 multiplied by 7?"}]
        )

        assert "105" in response.content

    @pytest.mark.asyncio
    async def test_complete_math_divide(self):
        """Test math division response."""
        provider = MockProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Calculate 128 divided by 8"}]
        )

        assert "16" in response.content

    @pytest.mark.asyncio
    async def test_complete_json(self):
        """Test JSON response format."""
        provider = MockProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Return a JSON object with name, age, city"}]
        )

        assert "name" in response.content
        assert "age" in response.content
        assert "city" in response.content

    @pytest.mark.asyncio
    async def test_complete_api_explanation(self):
        """Test API explanation response."""
        provider = MockProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Explain what an API is"}]
        )

        content_lower = response.content.lower()
        assert "interface" in content_lower or "application" in content_lower

    @pytest.mark.asyncio
    async def test_latency_simulation(self):
        """Test latency simulation works."""
        provider = MockProvider(latency_ms=100.0)
        response = await provider.complete(messages=[{"role": "user", "content": "Test"}])

        # Latency should be approximately 100ms (with some tolerance)
        assert response.latency_ms >= 90
        assert response.latency_ms < 200

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check returns True."""
        provider = MockProvider()
        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_deterministic_responses(self):
        """Test that same query returns same response."""
        provider = MockProvider()

        response1 = await provider.complete(
            messages=[{"role": "user", "content": "What is an API?"}]
        )
        response2 = await provider.complete(
            messages=[{"role": "user", "content": "What is an API?"}]
        )

        assert response1.content == response2.content

    @pytest.mark.asyncio
    async def test_unknown_query_hash_response(self):
        """Test unknown query returns hash-based response."""
        provider = MockProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "xyz123unique456query789"}]
        )

        assert "Mock response #" in response.content


class TestMockOpusProvider:
    """Tests for MockOpusProvider class."""

    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()

    def test_provider_name(self):
        """Test Opus provider name."""
        provider = MockOpusProvider()
        assert provider.name == "mock-opus"

    def test_provider_model_id(self):
        """Test Opus provider model_id."""
        provider = MockOpusProvider()
        assert provider.model_id == "mock-opus-v1"

    def test_capabilities_higher_cost(self):
        """Test Opus has higher cost than base mock."""
        base = MockProvider()
        opus = MockOpusProvider()

        base_caps = base.get_capabilities()
        opus_caps = opus.get_capabilities()

        # Opus should be 5x more expensive
        assert opus_caps.cost_per_1k_input_tokens > base_caps.cost_per_1k_input_tokens
        assert opus_caps.cost_per_1k_output_tokens > base_caps.cost_per_1k_output_tokens
        assert opus_caps.cost_per_1k_input_tokens == 0.015
        assert opus_caps.cost_per_1k_output_tokens == 0.075

    def test_capabilities_higher_quality(self):
        """Test Opus has higher quality ratings."""
        opus = MockOpusProvider()
        caps = opus.get_capabilities()

        assert caps.reasoning_quality >= 0.98
        assert caps.coding_quality >= 0.97
        assert caps.instruction_following >= 0.98

    def test_capabilities_vision_support(self):
        """Test Opus supports vision."""
        opus = MockOpusProvider()
        caps = opus.get_capabilities()

        assert caps.supports_vision is True

    @pytest.mark.asyncio
    async def test_higher_latency(self):
        """Test Opus has higher latency than base mock."""
        base = MockProvider()
        opus = MockOpusProvider()

        base_response = await base.complete(messages=[{"role": "user", "content": "Test"}])
        opus_response = await opus.complete(messages=[{"role": "user", "content": "Test"}])

        # Opus should be slower (150ms vs 50ms)
        assert opus_response.latency_ms > base_response.latency_ms

    @pytest.mark.asyncio
    async def test_machine_learning_response(self):
        """Test machine learning response contains expected keywords."""
        provider = MockOpusProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Explain machine learning"}]
        )

        content_lower = response.content.lower()
        assert "data" in content_lower
        assert "algorithm" in content_lower or "pattern" in content_lower

    @pytest.mark.asyncio
    async def test_version_control_response(self):
        """Test version control response."""
        provider = MockOpusProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Summarize version control"}]
        )

        content_lower = response.content.lower()
        assert "version" in content_lower
        assert "code" in content_lower or "changes" in content_lower

    @pytest.mark.asyncio
    async def test_fallback_to_base(self):
        """Test Opus falls back to base for unknown patterns."""
        provider = MockOpusProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "xyz123uniquequery456"}]
        )

        # Should get hash-based fallback response
        assert "Mock response #" in response.content


class TestRegisterMockProviders:
    """Tests for register_mock_providers function."""

    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()

    def test_registers_mock(self):
        """Test mock provider is registered."""
        register_mock_providers()
        assert ModelRegistry.has_provider("mock")

    def test_registers_mock_opus(self):
        """Test mock-opus provider is registered."""
        register_mock_providers()
        assert ModelRegistry.has_provider("mock-opus")

    def test_both_providers_registered(self):
        """Test both providers are registered."""
        register_mock_providers()
        providers = ModelRegistry.list_providers()

        assert "mock" in providers
        assert "mock-opus" in providers

    def test_get_registered_mock(self):
        """Test getting registered mock provider."""
        register_mock_providers()
        provider = ModelRegistry.get("mock")

        assert provider is not None
        assert provider.name == "mock"

    def test_get_registered_opus(self):
        """Test getting registered opus provider."""
        register_mock_providers()
        provider = ModelRegistry.get("mock-opus")

        assert provider is not None
        assert provider.name == "mock-opus"

    def test_default_provider_set(self):
        """Test first registered provider becomes default."""
        register_mock_providers()
        default_name = ModelRegistry.get_default_name()

        # First registered should be default
        assert default_name == "mock"

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Test health check for all registered providers."""
        register_mock_providers()
        results = await ModelRegistry.health_check_all()

        assert results["mock"] is True
        assert results["mock-opus"] is True


class TestIntegrationWithEvaluationHarness:
    """Integration tests with evaluation harness."""

    def setup_method(self):
        """Clear registry before each test."""
        ModelRegistry.clear()

    @pytest.mark.asyncio
    async def test_golden_set_quality(self):
        """Test mock provider achieves reasonable quality on golden set patterns."""
        register_mock_providers()
        provider = ModelRegistry.get("mock")

        # Test queries from golden set
        test_queries = [
            ("Say hello and introduce yourself briefly.", ["hello", "assistant"]),
            ("What is 15 multiplied by 7?", ["105"]),
            ("Write a Python function to check if prime", ["def", "prime"]),
            ("Explain what an API is", ["interface", "application"]),
        ]

        for query, expected_keywords in test_queries:
            response = await provider.complete(messages=[{"role": "user", "content": query}])
            content_lower = response.content.lower()

            # At least one expected keyword should be present
            found = any(kw.lower() in content_lower for kw in expected_keywords)
            assert found, f"Query '{query}' missing expected keywords {expected_keywords}"

    @pytest.mark.asyncio
    async def test_cost_calculation(self):
        """Test cost is calculated correctly."""
        register_mock_providers()

        mock = ModelRegistry.get("mock")
        opus = ModelRegistry.get("mock-opus")

        mock_caps = mock.get_capabilities()
        opus_caps = opus.get_capabilities()

        # Simulate same token counts
        input_tokens = 100
        output_tokens = 200

        mock_cost = (
            input_tokens * mock_caps.cost_per_1k_input_tokens / 1000
            + output_tokens * mock_caps.cost_per_1k_output_tokens / 1000
        )
        opus_cost = (
            input_tokens * opus_caps.cost_per_1k_input_tokens / 1000
            + output_tokens * opus_caps.cost_per_1k_output_tokens / 1000
        )

        # Opus should be significantly more expensive
        # Input: 15x more (0.015 vs 0.001)
        # Output: 37.5x more (0.075 vs 0.002)
        # With 100 input, 200 output: weighted average is ~25x
        assert opus_cost > mock_cost * 10  # At least 10x more
        assert opus_cost < mock_cost * 50  # But not more than 50x
