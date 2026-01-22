"""Tests for monitoring API routes.

Tests the /api/monitoring/* endpoints defined in src/api/routes/monitoring.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.monitoring_loop import MonitoringConfig, MonitoringLoop, MonitoringState


def create_test_app():
    """Create a FastAPI app with the monitoring router for testing."""
    from fastapi import FastAPI

    from src.api.routes.monitoring import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_monitoring_loop():
    """Create a mock MonitoringLoop for testing."""
    loop = MagicMock(spec=MonitoringLoop)
    loop.state = MonitoringState.STOPPED
    loop.is_running = False
    loop.config = MonitoringConfig()
    loop.collector = MagicMock()
    loop.collector.endpoints = []

    loop.get_stats.return_value = {
        "state": "stopped",
        "endpoints_count": 2,
        "enabled_endpoints": 2,
        "collections_total": 100,
        "collections_successful": 95,
        "collections_failed": 5,
        "anomalies_detected": 3,
        "healing_actions_triggered": 1,
        "last_collection_time": "2026-01-22T12:00:00Z",
        "last_anomaly_time": "2026-01-22T11:30:00Z",
    }

    loop.get_recent_metrics.return_value = [
        {
            "endpoint": "railway_health",
            "timestamp": "2026-01-22T12:00:00Z",
            "latency_ms": 50.0,
            "is_healthy": True,
            "metrics": {"response_latency_ms": 50.0},
            "error": None,
        }
    ]

    return loop


@pytest.fixture
def client(mock_monitoring_loop):
    """Create a test client with mocked monitoring loop."""
    app = create_test_app()

    with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
        yield TestClient(app)


class TestMonitoringStatusEndpoint:
    """Tests for GET /api/monitoring/status endpoint."""

    def test_get_status_returns_stats(self, client, mock_monitoring_loop):
        """Test status endpoint returns monitoring statistics."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/status")

        assert response.status_code == 200
        data = response.json()

        assert data["state"] == "stopped"
        assert data["is_running"] is False
        assert data["endpoints_count"] == 2
        assert data["collections_total"] == 100
        assert data["anomalies_detected"] == 3


class TestMonitoringStartEndpoint:
    """Tests for POST /api/monitoring/start endpoint."""

    def test_start_when_stopped(self, client, mock_monitoring_loop):
        """Test starting monitoring when it's stopped."""
        mock_monitoring_loop.state = MonitoringState.STOPPED

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "starting"
        assert "collection_interval" in data

    def test_start_when_already_running(self, client, mock_monitoring_loop):
        """Test starting monitoring when already running."""
        mock_monitoring_loop.state = MonitoringState.RUNNING

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_running"


class TestMonitoringStopEndpoint:
    """Tests for POST /api/monitoring/stop endpoint."""

    def test_stop_when_running(self, client, mock_monitoring_loop):
        """Test stopping monitoring when running."""
        mock_monitoring_loop.state = MonitoringState.RUNNING
        mock_monitoring_loop.stop = AsyncMock()

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

    def test_stop_when_already_stopped(self, client, mock_monitoring_loop):
        """Test stopping monitoring when already stopped."""
        mock_monitoring_loop.state = MonitoringState.STOPPED

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_stopped"


class TestMonitoringPauseResumeEndpoints:
    """Tests for pause and resume endpoints."""

    def test_pause_when_running(self, client, mock_monitoring_loop):
        """Test pausing when monitoring is running."""
        mock_monitoring_loop.state = MonitoringState.RUNNING
        mock_monitoring_loop.pause = AsyncMock()

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/pause")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    def test_pause_when_not_running(self, client, mock_monitoring_loop):
        """Test pausing when monitoring is not running fails."""
        mock_monitoring_loop.state = MonitoringState.STOPPED

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/pause")

        assert response.status_code == 400
        assert "Cannot pause" in response.json()["detail"]

    def test_resume_when_paused(self, client, mock_monitoring_loop):
        """Test resuming when monitoring is paused."""
        mock_monitoring_loop.state = MonitoringState.PAUSED
        mock_monitoring_loop.resume = AsyncMock()

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_resume_when_not_paused(self, client, mock_monitoring_loop):
        """Test resuming when not paused fails."""
        mock_monitoring_loop.state = MonitoringState.RUNNING

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/resume")

        assert response.status_code == 400
        assert "Cannot resume" in response.json()["detail"]


