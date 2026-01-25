"""
Tests for SmartLLMClient module.

ADR-015: Smart Model Routing Implementation
"""

import pytest

from src.smart_llm.classifier import ClassificationResult, TaskClassifier, Tier
from src.smart_llm.client import (
    MODEL_COSTS,
    MODEL_MAPPING,
    LLMResponse,
    SmartLLMClient,
    TaskType,
)


class TestTaskType:
    """Tests for TaskType enum."""

    def test_all_task_types_have_model_mapping(self):
        """Every task type should map to a model."""
        for task_type in TaskType:
            assert task_type in MODEL_MAPPING
            assert MODEL_MAPPING[task_type] in MODEL_COSTS

    def test_tier1_tasks_use_cheap_models(self):
        """Tier 1 tasks should use ultra-cheap models."""
        tier1_tasks = [
            TaskType.SIMPLE,
            TaskType.TRANSLATE,
            TaskType.SUMMARIZE,
            TaskType.FORMAT,
        ]
        cheap_models = ["gemini-flash", "deepseek-v3", "gpt-4o-mini"]

        for task in tier1_tasks:
            model = MODEL_MAPPING[task]
            assert model in cheap_models, f"{task} should use cheap model, got {model}"

    def test_coding_uses_deepseek(self):
        """Coding tasks should use DeepSeek V3 (best ROI for code)."""
        assert MODEL_MAPPING[TaskType.CODING] == "deepseek-v3"

    def test_architecture_uses_opus(self):
        """Architecture tasks should use Claude Opus (premium quality)."""
        assert MODEL_MAPPING[TaskType.ARCHITECTURE] == "claude-opus"


class TestSmartLLMClient:
    """Tests for SmartLLMClient."""

    def test_init_defaults(self):
        """Test default initialization."""
        client = SmartLLMClient()
        assert client.default_model == "claude-haiku"
        assert "litellm-gateway" in client.base_url

    def test_init_custom_url(self):
        """Test custom URL initialization."""
        client = SmartLLMClient(base_url="http://localhost:4000")
        assert client.base_url == "http://localhost:4000"

    def test_select_model_with_task_type(self):
        """Test model selection based on task type."""
        client = SmartLLMClient()

        # Test various task types
        assert client.select_model(TaskType.SIMPLE, None) == "gemini-flash"
        assert client.select_model(TaskType.CODING, None) == "deepseek-v3"
        assert client.select_model(TaskType.ANALYSIS, None) == "claude-haiku"
        assert client.select_model(TaskType.FEATURE, None) == "claude-sonnet"
        assert client.select_model(TaskType.ARCHITECTURE, None) == "claude-opus"

    def test_select_model_with_string_task_type(self):
        """Test model selection with string task type."""
        client = SmartLLMClient()

        assert client.select_model("simple", None) == "gemini-flash"
        assert client.select_model("coding", None) == "deepseek-v3"

    def test_select_model_force_override(self):
        """Force model should override task type."""
        client = SmartLLMClient()

        # Even with SIMPLE task type, force_model should win
        assert client.select_model(TaskType.SIMPLE, "claude-opus") == "claude-opus"

    def test_select_model_unknown_string(self):
        """Unknown string task type should use default."""
        client = SmartLLMClient()

        result = client.select_model("unknown_task_xyz", None)
        assert result == client.default_model

    def test_select_model_none_uses_default(self):
        """None task type should use default model."""
        client = SmartLLMClient()

        result = client.select_model(None, None)
        assert result == client.default_model

    def test_estimate_cost_known_model(self):
        """Test cost estimation for known models."""
        client = SmartLLMClient()

        # 1M tokens
        assert client.estimate_cost("gemini-flash", 1_000_000) == 0.30
        assert client.estimate_cost("deepseek-v3", 1_000_000) == 1.10
        assert client.estimate_cost("claude-haiku", 1_000_000) == 5.00
        assert client.estimate_cost("claude-sonnet", 1_000_000) == 15.00
        assert client.estimate_cost("claude-opus", 1_000_000) == 75.00

    def test_estimate_cost_unknown_model(self):
        """Unknown model should use Sonnet cost as default."""
        client = SmartLLMClient()

        result = client.estimate_cost("unknown-model", 1_000_000)
        assert result == 15.00  # Sonnet cost

    def test_estimate_cost_scaling(self):
        """Cost should scale linearly with tokens."""
        client = SmartLLMClient()

        # 100k tokens = 1/10 of 1M
        assert client.estimate_cost("gemini-flash", 100_000) == pytest.approx(0.03)


