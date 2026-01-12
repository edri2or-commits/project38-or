"""
Tests for observability module (tracer + metrics).

Tests the OpenTelemetry instrumentation and metrics collection
based on Research Paper #08 (Real-Time Observability Dashboard).
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.observability.metrics import AgentMetric, MetricsCollector
from src.observability.tracer import get_tracer, instrument_tool, sanitize_pii

# =============================================================================
# Tracer Tests
# =============================================================================


class TestTracer:
    """Tests for tracer.py (OpenTelemetry instrumentation)."""

    def test_get_tracer_returns_instance(self):
        """Test that get_tracer() returns a valid tracer."""
        tracer = get_tracer()
        assert tracer is not None
        assert hasattr(tracer, "start_as_current_span")

    def test_sanitize_pii_email(self):
        """Test email redaction."""
        input_text = "Contact user@example.com for details"
        result = sanitize_pii(input_text)
        assert "[EMAIL_REDACTED]" in result
        assert "user@example.com" not in result

    def test_sanitize_pii_phone(self):
        """Test phone number redaction."""
        input_text = "Call me at 555-123-4567"
        result = sanitize_pii(input_text)
        assert "[PHONE_REDACTED]" in result
        assert "555-123-4567" not in result

    def test_sanitize_pii_ssn(self):
        """Test SSN redaction."""
        input_text = "SSN: 123-45-6789"
        result = sanitize_pii(input_text)
        assert "[SSN_REDACTED]" in result
        assert "123-45-6789" not in result

    def test_sanitize_pii_credit_card(self):
        """Test credit card redaction."""
        input_text = "Card: 1234 5678 9012 3456"
        result = sanitize_pii(input_text)
        assert "[CC_REDACTED]" in result
        assert "1234 5678 9012 3456" not in result

    def test_sanitize_pii_dict(self):
        """Test dict sanitization."""
        input_dict = {"email": "test@example.com", "name": "John"}
        result = sanitize_pii(input_dict)
        assert result["email"] == "[EMAIL_REDACTED]"
        assert result["name"] == "John"

    def test_sanitize_pii_list(self):
        """Test list sanitization."""
        input_list = ["user@example.com", "555-123-4567"]
        result = sanitize_pii(input_list)
        assert result[0] == "[EMAIL_REDACTED]"
        assert result[1] == "[PHONE_REDACTED]"

    @pytest.mark.asyncio
    async def test_instrument_tool_async_success(self):
        """Test @instrument_tool decorator on async function (success)."""

        @instrument_tool("test_async_tool")
        async def async_function(value: int):
            return value * 2

        result = await async_function(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_instrument_tool_async_error(self):
        """Test @instrument_tool decorator on async function (error)."""

        @instrument_tool("test_error_tool")
        async def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_function()

    def test_instrument_tool_sync_success(self):
        """Test @instrument_tool decorator on sync function (success)."""

        @instrument_tool("test_sync_tool")
        def sync_function(value: int):
            return value * 2

        result = sync_function(5)
        assert result == 10

    def test_instrument_tool_sync_error(self):
        """Test @instrument_tool decorator on sync function (error)."""

        @instrument_tool("test_sync_error")
        def sync_failing():
            raise RuntimeError("Sync error")

        with pytest.raises(RuntimeError, match="Sync error"):
            sync_failing()

    @pytest.mark.asyncio
    async def test_instrument_tool_captures_kwargs(self):
        """Test that @instrument_tool captures function kwargs."""

        @instrument_tool("kwargs_test")
        async def function_with_kwargs(name: str, age: int):
            return f"{name} is {age}"

        result = await function_with_kwargs(name="Alice", age=30)
        assert result == "Alice is 30"


# =============================================================================
# Metrics Tests
# =============================================================================


class TestAgentMetric:
    """Tests for AgentMetric dataclass."""

    def test_agent_metric_creation(self):
        """Test creating AgentMetric instance."""
        metric = AgentMetric(
            agent_id="agent-123",
            model_id="claude-sonnet-4.5",
            metric_name="latency_ms",
            value=1500.0,
            labels={"environment": "prod"},
            timestamp=datetime.now(UTC),
        )
        assert metric.agent_id == "agent-123"
        assert metric.metric_name == "latency_ms"
        assert metric.value == 1500.0


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    @pytest.mark.asyncio
    async def test_collector_without_db_pool(self):
        """Test MetricsCollector in-memory mode (no DB)."""
        collector = MetricsCollector(db_pool=None)
        assert collector.db_pool is None
        assert len(collector._in_memory_buffer) == 0

    @pytest.mark.asyncio
    async def test_record_metric_in_memory(self):
        """Test recording metric to in-memory buffer."""
        collector = MetricsCollector(db_pool=None)

        metric = AgentMetric(
            agent_id="agent-1",
            model_id="claude",
            metric_name="test_metric",
            value=100.0,
            labels={},
            timestamp=datetime.now(UTC),
        )

        success = await collector.record_metric(metric)
        assert success is True
        assert len(collector._in_memory_buffer) == 1
        assert collector._in_memory_buffer[0] == metric

    @pytest.mark.asyncio
    async def test_record_metric_with_db_pool(self):
        """Test recording metric to database."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        collector = MetricsCollector(db_pool=mock_pool)

        metric = AgentMetric(
            agent_id="agent-1",
            model_id="claude",
            metric_name="latency_ms",
            value=1500.0,
            labels={"env": "test"},
            timestamp=datetime.now(UTC),
        )

        success = await collector.record_metric(metric)
        assert success is True
        mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_latency(self):
        """Test record_latency convenience method."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency("agent-123", 1.5, {"env": "prod"})

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.metric_name == "latency_ms"
        assert metric.value == 1500.0  # Converted to ms

    @pytest.mark.asyncio
    async def test_record_tokens(self):
        """Test record_tokens convenience method."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_tokens("agent-123", 100, 50, "claude-sonnet-4.5")

        assert len(collector._in_memory_buffer) == 2  # input + output
        assert collector._in_memory_buffer[0].metric_name == "tokens_input"
        assert collector._in_memory_buffer[0].value == 100
        assert collector._in_memory_buffer[1].metric_name == "tokens_output"
        assert collector._in_memory_buffer[1].value == 50

    @pytest.mark.asyncio
    async def test_record_success(self):
        """Test record_success convenience method."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_success("agent-123", "search")

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.metric_name == "success_count"
        assert metric.value == 1

    @pytest.mark.asyncio
    async def test_record_error(self):
        """Test record_error convenience method."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_error("agent-123", "ValueError", "Test error message")

        assert len(collector._in_memory_buffer) == 1
        metric = collector._in_memory_buffer[0]
        assert metric.metric_name == "error_count"
        assert metric.value == 1
        assert metric.labels["error_type"] == "ValueError"
        assert "Test error message" in metric.labels["error_message"]

    @pytest.mark.asyncio
    async def test_in_memory_buffer_limit(self):
        """Test that in-memory buffer keeps only last 1000 metrics."""
        collector = MetricsCollector(db_pool=None)

        # Record 1500 metrics
        for i in range(1500):
            await collector.record_latency(f"agent-{i}", 1.0)

        # Should keep only last 1000
        assert len(collector._in_memory_buffer) == 1000

    @pytest.mark.asyncio
    async def test_get_recent_metrics_in_memory(self):
        """Test get_recent_metrics() returns in-memory metrics."""
        collector = MetricsCollector(db_pool=None)

        await collector.record_latency("agent-1", 1.0)
        await collector.record_latency("agent-2", 2.0)

        metrics = await collector.get_recent_metrics(agent_id="agent-1")
        assert len(metrics) == 1
        assert metrics[0]["agent_id"] == "agent-1"

    @pytest.mark.asyncio
    async def test_get_recent_metrics_all(self):
        """Test get_recent_metrics() returns all metrics."""
        collector = MetricsCollector(db_pool=None)

        # Record some metrics
        await collector.record_latency("agent-1", 1.0)
        await collector.record_latency("agent-1", 2.0)
        await collector.record_success("agent-1", "test")
        await collector.record_error("agent-1", "ValueError", "Test error")

        metrics = await collector.get_recent_metrics()
        assert len(metrics) == 4


