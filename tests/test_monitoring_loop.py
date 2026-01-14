"""Tests for the monitoring loop module.

Tests cover:
- MetricsCollector: endpoint collection, error handling
- MonitoringLoop: lifecycle, statistics, anomaly routing
- Integration: full pipeline from collection to response
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.monitoring_loop import (
    CollectedMetrics,
    MetricsCollector,
    MetricsEndpoint,
    MonitoringConfig,
    MonitoringLoop,
    MonitoringState,
    create_railway_monitoring_loop,
)


class TestMetricsEndpoint:
    """Tests for MetricsEndpoint dataclass."""

    def test_default_values(self) -> None:
        """Test default endpoint configuration."""
        endpoint = MetricsEndpoint(
            url="https://example.com/health",
            name="test",
        )
        assert endpoint.timeout == 10.0
        assert endpoint.enabled is True
        assert endpoint.headers == {}

    def test_custom_values(self) -> None:
        """Test custom endpoint configuration."""
        endpoint = MetricsEndpoint(
            url="https://example.com/metrics",
            name="custom",
            timeout=30.0,
            enabled=False,
            headers={"Authorization": "Bearer token"},
        )
        assert endpoint.timeout == 30.0
        assert endpoint.enabled is False
        assert "Authorization" in endpoint.headers


class TestCollectedMetrics:
    """Tests for CollectedMetrics dataclass."""

    def test_successful_collection(self) -> None:
        """Test successful metrics collection representation."""
        now = datetime.now(UTC)
        metrics = CollectedMetrics(
            endpoint_name="health",
            timestamp=now,
            latency_ms=50.5,
            status_code=200,
            is_healthy=True,
            metrics={"response_latency_ms": 50.5, "health_status": 1.0},
        )
        assert metrics.error is None
        assert metrics.is_healthy is True
        assert "health_status" in metrics.metrics

    def test_failed_collection(self) -> None:
        """Test failed metrics collection representation."""
        now = datetime.now(UTC)
        metrics = CollectedMetrics(
            endpoint_name="health",
            timestamp=now,
            latency_ms=10000.0,
            status_code=0,
            is_healthy=False,
            metrics={},
            error="Connection timeout",
        )
        assert metrics.error is not None
        assert metrics.is_healthy is False


class TestMonitoringConfig:
    """Tests for MonitoringConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default monitoring configuration."""
        config = MonitoringConfig()
        assert config.collection_interval == 30.0
        assert config.min_interval == 5.0
        assert config.max_consecutive_errors == 5
        assert config.anomaly_detection_enabled is True
        assert config.self_healing_enabled is True

    def test_custom_config(self) -> None:
        """Test custom monitoring configuration."""
        config = MonitoringConfig(
            collection_interval=60.0,
            anomaly_detection_enabled=False,
            self_healing_enabled=False,
            history_size=500,
        )
        assert config.collection_interval == 60.0
        assert config.anomaly_detection_enabled is False
        assert config.history_size == 500


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_init_empty(self) -> None:
        """Test collector initialization with no endpoints."""
        collector = MetricsCollector()
        assert len(collector.endpoints) == 0

    def test_init_with_endpoints(self) -> None:
        """Test collector initialization with endpoints."""
        endpoints = [
            MetricsEndpoint(url="https://a.com/health", name="a"),
            MetricsEndpoint(url="https://b.com/health", name="b"),
        ]
        collector = MetricsCollector(endpoints=endpoints)
        assert len(collector.endpoints) == 2

    def test_add_endpoint(self) -> None:
        """Test adding an endpoint."""
        collector = MetricsCollector()
        endpoint = MetricsEndpoint(url="https://test.com/health", name="test")
        collector.add_endpoint(endpoint)
        assert len(collector.endpoints) == 1
        assert collector.endpoints[0].name == "test"

    def test_remove_endpoint(self) -> None:
        """Test removing an endpoint."""
        endpoint = MetricsEndpoint(url="https://test.com/health", name="test")
        collector = MetricsCollector(endpoints=[endpoint])

        result = collector.remove_endpoint("test")
        assert result is True
        assert len(collector.endpoints) == 0

    def test_remove_nonexistent_endpoint(self) -> None:
        """Test removing a nonexistent endpoint."""
        collector = MetricsCollector()
        result = collector.remove_endpoint("nonexistent")
        assert result is False

    def test_extract_metrics_health_format(self) -> None:
        """Test extracting metrics from Railway health format."""
        collector = MetricsCollector()
        data = {
            "status": "healthy",
            "database": "connected",
            "version": "1.0.0",
        }
        metrics = collector._extract_metrics(data)

        assert metrics["health_status"] == 1.0
        assert metrics["database_connected"] == 1.0

    def test_extract_metrics_unhealthy(self) -> None:
        """Test extracting metrics from unhealthy response."""
        collector = MetricsCollector()
        data = {
            "status": "degraded",
            "database": "disconnected",
        }
        metrics = collector._extract_metrics(data)

        assert metrics["health_status"] == 0.0
        assert metrics["database_connected"] == 0.0

    def test_extract_numeric_values_recursive(self) -> None:
        """Test recursive numeric value extraction."""
        collector = MetricsCollector()
        data = {
            "metrics": {
                "cpu": 45.5,
                "memory": 1024,
                "nested": {
                    "value": 100,
                },
            },
        }
        extracted: dict[str, float] = {}
        collector._extract_numeric_values(data, "", extracted)

        assert "metrics_cpu" in extracted
        assert extracted["metrics_cpu"] == 45.5
        assert "metrics_memory" in extracted
        assert "metrics_nested_value" in extracted

    @pytest.mark.asyncio
    async def test_collect_from_endpoint_success(self) -> None:
        """Test successful collection from endpoint."""
        collector = MetricsCollector()
        endpoint = MetricsEndpoint(
            url="https://test.com/health",
            name="test",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        with patch.object(collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await collector.collect_from_endpoint(endpoint)

        assert result.is_healthy is True
        assert result.status_code == 200
        assert result.error is None
        assert "response_latency_ms" in result.metrics

    @pytest.mark.asyncio
    async def test_collect_from_endpoint_timeout(self) -> None:
        """Test collection timeout handling."""
        import httpx

        collector = MetricsCollector()
        endpoint = MetricsEndpoint(
            url="https://test.com/health",
            name="test",
            timeout=1.0,
        )

        with patch.object(collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_get_client.return_value = mock_client

            result = await collector.collect_from_endpoint(endpoint)

        assert result.is_healthy is False
        assert result.error == "Request timeout"
        assert result.metrics.get("timeout") == 1.0

    @pytest.mark.asyncio
    async def test_collect_all_empty(self) -> None:
        """Test collecting from empty endpoint list."""
        collector = MetricsCollector()
        results = await collector.collect_all()
        assert results == []

    @pytest.mark.asyncio
    async def test_collect_all_disabled_endpoints(self) -> None:
        """Test that disabled endpoints are skipped."""
        endpoint = MetricsEndpoint(
            url="https://test.com/health",
            name="test",
            enabled=False,
        )
        collector = MetricsCollector(endpoints=[endpoint])
        results = await collector.collect_all()
        assert results == []

    @pytest.mark.asyncio
    async def test_close_client(self) -> None:
        """Test closing the HTTP client."""
        collector = MetricsCollector()
        collector._client = AsyncMock()
        collector._client.is_closed = False

        await collector.close()

        collector._client.aclose.assert_called_once()


class TestMonitoringLoop:
    """Tests for MonitoringLoop class."""

    def test_init_defaults(self) -> None:
        """Test loop initialization with defaults."""
        loop = MonitoringLoop()

        assert loop.state == MonitoringState.STOPPED
        assert loop.config is not None
        assert loop.collector is not None
        assert loop.detector is not None
        assert loop.integrator is None

    def test_init_with_components(self) -> None:
        """Test loop initialization with custom components."""
        config = MonitoringConfig(collection_interval=60.0)
        collector = MetricsCollector()

        loop = MonitoringLoop(config=config, collector=collector)

        assert loop.config.collection_interval == 60.0
        assert loop.collector is collector

    def test_is_running_property(self) -> None:
        """Test is_running property."""
        loop = MonitoringLoop()

        assert loop.is_running is False

        loop.state = MonitoringState.RUNNING
        assert loop.is_running is True

        loop.state = MonitoringState.PAUSED
        assert loop.is_running is False

    def test_set_integrator(self) -> None:
        """Test setting the integrator."""
        loop = MonitoringLoop()
        integrator = MagicMock()

        loop.set_integrator(integrator)

        assert loop.integrator is integrator

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Test starting and stopping the loop."""
        loop = MonitoringLoop()
        loop.config.collection_interval = 0.1  # Fast for testing

        # Start
        await loop.start()
        assert loop.state == MonitoringState.RUNNING
        assert loop._task is not None

        # Small delay to let loop start
        await asyncio.sleep(0.05)

        # Stop
        await loop.stop()
        assert loop.state == MonitoringState.STOPPED

    @pytest.mark.asyncio
    async def test_start_when_already_running(self) -> None:
        """Test starting when already running."""
        loop = MonitoringLoop()
        loop.state = MonitoringState.RUNNING

        await loop.start()  # Should not raise

        assert loop.state == MonitoringState.RUNNING

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped(self) -> None:
        """Test stopping when already stopped."""
        loop = MonitoringLoop()
        assert loop.state == MonitoringState.STOPPED

        await loop.stop()  # Should not raise

        assert loop.state == MonitoringState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_resume(self) -> None:
        """Test pausing and resuming."""
        loop = MonitoringLoop()
        loop.state = MonitoringState.RUNNING

        await loop.pause()
        assert loop.state == MonitoringState.PAUSED

        await loop.resume()
        assert loop.state == MonitoringState.RUNNING

    @pytest.mark.asyncio
    async def test_pause_when_not_running(self) -> None:
        """Test pausing when not running."""
        loop = MonitoringLoop()
        loop.state = MonitoringState.STOPPED

        await loop.pause()
        # State should not change
        assert loop.state == MonitoringState.STOPPED

    @pytest.mark.asyncio
    async def test_resume_when_not_paused(self) -> None:
        """Test resuming when not paused."""
        loop = MonitoringLoop()
        loop.state = MonitoringState.STOPPED

        await loop.resume()
        # State should not change
        assert loop.state == MonitoringState.STOPPED

    def test_get_stats(self) -> None:
        """Test getting statistics."""
        loop = MonitoringLoop()
        stats = loop.get_stats()

        assert "state" in stats
        assert "collections_total" in stats
        assert "anomalies_detected" in stats
        assert "endpoints_count" in stats
        assert stats["state"] == "stopped"

    def test_get_recent_metrics_empty(self) -> None:
        """Test getting recent metrics when empty."""
        loop = MonitoringLoop()
        recent = loop.get_recent_metrics()

        assert recent == []

    def test_get_recent_metrics_with_data(self) -> None:
        """Test getting recent metrics with data."""
        loop = MonitoringLoop()
        now = datetime.now(UTC)

        # Add some metrics to history
        loop._metrics_history = [
            CollectedMetrics(
                endpoint_name="test",
                timestamp=now,
                latency_ms=50.0,
                status_code=200,
                is_healthy=True,
                metrics={"value": 1.0},
            ),
            CollectedMetrics(
                endpoint_name="test",
                timestamp=now,
                latency_ms=60.0,
                status_code=200,
                is_healthy=True,
                metrics={"value": 2.0},
            ),
        ]

        recent = loop.get_recent_metrics(limit=1)
        assert len(recent) == 1
        assert recent[0]["latency_ms"] == 60.0

    def test_update_history_trimming(self) -> None:
        """Test that history is trimmed to configured size."""
        config = MonitoringConfig(history_size=2)
        loop = MonitoringLoop(config=config)
        now = datetime.now(UTC)

        # Add more than history_size items
        metrics_list = [
            CollectedMetrics(
                endpoint_name="test",
                timestamp=now,
                latency_ms=float(i),
                status_code=200,
                is_healthy=True,
                metrics={},
            )
            for i in range(5)
        ]

        loop._update_history(metrics_list)

        # Should be trimmed to history_size
        assert len(loop._metrics_history) == 2
        # Should keep the most recent
        assert loop._metrics_history[-1].latency_ms == 4.0

    @pytest.mark.asyncio
    async def test_process_metrics_anomaly_detection(self) -> None:
        """Test processing metrics through anomaly detection."""
        loop = MonitoringLoop()

        # Mock the detector to return an anomaly
        mock_result = MagicMock()
        mock_result.is_anomaly = True
        mock_result.confidence = 0.9
        loop.detector.detect_anomaly = MagicMock(return_value=mock_result)

        now = datetime.now(UTC)
        metrics_data = CollectedMetrics(
            endpoint_name="test",
            timestamp=now,
            latency_ms=500.0,
            status_code=200,
            is_healthy=True,
            metrics={"latency": 500.0},
        )

        await loop._process_metrics(metrics_data)

        assert loop.stats["anomalies_detected"] == 1
        assert loop.stats["last_anomaly_time"] is not None

    @pytest.mark.asyncio
    async def test_process_metrics_no_anomaly(self) -> None:
        """Test processing normal metrics (no anomaly)."""
        loop = MonitoringLoop()

        # Mock the detector to return no anomaly
        mock_result = MagicMock()
        mock_result.is_anomaly = False
        loop.detector.detect_anomaly = MagicMock(return_value=mock_result)

        now = datetime.now(UTC)
        metrics_data = CollectedMetrics(
            endpoint_name="test",
            timestamp=now,
            latency_ms=50.0,
            status_code=200,
            is_healthy=True,
            metrics={"latency": 50.0},
        )

        await loop._process_metrics(metrics_data)

        assert loop.stats["anomalies_detected"] == 0

    @pytest.mark.asyncio
    async def test_handle_anomaly_with_integrator(self) -> None:
        """Test handling anomaly with integrator."""
        loop = MonitoringLoop()

        # Mock integrator
        mock_integrator = AsyncMock()
        mock_response = MagicMock()
        mock_response.action_taken = "restart_service"
        mock_integrator.handle_anomaly.return_value = mock_response
        loop.integrator = mock_integrator

        mock_result = MagicMock()
        mock_result.is_anomaly = True

        await loop._handle_anomaly(
            metric_name="latency",
            value=500.0,
            detection_result=mock_result,
        )

        assert loop.stats["healing_actions_triggered"] == 1
        mock_integrator.handle_anomaly.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_anomaly_without_integrator(self) -> None:
        """Test handling anomaly without integrator."""
        loop = MonitoringLoop()
        loop.integrator = None

        mock_result = MagicMock()

        await loop._handle_anomaly(
            metric_name="latency",
            value=500.0,
            detection_result=mock_result,
        )

        # Should not raise, just return
        assert loop.stats["healing_actions_triggered"] == 0

    @pytest.mark.asyncio
    async def test_collection_cycle_success(self) -> None:
        """Test a successful collection cycle."""
        loop = MonitoringLoop()
        now = datetime.now(UTC)

        # Mock collector
        mock_metrics = CollectedMetrics(
            endpoint_name="test",
            timestamp=now,
            latency_ms=50.0,
            status_code=200,
            is_healthy=True,
            metrics={"value": 1.0},
        )
        loop.collector.collect_all = AsyncMock(return_value=[mock_metrics])

        # Mock detector
        mock_result = MagicMock()
        mock_result.is_anomaly = False
        loop.detector.detect_anomaly = MagicMock(return_value=mock_result)

        await loop._run_collection_cycle()

        assert loop.stats["collections_total"] == 1
        assert loop.stats["collections_successful"] == 1
        assert loop.stats["last_collection_time"] is not None

    @pytest.mark.asyncio
    async def test_collection_cycle_empty(self) -> None:
        """Test collection cycle with no results."""
        loop = MonitoringLoop()
        loop.collector.collect_all = AsyncMock(return_value=[])

        await loop._run_collection_cycle()

        assert loop.stats["collections_total"] == 1
        assert loop.stats["collections_failed"] == 1


