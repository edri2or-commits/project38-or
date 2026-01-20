"""
Model Provider Abstraction Layer.

This module provides a stable interface for model providers, allowing
easy swapping between different LLM backends (Claude, GPT, Gemini, etc.)
without changing application code.

Architecture (ADR-009):
    Application Layer
         ↓
    ModelProvider Interface (this module)
         ↓
    Concrete Adapters (Claude, OpenAI, etc.)
         ↓
    LLM APIs

Usage:
    from src.providers import ModelRegistry, ModelProvider

    # Get default provider
    provider = ModelRegistry.get()
    response = await provider.complete(messages)

    # Switch providers at runtime
    ModelRegistry.set_default("gpt-4")
    provider = ModelRegistry.get()
"""

from src.providers.base import ModelCapabilities, ModelProvider, ModelResponse
from src.providers.registry import ModelRegistry

__all__ = [
    "ModelProvider",
    "ModelResponse",
    "ModelCapabilities",
    "ModelRegistry",
]