class TestRecentMetricsEndpoint:
    """Tests for GET /api/monitoring/metrics/recent endpoint."""

    def test_get_recent_metrics(self, client, mock_monitoring_loop):
        """Test getting recent metrics."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/metrics/recent?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "count" in data
        assert "metrics" in data
        mock_monitoring_loop.get_recent_metrics.assert_called_with(10)

    def test_get_recent_metrics_default_limit(self, client, mock_monitoring_loop):
        """Test default limit is 10."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/metrics/recent")

        assert response.status_code == 200
        mock_monitoring_loop.get_recent_metrics.assert_called_with(10)

    def test_get_recent_metrics_invalid_limit_too_high(self, client, mock_monitoring_loop):
        """Test limit > 100 fails."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/metrics/recent?limit=150")

        assert response.status_code == 400
        assert "between 1 and 100" in response.json()["detail"]

    def test_get_recent_metrics_invalid_limit_zero(self, client, mock_monitoring_loop):
        """Test limit = 0 fails."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/metrics/recent?limit=0")

        assert response.status_code == 400


class TestEndpointsManagement:
    """Tests for endpoint management endpoints."""

    def test_list_endpoints(self, client, mock_monitoring_loop):
        """Test listing configured endpoints."""
        mock_endpoint = MagicMock()
        mock_endpoint.name = "test_endpoint"
        mock_endpoint.url = "https://example.com/health"
        mock_endpoint.timeout = 10.0
        mock_endpoint.enabled = True
        mock_monitoring_loop.collector.endpoints = [mock_endpoint]

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/endpoints")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 1
        assert data["endpoints"][0]["name"] == "test_endpoint"

    def test_add_endpoint(self, client, mock_monitoring_loop):
        """Test adding a new endpoint."""
        mock_monitoring_loop.collector.endpoints = []

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post(
                "/api/monitoring/endpoints",
                json={
                    "url": "https://new-service.com/health",
                    "name": "new_service",
                    "timeout": 15.0,
                    "enabled": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "added"
        assert data["endpoint"]["name"] == "new_service"

    def test_add_duplicate_endpoint_fails(self, client, mock_monitoring_loop):
        """Test adding duplicate endpoint name fails."""
        mock_endpoint = MagicMock()
        mock_endpoint.name = "existing"
        mock_monitoring_loop.collector.endpoints = [mock_endpoint]

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post(
                "/api/monitoring/endpoints",
                json={"url": "https://example.com", "name": "existing"},
            )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_remove_endpoint(self, client, mock_monitoring_loop):
        """Test removing an endpoint."""
        mock_monitoring_loop.collector.remove_endpoint.return_value = True

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.delete("/api/monitoring/endpoints/test_endpoint")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "removed"
        assert data["name"] == "test_endpoint"

    def test_remove_nonexistent_endpoint_fails(self, client, mock_monitoring_loop):
        """Test removing non-existent endpoint fails."""
        mock_monitoring_loop.collector.remove_endpoint.return_value = False

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.delete("/api/monitoring/endpoints/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_config(self, client, mock_monitoring_loop):
        """Test getting current configuration."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.get("/api/monitoring/config")

        assert response.status_code == 200
        data = response.json()

        assert "collection_interval" in data
        assert "anomaly_detection_enabled" in data
        assert "self_healing_enabled" in data
        assert "max_consecutive_errors" in data

    def test_update_config(self, client, mock_monitoring_loop):
        """Test updating configuration."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.put(
                "/api/monitoring/config",
                json={
                    "collection_interval": 60.0,
                    "anomaly_detection_enabled": False,
                    "self_healing_enabled": False,
                    "max_consecutive_errors": 10,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["config"]["collection_interval"] == 60.0

    def test_update_config_validation(self, client, mock_monitoring_loop):
        """Test config validation (interval must be 5-300)."""
        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.put(
                "/api/monitoring/config",
                json={"collection_interval": 1.0},  # Too low
            )

        assert response.status_code == 422  # Validation error


class TestCollectNowEndpoint:
    """Tests for POST /api/monitoring/collect-now endpoint."""

    def test_collect_now(self, client, mock_monitoring_loop):
        """Test immediate collection trigger."""
        mock_collected = MagicMock()
        mock_collected.endpoint_name = "test"
        mock_collected.latency_ms = 45.0
        mock_collected.is_healthy = True
        mock_collected.metrics = {"response_latency_ms": 45.0}
        mock_collected.error = None

        mock_monitoring_loop.collector.collect_all = AsyncMock(return_value=[mock_collected])

        with patch("src.api.routes.monitoring.get_monitoring_loop", return_value=mock_monitoring_loop):
            response = client.post("/api/monitoring/collect-now")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "collected"
        assert data["count"] == 1
        assert data["results"][0]["endpoint"] == "test"
        assert data["results"][0]["is_healthy"] is True