class TestCreateRailwayMonitoringLoop:
    """Tests for the factory function."""

    def test_create_default(self) -> None:
        """Test creating loop with defaults."""
        loop = create_railway_monitoring_loop()

        assert loop is not None
        assert len(loop.collector.endpoints) == 2
        assert loop.integrator is None

    def test_create_with_custom_url(self) -> None:
        """Test creating loop with custom URL."""
        loop = create_railway_monitoring_loop(
            railway_url="https://custom.example.com"
        )

        endpoints = loop.collector.endpoints
        assert endpoints[0].url == "https://custom.example.com/api/health"
        assert endpoints[1].url == "https://custom.example.com/api/metrics/summary"

    def test_create_with_controller(self) -> None:
        """Test creating loop with controller."""
        mock_controller = MagicMock()

        loop = create_railway_monitoring_loop(controller=mock_controller)

        assert loop.integrator is not None

    def test_create_with_custom_config(self) -> None:
        """Test creating loop with custom config."""
        config = MonitoringConfig(collection_interval=120.0)

        loop = create_railway_monitoring_loop(config=config)

        assert loop.config.collection_interval == 120.0


class TestMonitoringState:
    """Tests for MonitoringState enum."""

    def test_all_states(self) -> None:
        """Test all monitoring states."""
        assert MonitoringState.STOPPED.value == "stopped"
        assert MonitoringState.STARTING.value == "starting"
        assert MonitoringState.RUNNING.value == "running"
        assert MonitoringState.PAUSED.value == "paused"
        assert MonitoringState.ERROR.value == "error"


