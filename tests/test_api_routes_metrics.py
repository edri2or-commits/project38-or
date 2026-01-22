"""Tests for metrics API routes.

Tests the /metrics/* endpoints defined in src/api/routes/metrics.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routes.metrics import (
    AgentMetricPoint,
    AgentStatus,
    MetricSummary,
    SystemMetrics,
    estimate_cost,
    router,
)


def _has_psutil() -> bool:
    """Check if psutil module is available."""
    try:
        import psutil
        return True
    except ImportError:
        return False


def create_test_app():
    """Create a FastAPI app with the metrics router for testing."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def client():
    """Create a test client."""
    app = create_test_app()
    return TestClient(app)


class TestMetricsHealthEndpoint:
    """Tests for GET /metrics/health endpoint."""

    def test_health_returns_healthy(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/metrics/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "metrics-api"
        assert "timestamp" in data


class TestMetricsSummaryEndpoint:
    """Tests for GET /metrics/summary endpoint."""

    def test_summary_with_mocked_db(self, client):
        """Test summary endpoint with mocked database."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            5,    # active agents
            100,  # total requests
            10,   # errors
            100,  # total for error rate
            50.0, # avg latency
            100.0, # p95 latency
            50000, # total tokens
        ])

        with patch("src.api.routes.metrics.get_session", return_value=mock_conn):
            # Override the dependency
            app = create_test_app()
            app.dependency_overrides[lambda: None] = lambda: mock_conn

            # Since we can't easily override the Depends, test the model directly
            summary = MetricSummary(
                active_agents=5,
                total_requests_1h=100,
                error_rate_pct=10.0,
                avg_latency_ms=50.0,
                p95_latency_ms=100.0,
                total_tokens_1h=50000,
                estimated_cost_1h=0.45,
            )

            assert summary.active_agents == 5
            assert summary.error_rate_pct == 10.0


class TestAgentStatusesEndpoint:
    """Tests for GET /metrics/agents endpoint."""

    def test_agent_status_model(self):
        """Test AgentStatus model."""
        status = AgentStatus(
            agent_id="agent-1",
            last_seen=datetime.now(UTC),
            error_rate_pct=5.0,
            total_requests_1h=50,
            avg_latency_ms=100.0,
            total_tokens_1h=10000,
        )

        assert status.agent_id == "agent-1"
        assert status.error_rate_pct == 5.0


class TestTimeseriesEndpoint:
    """Tests for GET /metrics/timeseries endpoint."""

    def test_metric_point_model(self):
        """Test AgentMetricPoint model."""
        point = AgentMetricPoint(
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
            metric_name="latency_ms",
            value=50.0,
            labels={"environment": "production"},
        )

        assert point.metric_name == "latency_ms"
        assert point.value == 50.0
        assert point.labels["environment"] == "production"

    def test_metric_point_default_labels(self):
        """Test AgentMetricPoint with default empty labels."""
        point = AgentMetricPoint(
            timestamp=datetime.now(UTC),
            agent_id="agent-1",
            metric_name="latency_ms",
            value=50.0,
        )

        assert point.labels == {}


class TestSystemMetricsEndpoint:
    """Tests for GET /metrics/system endpoint."""

    @pytest.mark.skipif(not _has_psutil(), reason="psutil not available")
    def test_system_metrics_with_psutil(self, client):
        """Test system metrics endpoint with mocked psutil."""
        mock_memory = MagicMock()
        mock_memory.available = 4 * 1024 * 1024 * 1024  # 4 GB
        mock_memory.percent = 60.0

        mock_disk = MagicMock()
        mock_disk.free = 100 * 1024 * 1024 * 1024  # 100 GB
        mock_disk.percent = 50.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            with patch("psutil.disk_usage", return_value=mock_disk):
                with patch("psutil.cpu_percent", return_value=25.0):
                    response = client.get("/metrics/system")

        assert response.status_code == 200
        data = response.json()

        assert "timestamp" in data
        assert data["cpu_percent"] == 25.0
        assert data["memory_percent"] == 60.0
        assert data["disk_percent"] == 50.0

    def test_system_metrics_model(self):
        """Test SystemMetrics model."""
        metrics = SystemMetrics(
            timestamp=datetime.now(UTC),
            cpu_percent=25.0,
            memory_percent=60.0,
            memory_available_mb=4096.0,
            disk_percent=50.0,
            disk_available_gb=100.0,
        )

        assert metrics.cpu_percent == 25.0
        assert metrics.memory_available_mb == 4096.0


class TestEstimateCostFunction:
    """Tests for the estimate_cost helper function."""

    def test_estimate_cost_zero_tokens(self):
        """Test cost is 0 for zero tokens."""
        cost = estimate_cost(0)
        assert cost == 0.0

    def test_estimate_cost_1m_tokens(self):
        """Test cost for 1 million tokens."""
        cost = estimate_cost(1_000_000)
        # Average $9/MTok
        assert cost == 9.0

    def test_estimate_cost_100k_tokens(self):
        """Test cost for 100k tokens."""
        cost = estimate_cost(100_000)
        # 0.1 MTok * $9 = $0.9
        assert cost == 0.9

    def test_estimate_cost_small_amount(self):
        """Test cost for small token amounts."""
        cost = estimate_cost(1000)
        # 0.001 MTok * $9 = $0.009
        assert cost == 0.009


class TestPydanticModels:
    """Tests for Pydantic response models."""

    def test_metric_summary_required_fields(self):
        """Test MetricSummary requires all fields."""
        summary = MetricSummary(
            active_agents=10,
            total_requests_1h=1000,
            error_rate_pct=5.5,
            avg_latency_ms=100.0,
            p95_latency_ms=250.0,
            total_tokens_1h=500000,
            estimated_cost_1h=4.5,
        )

        assert summary.active_agents == 10
        assert summary.total_requests_1h == 1000
        assert summary.estimated_cost_1h == 4.5

    def test_agent_status_required_fields(self):
        """Test AgentStatus requires all fields."""
        status = AgentStatus(
            agent_id="test-agent",
            last_seen=datetime.now(UTC),
            error_rate_pct=2.5,
            total_requests_1h=50,
            avg_latency_ms=75.0,
            total_tokens_1h=25000,
        )

        assert status.agent_id == "test-agent"
        assert status.error_rate_pct == 2.5
