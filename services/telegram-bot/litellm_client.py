"""LiteLLM Gateway client for Telegram Bot service.

This module provides a client for interacting with the LiteLLM Gateway,
which routes requests to Claude, GPT-4, or Gemini with automatic fallback.
"""

import logging
from typing import Any

from config import get_settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LiteLLMClient:
    """Client for LiteLLM Gateway using OpenAI-compatible API.

    The LiteLLM Gateway exposes an OpenAI-compatible /v1/chat/completions endpoint
    that routes to multiple providers (Anthropic Claude, OpenAI GPT-4, Google Gemini)
    with automatic fallback.

    Attributes:
        client: AsyncOpenAI client pointed at LiteLLM Gateway
        default_model: Default model to use (e.g., "claude-sonnet")
        max_tokens: Maximum tokens per response
    """

    def __init__(self) -> None:
        """Initialize LiteLLM client."""
        settings = get_settings()

        # Point OpenAI client to LiteLLM Gateway
        self.client = AsyncOpenAI(
            base_url=settings.litellm_gateway_url,
            api_key="dummy",  # Not required for self-hosted LiteLLM
        )

        self.default_model = settings.default_model
        self.max_tokens = settings.max_tokens

        logger.info(
            f"LiteLLM client initialized: {settings.litellm_gateway_url}, "
            f"model={self.default_model}"
        )

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Generate a response from LLM via LiteLLM Gateway.

        Args:
            messages: List of conversation messages in OpenAI format
                     [{"role": "user", "content": "Hello"}, ...]
            model: Model to use (defaults to self.default_model)
            max_tokens: Max tokens (defaults to self.max_tokens)

        Returns:
            Tuple of (response_text, usage_info)
            - response_text: The LLM's response
            - usage_info: Dict with token usage and model info

        Raises:
            Exception: If LiteLLM Gateway request fails

        Example:
            >>> client = LiteLLMClient()
            >>> messages = [{"role": "user", "content": "Say hello"}]
            >>> response, usage = await client.generate_response(messages)
            >>> print(response)  # "Hello! How can I help you today?"
            >>> print(usage)     # {"model": "claude-sonnet", "total_tokens": 25}
        """
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
            )

            # Extract response text
            response_text = response.choices[0].message.content

            # Extract usage information
            usage_info = {
                "model": response.model,
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            logger.info(
                f"LiteLLM response: model={usage_info['model']}, "
                f"tokens={usage_info['total_tokens']}"
            )

            return response_text, usage_info

        except Exception as e:
            logger.error(f"LiteLLM Gateway request failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if LiteLLM Gateway is accessible.

        Returns:
            bool: True if gateway is reachable, False otherwise

        Example:
            >>> client = LiteLLMClient()
            >>> is_healthy = await client.health_check()
            >>> print(f"Gateway: {'healthy' if is_healthy else 'unhealthy'}")
        """
        try:
            # Try a minimal request
            messages = [{"role": "user", "content": "ping"}]
            await self.generate_response(messages, max_tokens=5)
            return True
        except Exception as e:
            logger.error(f"LiteLLM Gateway health check failed: {e}")
            return False
