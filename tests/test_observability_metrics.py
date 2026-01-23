"""Tests for Observability Metrics module.

Tests the metrics module in src/observability/metrics.py.
Covers:
- AgentMetric dataclass
- MetricsCollector initialization and methods
- Record methods (latency, tokens, error, success)
- In-memory buffer fallback
- Database storage (mocked)
- LatencyTracker context manager
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _import_metrics_directly():
    """Import metrics module directly, bypassing __init__.py which requires opentelemetry."""
    # Add asyncpg mock if not installed
    if "asyncpg" not in sys.modules:
        mock_asyncpg = MagicMock()
        mock_asyncpg.Pool = MagicMock
        sys.modules["asyncpg"] = mock_asyncpg

    spec = importlib.util.spec_from_file_location(
        "observability_metrics",
        "src/observability/metrics.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Import module directly to avoid opentelemetry dependency
_metrics_module = _import_metrics_directly()
AgentMetric = _metrics_module.AgentMetric
MetricsCollector = _metrics_module.MetricsCollector
LatencyTracker = _metrics_module.LatencyTracker


class TestAgentMetric:
    """Tests for AgentMetric dataclass."""

    def test_creation(self):
        """Test that AgentMetric can be created with all fields."""
        metric = AgentMetric(
            agent_id="agent-123",
            model_id="claude-sonnet-4.5",
            metric_name="latency_ms",
            value=150.0,
            labels={"environment": "prod"},
            timestamp=datetime.now(UTC),
        )

        assert metric.agent_id == "agent-123"
        assert metric.model_id == "claude-sonnet-4.5"
        assert metric.metric_name == "latency_ms"
        assert metric.value == 150.0
        assert metric.labels == {"environment": "prod"}

    def test_creation_optional_model_id(self):
        """Test that model_id can be None."""
        metric = AgentMetric(
            agent_id="agent-123",
            model_id=None,
            metric_name="error_count",
            value=1.0,
            labels={},
            timestamp=datetime.now(UTC),
        )

        assert metric.model_id is None


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_init_no_db(self):
        """Test initialization without database."""
        collector = MetricsCollector(db_pool=None)

        assert collector.db_pool is None
        assert collector._in_memory_buffer == []

    def test_init_with_db(self):
        """Test initialization with database pool."""
        mock_pool = MagicMock()
        collector = MetricsCollector(db_pool=mock_pool)

        assert collector.db_pool is mock_pool

    @pytest.mark.asyncio
    async def test_record_metric_in_memory(self):
        """Test recording metric to in-memory buffer."""
        collector = MetricsCollector(db_pool=None)

        metric = AgentMetric(
            agent_id="agent-123",
            model_id=None,
            metric_name="test_metric",
            value=42.0,
            labels={},
            timestamp=datetime.now(UTC),
        )

        result = await collector.record_metric(metric)

        assert result is True
        assert len(collector._in_memory_buffer) == 1
        assert collector._in_memory_buffer[0] == metric

    @pytest.mark.asyncio
    async def test_record_metric_buffer_limit(self):
        """Test that in-memory buffer is limited to 1000 items."""
        collector = MetricsCollector(db_pool=None)

        # Add 1050 metrics
        for i in range(1050):
            metric = AgentMetric(
                agent_id=f"agent-{i}",
                model_id=None,
                metric_name="test",
                value=float(i),
                labels={},
                timestamp=datetime.now(UTC),
            )
            await collector.record_metric(metric)

        # Should be limited to 1000
        assert len(collector._in_memory_buffer) == 1000
        # Should keep most recent (last 1000)
        assert collector._in_memory_buffer[0].value == 50.0  # 1050 - 1000 = 50

    @pytest.mark.asyncio
    async def test_record_metric_to_database(self):
        """Test recording metric to database."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))

        collector = MetricsCollector(db_pool=mock_pool)

        metric = AgentMetric(
            agent_id="agent-123",
            model_id="claude-sonnet-4.5",
            metric_name="latency_ms",
            value=150.0,
            labels={"env": "prod"},
            timestamp=datetime.now(UTC),
        )

        result = await collector.record_metric(metric)

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_latency(self):
        """Test recording latency metric."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency(
            agent_id="agent-123",
            latency_seconds=1.5,
            labels={"task": "search"},
        )

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.agent_id == "agent-123"
        assert metric.metric_name == "latency_ms"
        assert metric.value == 1500.0  # 1.5 seconds = 1500ms
        assert metric.labels == {"task": "search"}

    @pytest.mark.asyncio
    async def test_record_latency_default_labels(self):
        """Test recording latency with no labels."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency(agent_id="agent-123", latency_seconds=0.5)

        metric = collector._in_memory_buffer[0]
        assert metric.labels == {}

    @pytest.mark.asyncio
    async def test_record_tokens(self):
        """Test recording token usage metrics."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_tokens(
            agent_id="agent-123",
            input_tokens=100,
            output_tokens=50,
            model_id="claude-sonnet-4.5",
            labels={"task": "generate"},
        )

        # Should record 2 metrics (input and output)
        assert len(collector._in_memory_buffer) == 2

        input_metric = collector._in_memory_buffer[0]
        assert input_metric.metric_name == "tokens_input"
        assert input_metric.value == 100.0
        assert input_metric.model_id == "claude-sonnet-4.5"

        output_metric = collector._in_memory_buffer[1]
        assert output_metric.metric_name == "tokens_output"
        assert output_metric.value == 50.0

    @pytest.mark.asyncio
    async def test_record_tokens_with_reasoning(self):
        """Test recording tokens including reasoning tokens."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_tokens(
            agent_id="agent-123",
            input_tokens=100,
            output_tokens=50,
            model_id="o1-preview",
            reasoning_tokens=200,
        )

        # Should record 3 metrics
        assert len(collector._in_memory_buffer) == 3

        reasoning_metric = collector._in_memory_buffer[2]
        assert reasoning_metric.metric_name == "tokens_reasoning"
        assert reasoning_metric.value == 200.0

    @pytest.mark.asyncio
    async def test_record_tokens_no_reasoning(self):
        """Test that reasoning tokens are not recorded when None."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_tokens(
            agent_id="agent-123",
            input_tokens=100,
            output_tokens=50,
            model_id="claude-sonnet-4.5",
            reasoning_tokens=None,  # Explicitly None
        )

        # Should only record 2 metrics
        assert len(collector._in_memory_buffer) == 2

    @pytest.mark.asyncio
    async def test_record_error(self):
        """Test recording error metric."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_error(
            agent_id="agent-123",
            error_type="APIError",
            error_message="Rate limit exceeded",
            labels={"endpoint": "/api/generate"},
        )

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.metric_name == "error_count"
        assert metric.value == 1.0
        assert metric.labels["error_type"] == "APIError"
        assert metric.labels["error_message"] == "Rate limit exceeded"
        assert metric.labels["endpoint"] == "/api/generate"

    @pytest.mark.asyncio
    async def test_record_error_truncates_message(self):
        """Test that error messages are truncated to 200 chars."""
        collector = MetricsCollector(db_pool=None)

        long_message = "x" * 300  # 300 characters

        await collector.record_error(
            agent_id="agent-123",
            error_type="TestError",
            error_message=long_message,
        )

        metric = collector._in_memory_buffer[0]
        assert len(metric.labels["error_message"]) == 200

    @pytest.mark.asyncio
    async def test_record_success(self):
        """Test recording success metric."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_success(
            agent_id="agent-123",
            task_type="database_query",
            labels={"database": "postgres"},
        )

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.metric_name == "success_count"
        assert metric.value == 1.0
        assert metric.labels["task_type"] == "database_query"
        assert metric.labels["database"] == "postgres"

    @pytest.mark.asyncio
    async def test_get_recent_metrics_in_memory(self):
        """Test getting recent metrics from in-memory buffer."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency("agent-1", 0.5)
        await collector.record_latency("agent-2", 1.0)
        await collector.record_latency("agent-1", 0.3)

        metrics = await collector.get_recent_metrics(limit=10)

        assert len(metrics) == 3
        # Should be dictionaries
        assert isinstance(metrics[0], dict)
        assert "agent_id" in metrics[0]

    @pytest.mark.asyncio
    async def test_get_recent_metrics_filtered_by_agent(self):
        """Test filtering metrics by agent_id."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency("agent-1", 0.5)
        await collector.record_latency("agent-2", 1.0)
        await collector.record_latency("agent-1", 0.3)

        metrics = await collector.get_recent_metrics(agent_id="agent-1", limit=10)

        assert len(metrics) == 2
        for m in metrics:
            assert m["agent_id"] == "agent-1"

    @pytest.mark.asyncio
    async def test_get_recent_metrics_respects_limit(self):
        """Test that limit parameter is respected."""
        collector = MetricsCollector(db_pool=None)

        for i in range(10):
            await collector.record_latency(f"agent-{i}", float(i))

        metrics = await collector.get_recent_metrics(limit=5)

        assert len(metrics) == 5

    @pytest.mark.asyncio
    async def test_get_recent_metrics_from_database(self):
        """Test getting metrics from database."""
        mock_rows = [
            {"agent_id": "agent-1", "metric_name": "latency_ms", "value": 100.0},
            {"agent_id": "agent-2", "metric_name": "latency_ms", "value": 200.0},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))

        collector = MetricsCollector(db_pool=mock_pool)

        metrics = await collector.get_recent_metrics(limit=10)

        assert len(metrics) == 2
        mock_conn.fetch.assert_called_once()


class TestLatencyTracker:
    """Tests for LatencyTracker context manager."""

    @pytest.mark.asyncio
    async def test_tracks_latency(self):
        """Test that LatencyTracker records latency."""
        collector = MetricsCollector(db_pool=None)

        async with LatencyTracker(collector, "agent-123"):
            # Simulate some work
            pass

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.agent_id == "agent-123"
        assert metric.metric_name == "latency_ms"
        assert metric.value >= 0

    @pytest.mark.asyncio
    async def test_tracks_latency_with_labels(self):
        """Test that LatencyTracker passes labels."""
        collector = MetricsCollector(db_pool=None)

        async with LatencyTracker(
            collector, "agent-123", labels={"task": "search"}
        ):
            pass

        metric = collector._in_memory_buffer[0]
        assert metric.labels == {"task": "search"}

    @pytest.mark.asyncio
    async def test_records_error_on_exception(self):
        """Test that LatencyTracker records error when exception occurs."""
        collector = MetricsCollector(db_pool=None)

        with pytest.raises(ValueError):
            async with LatencyTracker(collector, "agent-123"):
                raise ValueError("Test error")

        # Should have latency and error metrics
        assert len(collector._in_memory_buffer) == 2

        latency_metric = collector._in_memory_buffer[0]
        assert latency_metric.metric_name == "latency_ms"

        error_metric = collector._in_memory_buffer[1]
        assert error_metric.metric_name == "error_count"
        assert error_metric.labels["error_type"] == "ValueError"
        assert "Test error" in error_metric.labels["error_message"]

    @pytest.mark.asyncio
    async def test_propagates_exception(self):
        """Test that exception is propagated after recording."""
        collector = MetricsCollector(db_pool=None)

        with pytest.raises(RuntimeError, match="Test error"):
            async with LatencyTracker(collector, "agent-123"):
                raise RuntimeError("Test error")

    @pytest.mark.asyncio
    async def test_returns_self(self):
        """Test that context manager returns self."""
        collector = MetricsCollector(db_pool=None)

        async with LatencyTracker(collector, "agent-123") as tracker:
            assert tracker is not None
            assert tracker.agent_id == "agent-123"


class TestIntegration:
    """Integration tests for metrics module."""

    @pytest.mark.asyncio
    async def test_full_agent_workflow(self):
        """Test recording metrics for a complete agent workflow."""
        collector = MetricsCollector(db_pool=None)

        # Record token usage
        await collector.record_tokens(
            agent_id="agent-123",
            input_tokens=500,
            output_tokens=200,
            model_id="claude-sonnet-4.5",
        )

        # Track execution with latency
        async with LatencyTracker(collector, "agent-123"):
            pass

        # Record success
        await collector.record_success("agent-123", "code_generation")

        # Should have: 2 token metrics + 1 latency + 1 success = 4
        assert len(collector._in_memory_buffer) == 4

        metrics = await collector.get_recent_metrics()
        metric_names = [m["metric_name"] for m in metrics]

        assert "tokens_input" in metric_names
        assert "tokens_output" in metric_names
        assert "latency_ms" in metric_names
        assert "success_count" in metric_names

    @pytest.mark.asyncio
    async def test_multiple_agents(self):
        """Test tracking metrics for multiple agents."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency("agent-1", 1.0)
        await collector.record_latency("agent-2", 2.0)
        await collector.record_latency("agent-3", 3.0)

        # Get all
        all_metrics = await collector.get_recent_metrics()
        assert len(all_metrics) == 3

        # Filter by agent
        agent_1_metrics = await collector.get_recent_metrics(agent_id="agent-1")
        assert len(agent_1_metrics) == 1
        assert agent_1_metrics[0]["agent_id"] == "agent-1"