# =============================================================================
# Integration Tests
# =============================================================================


class TestObservabilityIntegration:
    """Integration tests for tracer + metrics."""

    @pytest.mark.asyncio
    async def test_instrumented_function_records_metrics(self):
        """Test that instrumented function can be combined with metrics."""
        collector = MetricsCollector(db_pool=None)

        @instrument_tool("integrated_tool")
        async def monitored_function(x: int):
            # Simulate work
            await asyncio.sleep(0.1)
            await collector.record_success("agent-test", "integrated_tool")
            return x * 2

        result = await monitored_function(5)
        assert result == 10
        assert len(collector._in_memory_buffer) == 1

    @pytest.mark.asyncio
    async def test_end_to_end_observability(self):
        """Test complete observability flow."""
        collector = MetricsCollector(db_pool=None)

        @instrument_tool("e2e_tool")
        async def agent_task(query: str):
            start = asyncio.get_event_loop().time()
            # Simulate LLM call
            await asyncio.sleep(0.05)
            end = asyncio.get_event_loop().time()

            latency = end - start
            await collector.record_latency("agent-e2e", latency)
            await collector.record_tokens("agent-e2e", 100, 50, "claude")
            await collector.record_success("agent-e2e", "e2e_tool")

            return f"Results for {query}"

        result = await agent_task("test query")
        assert "Results for test query" in result

        # Verify metrics recorded
        metrics = await collector.get_recent_metrics(agent_id="agent-e2e")
        assert len(metrics) >= 4  # latency, tokens_input, tokens_output, success
