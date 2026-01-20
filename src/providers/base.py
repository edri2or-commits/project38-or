"""
Base classes for Model Providers.

This module defines the stable interface that all model providers must implement.
The interface is designed to be:
- Minimal: Only essential methods
- Stable: Changes require ADR approval
- Testable: Easy to mock for testing

Architecture Decision: ADR-009
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator


@dataclass
class ModelCapabilities:
    """Describes what a model can do.

    Used by orchestration layer to select appropriate model for task.
    """

    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True
    max_context_tokens: int = 100000
    max_output_tokens: int = 4096

    # Performance characteristics
    typical_latency_ms: int = 1000  # Typical response time
    cost_per_1k_input_tokens: float = 0.003  # USD
    cost_per_1k_output_tokens: float = 0.015  # USD

    # Quality indicators (0-1 scale, higher is better)
    reasoning_quality: float = 0.9
    coding_quality: float = 0.9
    instruction_following: float = 0.9


@dataclass
class ModelResponse:
    """Standardized response from any model provider.

    All providers must return this format, regardless of underlying API.
    """

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Optional metadata from provider
    stop_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimated cost in USD (requires capabilities to be accurate)."""
        # Default pricing - override in provider for accuracy
        return (self.input_tokens * 0.003 + self.output_tokens * 0.015) / 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "stop_reason": self.stop_reason,
            "metadata": self.metadata,
        }


class ModelProvider(ABC):
    """Abstract base class for model providers.

    All model providers must implement this interface.
    This ensures we can swap providers without changing application code.

    Example:
        class ClaudeProvider(ModelProvider):
            async def complete(self, messages, **kwargs):
                # Call Claude API
                return ModelResponse(...)

        # Register provider
        ModelRegistry.register("claude", ClaudeProvider())

        # Use provider
        provider = ModelRegistry.get("claude")
        response = await provider.complete(messages)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider."""
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """The specific model being used (e.g., 'claude-sonnet-4-20250514')."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ModelCapabilities:
        """Return the capabilities of this model.

        Used by orchestration to select appropriate model for task.
        """
        pass

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate a completion for the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                     Roles: 'user', 'assistant', 'system'
            system: Optional system prompt (some providers handle differently)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            **kwargs: Provider-specific parameters

        Returns:
            ModelResponse with the completion

        Raises:
            ProviderError: If the API call fails
            RateLimitError: If rate limited
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion token by token.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            **kwargs: Provider-specific parameters

        Yields:
            String tokens as they are generated

        Raises:
            ProviderError: If the API call fails
        """
        pass

    async def health_check(self) -> bool:
        """Check if the provider is healthy and responsive.

        Returns:
            True if provider is working, False otherwise
        """
        try:
            response = await self.complete(
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=10,
            )
            return len(response.content) > 0
        except Exception:
            return False


# Custom exceptions for providers
class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class RateLimitError(ProviderError):
    """Raised when rate limited by provider."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    """Raised when authentication fails."""

    pass


class ModelNotFoundError(ProviderError):
    """Raised when requested model doesn't exist."""

    pass
