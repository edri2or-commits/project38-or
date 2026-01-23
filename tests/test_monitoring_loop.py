"""Tests for MonitoringLoop module.

Tests the continuous health monitoring module in src/monitoring_loop.py.
Covers:
- MonitoringState enum
- MetricsEndpoint, CollectedMetrics, MonitoringConfig dataclasses
- MetricsCollector class
- MonitoringLoop class
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMonitoringState:
    """Tests for MonitoringState enum."""

    def test_monitoring_state_values(self):
        """Test that MonitoringState has expected values."""
        from src.monitoring_loop import MonitoringState

        assert MonitoringState.STOPPED.value == "stopped"
        assert MonitoringState.STARTING.value == "starting"
        assert MonitoringState.RUNNING.value == "running"
        assert MonitoringState.PAUSED.value == "paused"
        assert MonitoringState.ERROR.value == "error"


class TestMetricsEndpoint:
    """Tests for MetricsEndpoint dataclass."""

    def test_default_values(self):
        """Test MetricsEndpoint default values."""
        from src.monitoring_loop import MetricsEndpoint

        endpoint = MetricsEndpoint(url="https://example.com/health", name="test")

        assert endpoint.url == "https://example.com/health"
        assert endpoint.name == "test"
        assert endpoint.timeout == 10.0
        assert endpoint.enabled is True
        assert endpoint.headers == {}

    def test_custom_values(self):
        """Test MetricsEndpoint with custom values."""
        from src.monitoring_loop import MetricsEndpoint

        endpoint = MetricsEndpoint(
            url="https://example.com/metrics",
            name="metrics",
            timeout=30.0,
            enabled=False,
            headers={"Authorization": "Bearer token"},
        )

        assert endpoint.timeout == 30.0
        assert endpoint.enabled is False
        assert endpoint.headers == {"Authorization": "Bearer token"}


class TestCollectedMetrics:
    """Tests for CollectedMetrics dataclass."""

    def test_collected_metrics_creation(self):
        """Test CollectedMetrics creation."""
        from src.monitoring_loop import CollectedMetrics

        now = datetime.now(UTC)
        metrics = CollectedMetrics(
            endpoint_name="test",
            timestamp=now,
            latency_ms=50.5,
            status_code=200,
            is_healthy=True,
            metrics={"cpu": 50.0, "memory": 70.0},
        )

        assert metrics.endpoint_name == "test"
        assert metrics.timestamp == now
        assert metrics.latency_ms == 50.5
        assert metrics.status_code == 200
        assert metrics.is_healthy is True
        assert metrics.metrics == {"cpu": 50.0, "memory": 70.0}
        assert metrics.error is None

    def test_collected_metrics_with_error(self):
        """Test CollectedMetrics with error."""
        from src.monitoring_loop import CollectedMetrics

        metrics = CollectedMetrics(
            endpoint_name="test",
            timestamp=datetime.now(UTC),
            latency_ms=100.0,
            status_code=500,
            is_healthy=False,
            metrics={},
            error="Server error",
        )

        assert metrics.is_healthy is False
        assert metrics.error == "Server error"


class TestMonitoringConfig:
    """Tests for MonitoringConfig dataclass."""

    def test_default_config(self):
        """Test MonitoringConfig default values."""
        from src.monitoring_loop import MonitoringConfig

        config = MonitoringConfig()

        assert config.collection_interval == 30.0
        assert config.min_interval == 5.0
        assert config.max_consecutive_errors == 5
        assert config.error_pause_duration == 60.0
        assert config.anomaly_detection_enabled is True
        assert config.self_healing_enabled is True
        assert config.history_size == 1000

    def test_custom_config(self):
        """Test MonitoringConfig with custom values."""
        from src.monitoring_loop import MonitoringConfig

        config = MonitoringConfig(
            collection_interval=60.0,
            max_consecutive_errors=3,
            anomaly_detection_enabled=False,
        )

        assert config.collection_interval == 60.0
        assert config.max_consecutive_errors == 3
        assert config.anomaly_detection_enabled is False


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_init_empty(self):
        """Test MetricsCollector initialization without endpoints."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()

        assert collector.endpoints == []

    def test_init_with_endpoints(self):
        """Test MetricsCollector initialization with endpoints."""
        from src.monitoring_loop import MetricsCollector, MetricsEndpoint

        endpoints = [
            MetricsEndpoint(url="https://example.com/health", name="health"),
            MetricsEndpoint(url="https://example.com/metrics", name="metrics"),
        ]
        collector = MetricsCollector(endpoints=endpoints)

        assert len(collector.endpoints) == 2

    def test_add_endpoint(self):
        """Test adding endpoint to collector."""
        from src.monitoring_loop import MetricsCollector, MetricsEndpoint

        collector = MetricsCollector()
        endpoint = MetricsEndpoint(url="https://example.com/health", name="health")

        collector.add_endpoint(endpoint)

        assert len(collector.endpoints) == 1
        assert collector.endpoints[0].name == "health"

    def test_remove_endpoint(self):
        """Test removing endpoint from collector."""
        from src.monitoring_loop import MetricsCollector, MetricsEndpoint

        endpoint = MetricsEndpoint(url="https://example.com/health", name="health")
        collector = MetricsCollector(endpoints=[endpoint])

        result = collector.remove_endpoint("health")

        assert result is True
        assert len(collector.endpoints) == 0

    def test_remove_nonexistent_endpoint(self):
        """Test removing nonexistent endpoint."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()

        result = collector.remove_endpoint("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_collect_from_endpoint_timeout(self):
        """Test metric collection timeout."""
        import httpx

        from src.monitoring_loop import MetricsCollector, MetricsEndpoint

        collector = MetricsCollector()
        endpoint = MetricsEndpoint(url="https://example.com/health", name="health")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            result = await collector.collect_from_endpoint(endpoint)

            assert result.is_healthy is False
            assert result.error == "Request timeout"

    @pytest.mark.asyncio
    async def test_collect_all_no_endpoints(self):
        """Test collect_all with no endpoints."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()

        result = await collector.collect_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the collector."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()

        # Create a mock client
        mock_client = AsyncMock()
        mock_client.is_closed = False
        collector._client = mock_client

        await collector.close()

        mock_client.aclose.assert_called_once()

    def test_extract_metrics_health_status(self):
        """Test _extract_metrics with health status."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()
        data = {"status": "healthy", "database": "connected"}

        metrics = collector._extract_metrics(data)

        assert metrics["health_status"] == 1.0
        assert metrics["database_connected"] == 1.0

    def test_extract_metrics_unhealthy(self):
        """Test _extract_metrics with unhealthy status."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()
        data = {"status": "degraded", "database": "disconnected"}

        metrics = collector._extract_metrics(data)

        assert metrics["health_status"] == 0.0
        assert metrics["database_connected"] == 0.0

    def test_extract_numeric_values(self):
        """Test _extract_numeric_values from nested data."""
        from src.monitoring_loop import MetricsCollector

        collector = MetricsCollector()
        data = {"cpu": 50.5, "memory": {"used": 70, "free": 30}}
        metrics: dict[str, float] = {}

        collector._extract_numeric_values(data, "", metrics)

        assert metrics["cpu"] == 50.5
        assert metrics["memory_used"] == 70.0
        assert metrics["memory_free"] == 30.0


