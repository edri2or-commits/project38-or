"""
Mock Model Provider for Testing.

Provides a deterministic mock provider for testing experiments
without making actual API calls. Returns configurable responses.

Usage:
    from src.providers.mock import MockProvider
    from src.providers import ModelRegistry

    # Create and register mock provider
    mock = MockProvider(quality_score=0.85)
    ModelRegistry.register("mock", mock)

    # Use in experiments
    provider = ModelRegistry.get("mock")
    response = await provider.complete(messages)
"""

import random
import time
from collections.abc import AsyncIterator
from typing import Any

from src.providers.base import ModelCapabilities, ModelProvider, ModelResponse


class MockProvider(ModelProvider):
    """Mock provider for testing without real API calls.

    Simulates responses with configurable latency, quality, and cost.
    Useful for:
    - Testing experiment frameworks
    - Validating evaluation harness
    - CI/CD pipelines without API costs
    """

    def __init__(
        self,
        quality_score: float = 0.85,
        latency_ms: float = 100.0,
        cost_per_1k_input: float = 0.003,
        cost_per_1k_output: float = 0.015,
        model_id: str = "mock-model-v1",
        failure_rate: float = 0.0,
    ):
        """Initialize mock provider.

        Args:
            quality_score: Simulated quality score (0-1)
            latency_ms: Simulated response latency
            cost_per_1k_input: Input token cost per 1000
            cost_per_1k_output: Output token cost per 1000
            model_id: Model identifier
            failure_rate: Probability of simulated failure (0-1)
        """
        self._quality_score = quality_score
        self._latency_ms = latency_ms
        self._cost_per_1k_input = cost_per_1k_input
        self._cost_per_1k_output = cost_per_1k_output
        self._model_id = model_id
        self._failure_rate = failure_rate
        self._call_count = 0

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return "mock"

    @property
    def model_id(self) -> str:
        """The specific model being used."""
        return self._model_id

    def get_capabilities(self) -> ModelCapabilities:
        """Return the capabilities of this model."""
        return ModelCapabilities(
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            max_context_tokens=100000,
            max_output_tokens=4096,
            typical_latency_ms=int(self._latency_ms),
            cost_per_1k_input_tokens=self._cost_per_1k_input,
            cost_per_1k_output_tokens=self._cost_per_1k_output,
            reasoning_quality=self._quality_score,
            coding_quality=self._quality_score,
            instruction_following=self._quality_score,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate a mock completion."""
        self._call_count += 1

        # Simulate failure
        if self._failure_rate > 0 and random.random() < self._failure_rate:
            raise RuntimeError("Simulated API failure")

        # Simulate latency with some variance
        actual_latency = self._latency_ms * (0.8 + random.random() * 0.4)
        time.sleep(actual_latency / 1000)

        # Calculate token counts from messages
        input_text = " ".join(
            msg.get("content", "") for msg in messages if msg.get("content")
        )
        if system:
            input_text = system + " " + input_text
        input_tokens = len(input_text.split()) * 1.3  # Rough estimate

        # Generate mock response
        content = self._generate_mock_response(messages)
        output_tokens = len(content.split()) * 1.3

        return ModelResponse(
            content=content,
            model=self._model_id,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            latency_ms=actual_latency,
            stop_reason="end_turn",
            metadata={
                "mock": True,
                "quality_score": self._quality_score,
                "call_count": self._call_count,
            },
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a mock completion token by token."""
        response = await self.complete(messages, system, max_tokens, temperature)
        words = response.content.split()
        for word in words:
            yield word + " "
            time.sleep(0.01)  # Simulate token streaming

    def _generate_mock_response(self, messages: list[dict[str, str]]) -> str:
        """Generate a mock response based on messages."""
        last_message = messages[-1].get("content", "") if messages else ""

        # Generate contextual mock responses
        if "code" in last_message.lower() or "function" in last_message.lower():
            return "Here is a mock code implementation that demonstrates the requested functionality with proper error handling and documentation."
        elif "explain" in last_message.lower():
            return "This is a mock explanation that covers the key concepts with examples and practical applications for better understanding."
        elif "analyze" in last_message.lower():
            return "Analysis shows that the data exhibits expected patterns with confidence levels meeting the threshold criteria."
        elif "summarize" in last_message.lower():
            return "Summary: The key points are organized into three main categories with supporting evidence and actionable recommendations."
        else:
            return "Mock response generated successfully. This simulates a helpful and accurate response to the user query."

    async def health_check(self) -> bool:
        """Check if the mock provider is healthy."""
        return self._failure_rate < 1.0


class MockOpusProvider(MockProvider):
    """Mock provider simulating Claude Opus characteristics.

    Higher quality, higher latency, higher cost.
    """

    def __init__(self):
        """Initialize mock Opus provider."""
        super().__init__(
            quality_score=0.95,
            latency_ms=800.0,
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.075,
            model_id="mock-opus-v1",
        )

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return "mock-opus"


class MockSonnetProvider(MockProvider):
    """Mock provider simulating Claude Sonnet characteristics.

    Balanced quality, latency, cost.
    """

    def __init__(self):
        """Initialize mock Sonnet provider."""
        super().__init__(
            quality_score=0.85,
            latency_ms=300.0,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            model_id="mock-sonnet-v1",
        )

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return "mock-sonnet"


class MockHaikuProvider(MockProvider):
    """Mock provider simulating Claude Haiku characteristics.

    Lower quality, fastest, cheapest.
    """

    def __init__(self):
        """Initialize mock Haiku provider."""
        super().__init__(
            quality_score=0.75,
            latency_ms=100.0,
            cost_per_1k_input=0.00025,
            cost_per_1k_output=0.00125,
            model_id="mock-haiku-v1",
        )

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return "mock-haiku"


def register_mock_providers():
    """Register all mock providers with the registry.

    Call this before running experiments in mock mode.
    """
    from src.providers.registry import ModelRegistry

    ModelRegistry.register("mock", MockProvider())
    ModelRegistry.register("mock-opus", MockOpusProvider())
    ModelRegistry.register("mock-sonnet", MockSonnetProvider())
    ModelRegistry.register("mock-haiku", MockHaikuProvider())