class TestTaskClassifier:
    """Tests for TaskClassifier."""

    def test_classify_simple_question(self):
        """Simple questions should be classified as SIMPLE."""
        classifier = TaskClassifier()

        result = classifier.classify("What is Python?")
        assert result.task_type == TaskType.SIMPLE
        assert result.suggested_model == "gemini-flash"

    def test_classify_coding_task(self):
        """Coding tasks should be classified as CODING."""
        classifier = TaskClassifier()

        prompts = [
            "Write a Python function to sort a list",
            "Create a class for user authentication",
            "Implement a binary search algorithm",
        ]

        for prompt in prompts:
            result = classifier.classify(prompt)
            assert result.task_type == TaskType.CODING, f"Failed for: {prompt}"
            assert result.suggested_model == "deepseek-v3"

    def test_classify_translation(self):
        """Translation tasks should be classified as TRANSLATE."""
        classifier = TaskClassifier()

        result = classifier.classify("Translate this to Hebrew")
        assert result.task_type == TaskType.TRANSLATE
        assert result.suggested_model == "gemini-flash"

    def test_classify_summarize(self):
        """Summarization tasks should be classified as SUMMARIZE."""
        classifier = TaskClassifier()

        result = classifier.classify("Summarize this article")
        assert result.task_type == TaskType.SUMMARIZE
        assert result.suggested_model == "gemini-flash"

    def test_classify_analysis(self):
        """Analysis tasks should be classified as ANALYSIS."""
        classifier = TaskClassifier()

        result = classifier.classify("Analyze this code for performance issues")
        assert result.task_type == TaskType.ANALYSIS
        assert result.suggested_model == "claude-haiku"

    def test_classify_architecture(self):
        """Architecture tasks should be classified as ARCHITECTURE."""
        classifier = TaskClassifier()

        prompts = [
            "Design the system architecture for a microservices platform",
            "Create an ADR for the new authentication system",
        ]

        for prompt in prompts:
            result = classifier.classify(prompt)
            assert result.task_type == TaskType.ARCHITECTURE, f"Failed for: {prompt}"
            assert result.suggested_model == "claude-opus"

    def test_classify_research(self):
        """Research tasks should be classified as RESEARCH."""
        classifier = TaskClassifier()

        result = classifier.classify("Research best practices for API design")
        assert result.task_type == TaskType.RESEARCH
        assert result.suggested_model == "deepseek-r1"

    def test_classify_debug(self):
        """Debug tasks should be classified as DEBUG."""
        classifier = TaskClassifier()

        prompts = [
            "Debug this error: IndexError",
            "Why doesn't this code work?",
            "Fix this bug in the authentication module",
        ]

        for prompt in prompts:
            result = classifier.classify(prompt)
            assert result.task_type == TaskType.DEBUG, f"Failed for: {prompt}"

    def test_classify_unknown_uses_general(self):
        """Unknown prompts should default to GENERAL."""
        classifier = TaskClassifier()

        result = classifier.classify("xyz abc 123")
        assert result.task_type == TaskType.GENERAL
        assert result.confidence < 0.5  # Low confidence

    def test_classify_returns_confidence(self):
        """Classification should include confidence score."""
        classifier = TaskClassifier()

        result = classifier.classify("Write a Python function")
        assert 0 <= result.confidence <= 1

    def test_classify_batch(self):
        """Batch classification should work."""
        classifier = TaskClassifier()

        prompts = [
            "What is Python?",
            "Write a sorting function",
            "Design system architecture",
        ]

        results = classifier.classify_batch(prompts)
        assert len(results) == 3
        assert all(isinstance(r, ClassificationResult) for r in results)


class TestModelCosts:
    """Tests for model cost definitions."""

    def test_tier1_models_are_cheapest(self):
        """Tier 1 models should be < $1/1M."""
        tier1_models = ["gemini-flash", "deepseek-v3", "gpt-4o-mini"]
        for model in tier1_models:
            assert MODEL_COSTS[model] <= 1.10, f"{model} should be < $1.10/1M"

    def test_tier2_models_are_budget(self):
        """Tier 2 models should be $1-5/1M."""
        tier2_models = ["claude-haiku", "deepseek-r1", "gemini-pro"]
        for model in tier2_models:
            assert 1.0 <= MODEL_COSTS[model] <= 5.50, f"{model} should be $1-5.50/1M"

    def test_tier3_models_are_premium(self):
        """Tier 3 models should be $5-15/1M."""
        tier3_models = ["claude-sonnet", "gpt-4o"]
        for model in tier3_models:
            assert 5.0 <= MODEL_COSTS[model] <= 15.0, f"{model} should be $5-15/1M"

    def test_opus_is_most_expensive(self):
        """Claude Opus should be the most expensive."""
        assert MODEL_COSTS["claude-opus"] == max(MODEL_COSTS.values())


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """Test LLMResponse creation."""
        response = LLMResponse(
            content="Hello",
            model="gemini-flash",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            estimated_cost=0.0000015,
            task_type=TaskType.SIMPLE,
        )

        assert response.content == "Hello"
        assert response.model == "gemini-flash"
        assert response.total_tokens == 15


class TestCostSavingsCalculation:
    """Tests to verify cost savings claims from ADR-015."""

    def test_coding_savings_vs_sonnet(self):
        """Coding with DeepSeek should save 93% vs Sonnet."""
        sonnet_cost = MODEL_COSTS["claude-sonnet"]
        deepseek_cost = MODEL_COSTS["deepseek-v3"]

        savings = (sonnet_cost - deepseek_cost) / sonnet_cost
        assert savings >= 0.90, f"Expected 90%+ savings, got {savings*100:.1f}%"

    def test_simple_savings_vs_sonnet(self):
        """Simple tasks with Gemini Flash should save 98% vs Sonnet."""
        sonnet_cost = MODEL_COSTS["claude-sonnet"]
        flash_cost = MODEL_COSTS["gemini-flash"]

        savings = (sonnet_cost - flash_cost) / sonnet_cost
        assert savings >= 0.95, f"Expected 95%+ savings, got {savings*100:.1f}%"

    def test_research_savings_vs_opus(self):
        """Research with DeepSeek R1 should save 97% vs Opus."""
        opus_cost = MODEL_COSTS["claude-opus"]
        r1_cost = MODEL_COSTS["deepseek-r1"]

        savings = (opus_cost - r1_cost) / opus_cost
        assert savings >= 0.95, f"Expected 95%+ savings, got {savings*100:.1f}%"
