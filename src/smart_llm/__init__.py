"""
Smart LLM Client Module - ADR-015 Implementation.

Provides intelligent model routing based on task complexity and cost optimization.
Routes tasks to the most cost-effective model while maintaining quality.

Architecture:
    TIER 1 (Ultra-Cheap): gemini-flash, deepseek-v3, gpt-4o-mini
    TIER 2 (Budget): claude-haiku, deepseek-r1, gemini-pro
    TIER 3 (Premium): claude-sonnet, gpt-4o
    TIER 4 (Premium+): claude-opus

Usage:
    from src.smart_llm import SmartLLMClient, TaskType

    client = SmartLLMClient()

    # Auto-select model based on task type
    response = await client.complete(
        messages=[{"role": "user", "content": "Write a function to sort a list"}],
        task_type=TaskType.CODING
    )

    # Force specific model
    response = await client.complete(
        messages=[{"role": "user", "content": "Design system architecture"}],
        force_model="claude-opus"
    )

See Also:
    - ADR-015: Smart Model Routing Implementation
    - services/litellm-gateway/litellm-config.yaml
"""

from src.smart_llm.classifier import TaskClassifier

# TaskType is defined in both modules, import from classifier for base usage
from src.smart_llm.classifier import TaskType, Tier, MODEL_MAPPING

# SmartLLMClient requires openai package - import conditionally
try:
    from src.smart_llm.client import SmartLLMClient, LLMResponse, MODEL_COSTS
    __all__ = ["SmartLLMClient", "TaskType", "TaskClassifier", "LLMResponse", "MODEL_COSTS", "Tier", "MODEL_MAPPING"]
except ImportError:
    # openai not installed - classifier-only mode
    SmartLLMClient = None  # type: ignore
    LLMResponse = None  # type: ignore
    MODEL_COSTS = None  # type: ignore
    __all__ = ["TaskType", "TaskClassifier", "Tier", "MODEL_MAPPING"]

__version__ = "1.0.0"