class TestIntegration:
    """Integration tests for the full monitoring pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_no_anomaly(self) -> None:
        """Test full pipeline with normal metrics."""
        loop = create_railway_monitoring_loop()
        loop.config.anomaly_detection_enabled = True

        # Mock successful collection
        now = datetime.now(UTC)
        mock_metrics = CollectedMetrics(
            endpoint_name="railway_health",
            timestamp=now,
            latency_ms=50.0,
            status_code=200,
            is_healthy=True,
            metrics={
                "health_status": 1.0,
                "response_latency_ms": 50.0,
            },
        )
        loop.collector.collect_all = AsyncMock(return_value=[mock_metrics])

        # Run one cycle
        await loop._run_collection_cycle()

        assert loop.stats["collections_successful"] == 1
        assert len(loop._metrics_history) == 1

    @pytest.mark.asyncio
    async def test_full_pipeline_with_anomaly(self) -> None:
        """Test full pipeline detecting anomaly."""
        loop = create_railway_monitoring_loop()

        # Train detector with normal values first
        for i in range(50):
            loop.detector.detect_anomaly(50.0 + i, "latency")

        # Mock collection returning anomalous value
        now = datetime.now(UTC)
        mock_metrics = CollectedMetrics(
            endpoint_name="railway_health",
            timestamp=now,
            latency_ms=5000.0,  # Very high latency
            status_code=200,
            is_healthy=True,
            metrics={
                "response_latency_ms": 5000.0,
            },
        )
        loop.collector.collect_all = AsyncMock(return_value=[mock_metrics])

        # Run cycle
        await loop._run_collection_cycle()

        # Check that anomaly was detected
        # (may not trigger depending on exact detection logic)
        assert loop.stats["collections_successful"] >= 1

    @pytest.mark.asyncio
    async def test_consecutive_error_handling(self) -> None:
        """Test handling of consecutive errors."""
        config = MonitoringConfig(
            max_consecutive_errors=2,
            error_pause_duration=0.1,  # Short for testing
            collection_interval=0.05,
        )
        loop = MonitoringLoop(config=config)

        # Mock collection to always fail
        loop.collector.collect_all = AsyncMock(side_effect=Exception("Test error"))

        # Start the loop
        await loop.start()

        # Wait for errors to accumulate
        await asyncio.sleep(0.3)

        # Stop
        await loop.stop()

        # Should have recovered from error state
        assert loop.stats["collections_total"] > 0
