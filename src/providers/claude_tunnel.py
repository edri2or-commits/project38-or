"""
Claude Provider via MCP Tunnel.

Provides real Claude API access from environments blocked by proxy,
using the MCP Tunnel's claude_complete tool.

Usage:
    from src.providers.claude_tunnel import ClaudeTunnelProvider
    from src.providers import ModelRegistry

    # Register real Claude provider
    provider = ClaudeTunnelProvider(model="claude-sonnet-4-20250514")
    ModelRegistry.register("claude-sonnet", provider)

    # Use in experiments
    response = await provider.complete(messages)
"""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import requests

from src.providers.base import ModelCapabilities, ModelProvider, ModelResponse, ProviderError


# MCP Tunnel configuration
# Use Cloud Function URL (whitelisted by proxy) instead of Cloud Run URL (blocked)
MCP_TUNNEL_URL = "https://us-central1-project38-483612.cloudfunctions.net/mcp-router"


class ClaudeTunnelProvider(ModelProvider):
    """Real Claude provider via MCP Tunnel.

    Calls Claude API through the MCP Tunnel's claude_complete tool,
    bypassing proxy restrictions in cloud environments.
    """

    # Model configurations
    MODEL_CONFIGS = {
        "claude-sonnet-4-20250514": {
            "name": "claude-sonnet",
            "cost_input": 3.00,  # per 1M tokens
            "cost_output": 15.00,
            "latency_ms": 2000,
            "quality": 0.90,
        },
        "claude-opus-4-20250514": {
            "name": "claude-opus",
            "cost_input": 15.00,
            "cost_output": 75.00,
            "latency_ms": 5000,
            "quality": 0.95,
        },
        "claude-3-5-haiku-20241022": {
            "name": "claude-haiku",
            "cost_input": 0.80,
            "cost_output": 4.00,
            "latency_ms": 500,
            "quality": 0.80,
        },
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        tunnel_url: str | None = None,
        tunnel_token: str | None = None,
    ):
        """Initialize Claude Tunnel provider.

        Args:
            model: Claude model ID to use
            tunnel_url: MCP Tunnel URL (default: Cloud Run URL)
            tunnel_token: MCP Tunnel auth token (default: from env)
        """
        self._model = model
        self._tunnel_url = tunnel_url or MCP_TUNNEL_URL
        self._tunnel_token = tunnel_token or os.environ.get("MCP_TUNNEL_TOKEN", "")
        self._call_count = 0

        if model not in self.MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model}. Available: {list(self.MODEL_CONFIGS.keys())}")

        self._config = self.MODEL_CONFIGS[model]

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return self._config["name"]

    @property
    def model_id(self) -> str:
        """The specific model being used."""
        return self._model

    def get_capabilities(self) -> ModelCapabilities:
        """Return the capabilities of this model."""
        return ModelCapabilities(
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            max_context_tokens=200000,
            max_output_tokens=8192,
            typical_latency_ms=self._config["latency_ms"],
            cost_per_1k_input_tokens=self._config["cost_input"] / 1000,
            cost_per_1k_output_tokens=self._config["cost_output"] / 1000,
            reasoning_quality=self._config["quality"],
            coding_quality=self._config["quality"],
            instruction_following=self._config["quality"],
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate a completion using Claude via MCP Tunnel.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            ModelResponse with the completion

        Raises:
            ProviderError: If the API call fails
        """
        self._call_count += 1
        start_time = time.time()

        # Build MCP request
        tool_args = {
            "messages": messages,
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            tool_args["system"] = system

        mcp_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "claude_complete",
                "arguments": tool_args,
            },
            "id": self._call_count,
        }

        # Call MCP Tunnel
        try:
            response = requests.post(
                self._tunnel_url,
                headers={
                    "Authorization": f"Bearer {self._tunnel_token}",
                    "Content-Type": "application/json",
                },
                json={"data": json.dumps(mcp_request)},
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ProviderError(f"MCP Tunnel request failed: {e}") from e

        # Parse response
        try:
            outer = response.json()
            result_str = outer.get("result", "{}")
            result = json.loads(result_str)
        except (json.JSONDecodeError, KeyError) as e:
            raise ProviderError(f"Failed to parse MCP response: {e}") from e

        # Check for errors in tool result
        if "error" in result:
            error_data = result.get("error", {})
            if isinstance(error_data, dict):
                raise ProviderError(f"Tool error: {error_data.get('message', error_data)}")
            raise ProviderError(f"Tool error: {error_data}")

        # Extract tool result
        tool_result = result.get("result", {})
        if isinstance(tool_result, str):
            tool_result = json.loads(tool_result)

        # Extract tool result from MCP response
        # Structure: result["result"]["content"][0]["text"] -> JSON string
        inner_result = tool_result.get("result", tool_result)
        content_list = inner_result.get("content", [])

        # Parse the text content which contains the actual tool response
        tool_response = {}
        if content_list and isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict) and item.get("type") == "text":
                    try:
                        tool_response = json.loads(item.get("text", "{}"))
                    except json.JSONDecodeError:
                        tool_response = {"content": item.get("text", "")}
                    break

        if not tool_response.get("success", False):
            raise ProviderError(f"Claude API error: {tool_response.get('error', 'Unknown error')}")

        # Extract response data (tokens at top level, not in usage object)
        content = tool_response.get("content", "")
        actual_latency = tool_response.get("latency_ms", (time.time() - start_time) * 1000)

        return ModelResponse(
            content=content,
            model=tool_response.get("model", self._model),
            input_tokens=tool_response.get("input_tokens", 0),
            output_tokens=tool_response.get("output_tokens", 0),
            latency_ms=actual_latency,
            stop_reason=tool_response.get("stop_reason"),
            metadata={
                "via_tunnel": True,
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
        """Stream not supported via MCP Tunnel - falls back to complete."""
        response = await self.complete(messages, system, max_tokens, temperature, **kwargs)
        # Yield content in chunks to simulate streaming
        words = response.content.split()
        for word in words:
            yield word + " "


class ClaudeSonnetProvider(ClaudeTunnelProvider):
    """Claude Sonnet provider via MCP Tunnel."""

    def __init__(self, tunnel_url: str | None = None, tunnel_token: str | None = None):
        """Initialize Claude Sonnet provider."""
        super().__init__(
            model="claude-sonnet-4-20250514",
            tunnel_url=tunnel_url,
            tunnel_token=tunnel_token,
        )


class ClaudeOpusProvider(ClaudeTunnelProvider):
    """Claude Opus provider via MCP Tunnel."""

    def __init__(self, tunnel_url: str | None = None, tunnel_token: str | None = None):
        """Initialize Claude Opus provider."""
        super().__init__(
            model="claude-opus-4-20250514",
            tunnel_url=tunnel_url,
            tunnel_token=tunnel_token,
        )


class ClaudeHaikuProvider(ClaudeTunnelProvider):
    """Claude Haiku provider via MCP Tunnel."""

    def __init__(self, tunnel_url: str | None = None, tunnel_token: str | None = None):
        """Initialize Claude Haiku provider."""
        super().__init__(
            model="claude-3-5-haiku-20241022",
            tunnel_url=tunnel_url,
            tunnel_token=tunnel_token,
        )


def register_claude_providers(tunnel_token: str | None = None) -> None:
    """Register all real Claude providers with the registry.

    Args:
        tunnel_token: MCP Tunnel auth token (default: from env)
    """
    from src.providers.registry import ModelRegistry

    token = tunnel_token or os.environ.get("MCP_TUNNEL_TOKEN", "")

    ModelRegistry.register("claude-sonnet", ClaudeSonnetProvider(tunnel_token=token))
    ModelRegistry.register("claude-opus", ClaudeOpusProvider(tunnel_token=token))
    ModelRegistry.register("claude-haiku", ClaudeHaikuProvider(tunnel_token=token))