class TestMonitoringLoop:
    """Tests for MonitoringLoop class."""

    def test_init_defaults(self):
        """Test MonitoringLoop initialization with defaults."""
        from src.monitoring_loop import MonitoringLoop, MonitoringState

        loop = MonitoringLoop()

        assert loop.config is not None
        assert loop.collector is not None
        assert loop.detector is not None
        assert loop.integrator is None
        assert loop.state == MonitoringState.STOPPED

    def test_init_with_config(self):
        """Test MonitoringLoop initialization with custom config."""
        from src.monitoring_loop import MonitoringConfig, MonitoringLoop

        config = MonitoringConfig(collection_interval=60.0)
        loop = MonitoringLoop(config=config)

        assert loop.config.collection_interval == 60.0

    def test_is_running_property(self):
        """Test is_running property."""
        from src.monitoring_loop import MonitoringLoop, MonitoringState

        loop = MonitoringLoop()

        assert loop.is_running is False

        loop.state = MonitoringState.RUNNING
        assert loop.is_running is True

    def test_set_integrator(self):
        """Test setting integrator."""
        from src.monitoring_loop import MonitoringLoop

        loop = MonitoringLoop()
        mock_integrator = MagicMock()

        loop.set_integrator(mock_integrator)

        assert loop.integrator == mock_integrator

    @pytest.mark.asyncio
    async def test_start_when_already_running(self):
        """Test start when already running does nothing."""
        from src.monitoring_loop import MonitoringLoop, MonitoringState

        loop = MonitoringLoop()
        loop.state = MonitoringState.RUNNING

        await loop.start()

        # Should still be running, no error
        assert loop.state == MonitoringState.RUNNING

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped(self):
        """Test stop when already stopped does nothing."""
        from src.monitoring_loop import MonitoringLoop, MonitoringState

        loop = MonitoringLoop()
        assert loop.state == MonitoringState.STOPPED

        await loop.stop()

        assert loop.state == MonitoringState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """Test pause and resume."""
        from src.monitoring_loop import MonitoringLoop, MonitoringState

        loop = MonitoringLoop()
        loop.state = MonitoringState.RUNNING

        await loop.pause()
        assert loop.state == MonitoringState.PAUSED

        await loop.resume()
        assert loop.state == MonitoringState.RUNNING

    @pytest.mark.asyncio
    async def test_pause_when_not_running(self):
        """Test pause when not running."""
        from src.monitoring_loop import MonitoringLoop, MonitoringState

        loop = MonitoringLoop()
        assert loop.state == MonitoringState.STOPPED

        await loop.pause()

        # Should not change state
        assert loop.state == MonitoringState.STOPPED

    def test_get_stats(self):
        """Test get_stats returns correct structure."""
        from src.monitoring_loop import MetricsEndpoint, MonitoringLoop

        loop = MonitoringLoop()
        loop.collector.add_endpoint(
            MetricsEndpoint(url="https://example.com", name="test")
        )

        stats = loop.get_stats()

        assert "collections_total" in stats
        assert "collections_successful" in stats
        assert "anomalies_detected" in stats
        assert "state" in stats
        assert stats["endpoints_count"] == 1
        assert stats["enabled_endpoints"] == 1

    def test_get_recent_metrics_empty(self):
        """Test get_recent_metrics when history is empty."""
        from src.monitoring_loop import MonitoringLoop

        loop = MonitoringLoop()

        metrics = loop.get_recent_metrics()

        assert metrics == []

    def test_get_recent_metrics_with_history(self):
        """Test get_recent_metrics with history."""
        from src.monitoring_loop import CollectedMetrics, MonitoringLoop

        loop = MonitoringLoop()
        loop._metrics_history = [
            CollectedMetrics(
                endpoint_name="test",
                timestamp=datetime.now(UTC),
                latency_ms=50.0,
                status_code=200,
                is_healthy=True,
                metrics={"cpu": 50.0},
            )
        ]

        metrics = loop.get_recent_metrics()

        assert len(metrics) == 1
        assert metrics[0]["endpoint"] == "test"
        assert metrics[0]["is_healthy"] is True

    def test_update_history(self):
        """Test _update_history."""
        from src.monitoring_loop import CollectedMetrics, MonitoringConfig, MonitoringLoop

        config = MonitoringConfig(history_size=3)
        loop = MonitoringLoop(config=config)

        # Add more than history_size
        for i in range(5):
            loop._update_history([
                CollectedMetrics(
                    endpoint_name=f"test_{i}",
                    timestamp=datetime.now(UTC),
                    latency_ms=50.0,
                    status_code=200,
                    is_healthy=True,
                    metrics={},
                )
            ])

        # Should be trimmed to history_size
        assert len(loop._metrics_history) == 3

    @pytest.mark.asyncio
    async def test_run_collection_cycle_no_endpoints(self):
        """Test _run_collection_cycle with no endpoints."""
        from src.monitoring_loop import MonitoringLoop

        loop = MonitoringLoop()

        await loop._run_collection_cycle()

        assert loop.stats["collections_total"] == 1
        assert loop.stats["collections_failed"] == 1


class TestCreateRailwayMonitoringLoop:
    """Tests for create_railway_monitoring_loop factory."""

    def test_creates_loop_with_endpoints(self):
        """Test factory creates loop with Railway endpoints."""
        from src.monitoring_loop import create_railway_monitoring_loop

        loop = create_railway_monitoring_loop(railway_url="https://test.railway.app")

        assert len(loop.collector.endpoints) == 2
        assert loop.collector.endpoints[0].name == "railway_health"
        assert loop.collector.endpoints[1].name == "railway_metrics"

    def test_creates_loop_with_config(self):
        """Test factory uses provided config."""
        from src.monitoring_loop import MonitoringConfig, create_railway_monitoring_loop

        config = MonitoringConfig(collection_interval=120.0)
        loop = create_railway_monitoring_loop(config=config)

        assert loop.config.collection_interval == 120.0
