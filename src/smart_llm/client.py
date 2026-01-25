"""
Smart LLM Client with automatic model selection based on task type.

This client routes requests to the most cost-effective model while maintaining
quality. It uses the LiteLLM Gateway for unified access to multiple providers.

ADR-015: Smart Model Routing Implementation
"""

import logging
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

# Import TaskType from classifier (single source of truth)
from src.smart_llm.classifier import TaskType

logger = logging.getLogger(__name__)


# Model selection mapping based on task type
MODEL_MAPPING: dict[TaskType, str] = {
    # TIER 1: Ultra-Cheap
    TaskType.SIMPLE: "gemini-flash",
    TaskType.TRANSLATE: "gemini-flash",
    TaskType.SUMMARIZE: "gemini-flash",
    TaskType.FORMAT: "gemini-flash",
    # TIER 1-2: Budget coding
    TaskType.CODING: "deepseek-v3",
    TaskType.MATH: "deepseek-v3",
    TaskType.DATA: "gpt-4o-mini",
    # TIER 2: Budget analysis
    TaskType.ANALYSIS: "claude-haiku",
    TaskType.REVIEW: "claude-haiku",
    TaskType.DEBUG: "claude-haiku",
    # TIER 3: Premium
    TaskType.FEATURE: "claude-sonnet",
    TaskType.REFACTOR: "claude-sonnet",
    TaskType.COMPLEX: "claude-sonnet",
    # TIER 4: Premium+
    TaskType.ARCHITECTURE: "claude-opus",
    TaskType.RESEARCH: "deepseek-r1",
    TaskType.CRITICAL: "claude-opus",
    # Default
    TaskType.GENERAL: "claude-haiku",
}

# Cost per 1M output tokens (for logging/tracking)
MODEL_COSTS: dict[str, float] = {
    "gemini-flash": 0.30,
    "deepseek-v3": 1.10,
    "gpt-4o-mini": 0.60,
    "claude-haiku": 5.00,
    "deepseek-r1": 2.19,
    "gemini-pro": 5.00,
    "claude-sonnet": 15.00,
    "gpt-4o": 10.00,
    "claude-opus": 75.00,
}


@dataclass
class LLMResponse:
    """Standardized response from SmartLLMClient."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float  # USD
    task_type: TaskType | None


class SmartLLMClient:
    """Smart LLM Client with automatic model selection.

    Routes requests to the most cost-effective model based on task type.
    Uses LiteLLM Gateway for unified access to multiple providers.

    Args:
        base_url: LiteLLM Gateway URL
        api_key: API key (not required for self-hosted gateway)
        default_model: Default model if task type not specified

    Example:
        client = SmartLLMClient()

        # Auto-select model based on task
        response = await client.complete(
            messages=[{"role": "user", "content": "What is Python?"}],
            task_type=TaskType.SIMPLE
        )
        # Uses gemini-flash ($0.30/1M)

        response = await client.complete(
            messages=[{"role": "user", "content": "Write a sorting algorithm"}],
            task_type=TaskType.CODING
        )
        # Uses deepseek-v3 ($1.10/1M)
    """

    def __init__(
        self,
        base_url: str = "https://litellm-gateway-production-0339.up.railway.app",
        api_key: str = "dummy",
        default_model: str = "claude-haiku",
    ):
        """Initialize the SmartLLMClient.

        Args:
            base_url: LiteLLM Gateway URL
            api_key: API key (not required for self-hosted)
            default_model: Default model when task_type is not specified
        """
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.default_model = default_model
        self.base_url = base_url

    def select_model(
        self, task_type: TaskType | str | None, force_model: str | None = None
    ) -> str:
        """Select the optimal model based on task type.

        Args:
            task_type: Type of task (TaskType enum or string)
            force_model: Override automatic selection

        Returns:
            Model name to use
        """
        if force_model:
            return force_model

        if task_type is None:
            return self.default_model

        # Convert string to TaskType if needed
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                logger.warning(f"Unknown task type: {task_type}, using default")
                return self.default_model

        return MODEL_MAPPING.get(task_type, self.default_model)

    def estimate_cost(self, model: str, output_tokens: int) -> float:
        """Estimate cost in USD based on model and output tokens.

        Args:
            model: Model name
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        cost_per_million = MODEL_COSTS.get(model, 15.00)  # Default to Sonnet cost
        return (output_tokens / 1_000_000) * cost_per_million

    async def complete(
        self,
        messages: list[dict[str, str]],
        task_type: TaskType | str | None = None,
        force_model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion with automatic model selection.

        Args:
            messages: List of message dicts with 'role' and 'content'
            task_type: Type of task for automatic model selection
            force_model: Force specific model (overrides task_type)
            system: System prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            **kwargs: Additional parameters passed to OpenAI client

        Returns:
            LLMResponse with content, model, tokens, and cost

        Example:
            response = await client.complete(
                messages=[{"role": "user", "content": "Hello"}],
                task_type=TaskType.SIMPLE
            )
            print(f"Used {response.model}, cost: ${response.estimated_cost:.4f}")
        """
        model = self.select_model(task_type, force_model)

        # Add system message if provided
        if system:
            messages = [{"role": "system", "content": system}] + messages

        logger.info(f"SmartLLM: task_type={task_type}, selected_model={model}")

        # Call LiteLLM Gateway
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

        # Extract usage info
        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        total_tokens = response.usage.total_tokens if response.usage else 0

        # Calculate cost
        estimated_cost = self.estimate_cost(model, output_tokens)

        logger.info(
            f"SmartLLM response: model={model}, "
            f"tokens={total_tokens}, cost=${estimated_cost:.4f}"
        )

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            task_type=TaskType(task_type) if isinstance(task_type, str) else task_type,
        )

    async def complete_simple(
        self,
        prompt: str,
        task_type: TaskType | str | None = TaskType.GENERAL,
        **kwargs: Any,
    ) -> str:
        """Simplified completion - returns just the content string.

        Args:
            prompt: User prompt
            task_type: Task type for model selection
            **kwargs: Additional parameters

        Returns:
            Response content string
        """
        response = await self.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type=task_type,
            **kwargs,
        )
        return response.content

    async def code(
        self,
        prompt: str,
        language: str = "python",
        **kwargs: Any,
    ) -> str:
        """Generate code using the optimal coding model (DeepSeek V3).

        Args:
            prompt: Code generation prompt
            language: Programming language
            **kwargs: Additional parameters

        Returns:
            Generated code
        """
        system = f"You are an expert {language} programmer. Write clean, efficient code."
        response = await self.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type=TaskType.CODING,
            system=system,
            **kwargs,
        )
        return response.content

    async def analyze(
        self,
        content: str,
        analysis_type: str = "general",
        **kwargs: Any,
    ) -> str:
        """Analyze content using the budget analysis model (Claude Haiku).

        Args:
            content: Content to analyze
            analysis_type: Type of analysis
            **kwargs: Additional parameters

        Returns:
            Analysis result
        """
        prompt = f"Analyze the following ({analysis_type}):\n\n{content}"
        response = await self.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type=TaskType.ANALYSIS,
            **kwargs,
        )
        return response.content

    async def research(
        self,
        topic: str,
        depth: str = "deep",
        **kwargs: Any,
    ) -> str:
        """Research a topic using DeepSeek R1 reasoning model.

        Args:
            topic: Research topic
            depth: Research depth (shallow, medium, deep)
            **kwargs: Additional parameters

        Returns:
            Research findings
        """
        prompt = f"Research the following topic in {depth} detail:\n\n{topic}"
        response = await self.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type=TaskType.RESEARCH,
            **kwargs,
        )
        return response.content
