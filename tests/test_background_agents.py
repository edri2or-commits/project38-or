"""Tests for background agents.

Tests agent structure, metrics collection, and model routing without
making actual LLM calls.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.background_agents.metrics import AgentMetrics, MetricsCollector, generate_run_id
from src.smart_llm.classifier import MODEL_MAPPING, TaskType


class TestAgentMetrics:
    """Tests for AgentMetrics dataclass."""

    def test_metrics_creation(self):
        """Test creating metrics with required fields."""
        metrics = AgentMetrics(
            agent_name="test_agent",
            run_id="abc123",
        )
        assert metrics.agent_name == "test_agent"
        assert metrics.run_id == "abc123"
        assert metrics.success is False
        assert metrics.duration_ms == 0

    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = AgentMetrics(
            agent_name="test_agent",
            run_id="abc123",
            success=True,
            model_used="claude-haiku",
            input_tokens=100,
            output_tokens=50,
        )
        data = metrics.to_dict()
        assert data["agent_name"] == "test_agent"
        assert data["success"] is True
        assert data["model_used"] == "claude-haiku"
        assert data["input_tokens"] == 100

    def test_metrics_to_json(self):
        """Test JSON serialization."""
        metrics = AgentMetrics(
            agent_name="test_agent",
            run_id="abc123",
        )
        json_str = metrics.to_json()
        parsed = json.loads(json_str)
        assert parsed["agent_name"] == "test_agent"


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collector_init(self, tmp_path):
        """Test collector initialization."""
        collector = MetricsCollector(base_path=tmp_path / "metrics")
        assert collector.base_path.exists()

    def test_store_and_load(self, tmp_path):
        """Test storing and loading metrics."""
        collector = MetricsCollector(base_path=tmp_path / "metrics")

        metrics = AgentMetrics(
            agent_name="test_agent",
            run_id="run123",
            success=True,
            model_used="claude-haiku",
            estimated_cost_usd=0.005,
        )

        path = collector.store(metrics)
        assert path.exists()

        loaded = collector.load_day()
        assert len(loaded) == 1
        assert loaded[0].agent_name == "test_agent"
        assert loaded[0].success is True

    def test_get_summary(self, tmp_path):
        """Test getting summary statistics."""
        collector = MetricsCollector(base_path=tmp_path / "metrics")

        # Store multiple metrics
        for i in range(3):
            metrics = AgentMetrics(
                agent_name=f"agent_{i % 2}",  # Two different agents
                run_id=f"run_{i}",
                success=True,
                model_used="claude-haiku",
                total_tokens=100 * (i + 1),
                estimated_cost_usd=0.001 * (i + 1),
            )
            collector.store(metrics)

        summary = collector.get_summary()
        assert summary["total_runs"] == 3
        assert summary["successful_runs"] == 3
        assert summary["success_rate"] == 1.0
        assert len(summary["by_agent"]) == 2


class TestGenerateRunId:
    """Tests for run ID generation."""

    def test_run_id_uniqueness(self):
        """Test that run IDs are unique."""
        ids = [generate_run_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_run_id_format(self):
        """Test run ID format."""
        run_id = generate_run_id()
        assert len(run_id) == 8
        assert run_id.isalnum()


class TestModelRouting:
    """Tests for model routing in agents."""

    def test_cost_opt_uses_haiku(self):
        """CostOptAgent should use claude-haiku (ANALYSIS task type)."""
        from src.background_agents.cost_opt_agent import CostOptAgent

        agent = CostOptAgent()
        model = MODEL_MAPPING.get(agent.MODEL_TASK_TYPE)
        assert model == "claude-haiku"

    def test_health_synth_uses_gemini_flash(self):
        """HealthSynthAgent should use gemini-flash (SUMMARIZE task type)."""
        from src.background_agents.health_synth_agent import HealthSynthAgent

        agent = HealthSynthAgent()
        model = MODEL_MAPPING.get(agent.MODEL_TASK_TYPE)
        assert model == "gemini-flash"

    def test_learn_insight_uses_sonnet(self):
        """LearnInsightAgent should use claude-sonnet (COMPLEX task type)."""
        from src.background_agents.learn_insight_agent import LearnInsightAgent

        agent = LearnInsightAgent()
        model = MODEL_MAPPING.get(agent.MODEL_TASK_TYPE)
        assert model == "claude-sonnet"


class TestCostOptAgent:
    """Tests for CostOptAgent."""

    def test_agent_name(self):
        """Test agent name is set correctly."""
        from src.background_agents.cost_opt_agent import CostOptAgent

        agent = CostOptAgent()
        assert agent.AGENT_NAME == "cost_opt_agent"

    @pytest.mark.asyncio
    async def test_get_cost_data(self):
        """Test cost data retrieval returns expected structure."""
        from src.background_agents.cost_opt_agent import CostOptAgent

        agent = CostOptAgent()
        data = await agent._get_cost_data()

        assert "period" in data
        assert "total_cost_usd" in data
        assert "breakdown" in data
        assert "services" in data
        assert "llm_usage" in data

    def test_build_prompt(self):
        """Test prompt building includes cost data."""
        from src.background_agents.cost_opt_agent import CostOptAgent

        agent = CostOptAgent()
        cost_data = {"total_cost_usd": 100, "services": []}
        prompt = agent._build_prompt(cost_data)

        assert "cost optimization" in prompt.lower()
        assert "100" in prompt
        assert "JSON" in prompt


class TestHealthSynthAgent:
    """Tests for HealthSynthAgent."""

    def test_agent_name(self):
        """Test agent name is set correctly."""
        from src.background_agents.health_synth_agent import HealthSynthAgent

        agent = HealthSynthAgent()
        assert agent.AGENT_NAME == "health_synth_agent"

    @pytest.mark.asyncio
    async def test_get_health_data(self):
        """Test health data retrieval returns expected structure."""
        from src.background_agents.health_synth_agent import HealthSynthAgent

        agent = HealthSynthAgent()
        data = await agent._get_health_data()

        assert "timestamp" in data
        assert "services" in data
        assert "infrastructure" in data
        assert "anomalies_detected" in data


class TestLearnInsightAgent:
    """Tests for LearnInsightAgent."""

    def test_agent_name(self):
        """Test agent name is set correctly."""
        from src.background_agents.learn_insight_agent import LearnInsightAgent

        agent = LearnInsightAgent()
        assert agent.AGENT_NAME == "learn_insight_agent"

    @pytest.mark.asyncio
    async def test_get_learning_data(self):
        """Test learning data retrieval returns expected structure."""
        from src.background_agents.learn_insight_agent import LearnInsightAgent

        agent = LearnInsightAgent()
        data = await agent._get_learning_data()

        assert "period" in data
        assert "total_actions" in data
        assert "actions_by_type" in data
        assert "failure_patterns" in data
        assert "success_patterns" in data


class TestModelCosts:
    """Tests for model cost calculations."""

    def test_cost_tiers(self):
        """Test that cost tiers are correctly ordered."""
        from src.smart_llm.client import MODEL_COSTS

        # Tier 1 should be cheapest
        assert MODEL_COSTS["gemini-flash"] < MODEL_COSTS["claude-haiku"]
        assert MODEL_COSTS["deepseek-v3"] < MODEL_COSTS["claude-haiku"]

        # Tier 2 should be cheaper than Tier 3
        assert MODEL_COSTS["claude-haiku"] < MODEL_COSTS["claude-sonnet"]

        # Tier 3 should be cheaper than Tier 4
        assert MODEL_COSTS["claude-sonnet"] < MODEL_COSTS["claude-opus"]

    def test_estimated_24h_cost(self):
        """Test that 24h cost estimate is reasonable."""
        from src.smart_llm.client import MODEL_COSTS

        # Based on design:
        # CostOptAgent: 4 runs × ~1000 tokens × claude-haiku
        # HealthSynthAgent: 6 runs × ~800 tokens × gemini-flash
        # LearnInsightAgent: 3 runs × ~1500 tokens × claude-sonnet

        cost_opt_cost = 4 * 1000 / 1_000_000 * MODEL_COSTS["claude-haiku"]
        health_synth_cost = 6 * 800 / 1_000_000 * MODEL_COSTS["gemini-flash"]
        learn_insight_cost = 3 * 1500 / 1_000_000 * MODEL_COSTS["claude-sonnet"]

        total_24h = cost_opt_cost + health_synth_cost + learn_insight_cost

        # Should be under $0.15 for 24 hours
        assert total_24h < 0.15, f"24h cost estimate {total_24h:.4f} exceeds budget"
