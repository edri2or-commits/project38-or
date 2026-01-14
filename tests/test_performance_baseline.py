"""Tests for Performance Baseline Module.

Tests cover:
- Metric snapshot collection
- Baseline statistics calculation
- Anomaly detection
- Trend analysis
- Dashboard data generation
"""

import statistics
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asyncpg import Connection

from src.performance_baseline import (
    Anomaly,
    BaselineStats,
    MetricSnapshot,
    PerformanceBaseline,
    TrendAnalysis,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def database_url():
    """Mock database URL."""
    return "postgresql://user:pass@localhost:5432/test"


@pytest.fixture
def baseline(database_url):
    """Performance baseline instance."""
    return PerformanceBaseline(
        database_url=database_url,
        baseline_window_hours=24,
        collection_interval_minutes=5,
        anomaly_threshold_stddev=3.0,
    )


@pytest.fixture
def mock_snapshot():
    """Mock metric snapshot."""
    return MetricSnapshot(
        timestamp=datetime.now(UTC),
        latency_ms=150.5,
        p95_latency_ms=350.2,
        error_rate_pct=1.5,
        throughput_rph=1200,
        active_agents=5,
        total_tokens_1h=50000,
        cpu_percent=45.5,
        memory_percent=62.3,
    )


@pytest.fixture
def mock_historical_data():
    """Mock historical data for baseline calculation."""
    now = datetime.now(UTC)
    return [
        {
            "timestamp": now - timedelta(hours=i),
            "latency_ms": 150.0 + (i % 10) * 5,
            "p95_latency_ms": 350.0 + (i % 10) * 10,
            "error_rate_pct": 1.5 + (i % 5) * 0.2,
            "throughput_rph": 1200 - (i % 10) * 50,
            "cpu_percent": 45.0 + (i % 8) * 2,
            "memory_percent": 60.0 + (i % 6) * 3,
        }
        for i in range(24)
    ]


# =============================================================================
# METRICSNAPS HOT TESTS
# =============================================================================


def test_metric_snapshot_creation(mock_snapshot):
    """Test MetricSnapshot creation."""
    assert mock_snapshot.latency_ms == 150.5
    assert mock_snapshot.p95_latency_ms == 350.2
    assert mock_snapshot.error_rate_pct == 1.5
    assert mock_snapshot.throughput_rph == 1200
    assert mock_snapshot.active_agents == 5
    assert mock_snapshot.total_tokens_1h == 50000
    assert mock_snapshot.cpu_percent == 45.5
    assert mock_snapshot.memory_percent == 62.3


def test_metric_snapshot_to_dict(mock_snapshot):
    """Test MetricSnapshot serialization."""
    data = mock_snapshot.to_dict()

    assert data["latency_ms"] == 150.5
    assert data["error_rate_pct"] == 1.5
    assert data["throughput_rph"] == 1200
    assert "timestamp" in data
    assert isinstance(data["timestamp"], str)


# =============================================================================
# BASELINE STATS TESTS
# =============================================================================


def test_baseline_stats_creation():
    """Test BaselineStats creation."""
    now = datetime.now(UTC)
    stats = BaselineStats(
        metric_name="latency_ms",
        mean=150.5,
        median=145.2,
        p95=350.8,
        p99=450.3,
        stddev=25.4,
        min_value=100.0,
        max_value=500.0,
        sample_count=100,
        calculated_at=now,
    )

    assert stats.metric_name == "latency_ms"
    assert stats.mean == 150.5
    assert stats.median == 145.2
    assert stats.p95 == 350.8
    assert stats.p99 == 450.3
    assert stats.stddev == 25.4
    assert stats.sample_count == 100


def test_baseline_stats_to_dict():
    """Test BaselineStats serialization."""
    stats = BaselineStats(
        metric_name="error_rate_pct",
        mean=1.5,
        median=1.2,
        p95=3.5,
        p99=5.0,
        stddev=0.8,
        min_value=0.1,
        max_value=6.0,
        sample_count=50,
        calculated_at=datetime.now(UTC),
    )

    data = stats.to_dict()
    assert data["metric_name"] == "error_rate_pct"
    assert data["mean"] == 1.5
    assert data["sample_count"] == 50
    assert "calculated_at" in data


# =============================================================================
# ANOMALY TESTS
# =============================================================================


def test_anomaly_creation():
    """Test Anomaly creation."""
    now = datetime.now(UTC)
    anomaly = Anomaly(
        metric_name="latency_ms",
        timestamp=now,
        current_value=500.0,
        expected_value=150.0,
        deviation_stddev=4.5,
        severity="warning",
        message="Latency is 4.5σ above baseline",
    )

    assert anomaly.metric_name == "latency_ms"
    assert anomaly.current_value == 500.0
    assert anomaly.expected_value == 150.0
    assert anomaly.deviation_stddev == 4.5
    assert anomaly.severity == "warning"


def test_anomaly_to_dict():
    """Test Anomaly serialization."""
    anomaly = Anomaly(
        metric_name="cpu_percent",
        timestamp=datetime.now(UTC),
        current_value=95.0,
        expected_value=45.0,
        deviation_stddev=5.2,
        severity="critical",
        message="CPU is critically high",
    )

    data = anomaly.to_dict()
    assert data["metric_name"] == "cpu_percent"
    assert data["severity"] == "critical"
    assert data["deviation_stddev"] == 5.2


# =============================================================================
# TREND ANALYSIS TESTS
# =============================================================================


def test_trend_analysis_creation():
    """Test TrendAnalysis creation."""
    trend = TrendAnalysis(
        metric_name="latency_ms",
        trend="improving",
        change_pct=-15.5,
        recent_mean=130.0,
        baseline_mean=150.0,
        confidence="high",
    )

    assert trend.metric_name == "latency_ms"
    assert trend.trend == "improving"
    assert trend.change_pct == -15.5
    assert trend.confidence == "high"


def test_trend_analysis_to_dict():
    """Test TrendAnalysis serialization."""
    trend = TrendAnalysis(
        metric_name="error_rate_pct",
        trend="degrading",
        change_pct=25.0,
        recent_mean=2.5,
        baseline_mean=2.0,
        confidence="medium",
    )

    data = trend.to_dict()
    assert data["trend"] == "degrading"
    assert data["change_pct"] == 25.0
    assert data["confidence"] == "medium"


# =============================================================================
# PERFORMANCE BASELINE INITIALIZATION TESTS
# =============================================================================


def test_performance_baseline_init(baseline):
    """Test PerformanceBaseline initialization."""
    assert baseline.baseline_window_hours == 24
    assert baseline.collection_interval_minutes == 5
    assert baseline.anomaly_threshold_stddev == 3.0
    assert baseline.database_url == "postgresql://user:pass@localhost:5432/test"


def test_performance_baseline_custom_params():
    """Test PerformanceBaseline with custom parameters."""
    baseline = PerformanceBaseline(
        database_url="postgresql://custom:pass@localhost:5432/db",
        baseline_window_hours=48,
        collection_interval_minutes=10,
        anomaly_threshold_stddev=2.5,
    )

    assert baseline.baseline_window_hours == 48
    assert baseline.collection_interval_minutes == 10
    assert baseline.anomaly_threshold_stddev == 2.5


# =============================================================================
# COLLECT METRICS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_collect_metrics_success(baseline, mock_snapshot):
    """Test successful metrics collection."""
    mock_conn = AsyncMock(spec=Connection)

    # Mock database queries
    mock_conn.fetchval.side_effect = [
        150.5,  # latency_ms
        350.2,  # p95_latency_ms
        15,  # errors
        1000,  # total_requests
        5,  # active_agents
        50000,  # total_tokens
    ]

    mock_conn.execute = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect, patch(
        "psutil.cpu_percent", return_value=45.5
    ), patch(
        "psutil.virtual_memory", return_value=MagicMock(percent=62.3)
    ):
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        # Override close to be async
        mock_conn.close = AsyncMock()

        snapshot = await baseline.collect_metrics()

        assert isinstance(snapshot, MetricSnapshot)
        assert snapshot.latency_ms == 150.5
        assert snapshot.p95_latency_ms == 350.2
        assert snapshot.error_rate_pct == 1.5  # 15/1000 * 100
        assert snapshot.throughput_rph == 1000
        assert snapshot.active_agents == 5


@pytest.mark.asyncio
async def test_collect_metrics_zero_requests(baseline):
    """Test metrics collection with zero requests."""
    mock_conn = AsyncMock(spec=Connection)

    mock_conn.fetchval.side_effect = [
        0.0,  # latency_ms
        0.0,  # p95_latency_ms
        0,  # errors
        0,  # total_requests (zero to test division)
        0,  # active_agents
        0,  # total_tokens
    ]

    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect, patch(
        "psutil.cpu_percent", return_value=10.0
    ), patch(
        "psutil.virtual_memory", return_value=MagicMock(percent=30.0)
    ):
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        snapshot = await baseline.collect_metrics()

        # Should handle zero requests without error
        assert snapshot.error_rate_pct == 0.0
        assert snapshot.throughput_rph == 0


# =============================================================================
# BASELINE STATS CALCULATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_baseline_stats_success(baseline, mock_historical_data):
    """Test baseline statistics calculation."""
    mock_conn = AsyncMock(spec=Connection)

    # Convert dict to mock records with attribute access
    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    mock_records = [MockRecord(d) for d in mock_historical_data]
    mock_conn.fetch = AsyncMock(return_value=mock_records)
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        stats = await baseline.get_baseline_stats()

        assert isinstance(stats, dict)
        assert "latency_ms" in stats
        assert "error_rate_pct" in stats

        latency_stats = stats["latency_ms"]
        assert isinstance(latency_stats, BaselineStats)
        assert latency_stats.sample_count == 24
        assert latency_stats.mean > 0
        assert latency_stats.stddev >= 0


@pytest.mark.asyncio
async def test_get_baseline_stats_specific_metric(baseline, mock_historical_data):
    """Test baseline calculation for specific metric."""
    mock_conn = AsyncMock(spec=Connection)

    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    mock_records = [MockRecord(d) for d in mock_historical_data]
    mock_conn.fetch = AsyncMock(return_value=mock_records)
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        stats = await baseline.get_baseline_stats(metric_name="latency_ms")

        assert "latency_ms" in stats
        assert len(stats) == 1


@pytest.mark.asyncio
async def test_get_baseline_stats_no_data(baseline):
    """Test baseline calculation with no historical data."""
    mock_conn = AsyncMock(spec=Connection)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        stats = await baseline.get_baseline_stats()

        assert stats == {}


@pytest.mark.asyncio
async def test_get_baseline_stats_invalid_metric(baseline, mock_historical_data):
    """Test baseline calculation with invalid metric name."""
    mock_conn = AsyncMock(spec=Connection)

    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    mock_records = [MockRecord(d) for d in mock_historical_data]
    mock_conn.fetch = AsyncMock(return_value=mock_records)
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        with pytest.raises(ValueError, match="Unknown metric"):
            await baseline.get_baseline_stats(metric_name="invalid_metric")


# =============================================================================
# ANOMALY DETECTION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_detect_anomalies_none(baseline, mock_snapshot, mock_historical_data):
    """Test anomaly detection when no anomalies present."""
    mock_conn = AsyncMock(spec=Connection)

    # Create historical data with similar values to snapshot
    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    # Make historical data close to snapshot values
    historical_data = [
        {
            "timestamp": datetime.now(UTC) - timedelta(hours=i),
            "latency_ms": 150.0 + (i % 5),  # Close to 150.5
            "p95_latency_ms": 350.0 + (i % 5),  # Close to 350.2
            "error_rate_pct": 1.5 + (i % 3) * 0.1,  # Close to 1.5
            "throughput_rph": 1200 - (i % 5) * 10,  # Close to 1200
            "cpu_percent": 45.0 + (i % 3),  # Close to 45.5
            "memory_percent": 62.0 + (i % 3),  # Close to 62.3
        }
        for i in range(24)
    ]

    mock_records = [MockRecord(d) for d in historical_data]
    mock_conn.fetch = AsyncMock(return_value=mock_records)
    mock_conn.fetchval.side_effect = [
        150.5,
        350.2,
        15,
        1000,
        5,
        50000,
    ]  # For collect_metrics
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect, patch(
        "psutil.cpu_percent", return_value=45.5
    ), patch(
        "psutil.virtual_memory", return_value=MagicMock(percent=62.3)
    ):
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        anomalies = await baseline.detect_anomalies()

        # Should detect no significant anomalies
        assert isinstance(anomalies, list)
        assert len(anomalies) == 0


@pytest.mark.asyncio
async def test_detect_anomalies_with_current_snapshot(baseline, mock_historical_data):
    """Test anomaly detection with provided snapshot."""
    mock_conn = AsyncMock(spec=Connection)

    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    mock_records = [MockRecord(d) for d in mock_historical_data]
    mock_conn.fetch = AsyncMock(return_value=mock_records)
    mock_conn.close = AsyncMock()

    # Create snapshot with anomalous values
    anomalous_snapshot = MetricSnapshot(
        timestamp=datetime.now(UTC),
        latency_ms=500.0,  # Much higher than baseline
        p95_latency_ms=800.0,
        error_rate_pct=10.0,  # Much higher
        throughput_rph=1200,
        active_agents=5,
        total_tokens_1h=50000,
        cpu_percent=95.0,  # Much higher
        memory_percent=62.3,
    )

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        anomalies = await baseline.detect_anomalies(current_snapshot=anomalous_snapshot)

        # Should detect anomalies
        assert isinstance(anomalies, list)
        # Likely to detect anomalies for latency_ms, error_rate_pct, cpu_percent
        anomaly_metrics = [a.metric_name for a in anomalies]
        assert any(m in ["latency_ms", "error_rate_pct", "cpu_percent"] for m in anomaly_metrics)


@pytest.mark.asyncio
async def test_detect_anomalies_no_baseline(baseline):
    """Test anomaly detection with no baseline data."""
    mock_conn = AsyncMock(spec=Connection)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        mock_snapshot = MetricSnapshot(
            timestamp=datetime.now(UTC),
            latency_ms=150.0,
            p95_latency_ms=350.0,
            error_rate_pct=1.5,
            throughput_rph=1200,
            active_agents=5,
            total_tokens_1h=50000,
            cpu_percent=45.0,
            memory_percent=62.0,
        )

        anomalies = await baseline.detect_anomalies(current_snapshot=mock_snapshot)

        assert anomalies == []


# =============================================================================
# TREND ANALYSIS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_analyze_trends_stable(baseline, mock_historical_data):
    """Test trend analysis with stable metrics."""
    mock_conn = AsyncMock(spec=Connection)

    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    # Create stable data (same values in baseline and recent)
    stable_data = [
        {
            "timestamp": datetime.now(UTC) - timedelta(hours=i),
            "latency_ms": 150.0,
            "error_rate_pct": 1.5,
            "throughput_rph": 1200,
            "cpu_percent": 45.0,
            "memory_percent": 62.0,
        }
        for i in range(24)
    ]

    mock_records = [MockRecord(d) for d in stable_data]

    # Mock two calls: one for baseline data, one for recent data
    mock_conn.fetch = AsyncMock(side_effect=[mock_records[:18], mock_records[18:]])
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        trends = await baseline.analyze_trends(recent_window_hours=6)

        assert isinstance(trends, list)
        # All trends should be "stable"
        for trend in trends:
            assert trend.trend == "stable"
            assert abs(trend.change_pct) < 5


@pytest.mark.asyncio
async def test_analyze_trends_insufficient_data(baseline):
    """Test trend analysis with insufficient data."""
    mock_conn = AsyncMock(spec=Connection)
    mock_conn.fetch = AsyncMock(side_effect=[[], []])  # No data
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        trends = await baseline.analyze_trends()

        assert trends == []


# =============================================================================
# DASHBOARD DATA TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_dashboard_data(baseline, mock_historical_data):
    """Test dashboard data generation."""
    mock_conn = AsyncMock(spec=Connection)

    class MockRecord:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

        def __getitem__(self, key):
            return getattr(self, key)

    mock_records = [MockRecord(d) for d in mock_historical_data]

    # Mock multiple fetch calls
    mock_conn.fetch = AsyncMock(side_effect=[mock_records, mock_records[:18], mock_records[18:]])
    mock_conn.fetchval.side_effect = [
        150.5,
        350.2,
        15,
        1000,
        5,
        50000,
    ]
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect, patch(
        "psutil.cpu_percent", return_value=45.5
    ), patch(
        "psutil.virtual_memory", return_value=MagicMock(percent=62.3)
    ):
        mock_connect.return_value.__aenter__.return_value = mock_conn
        mock_connect.return_value.__aexit__.return_value = None

        dashboard = await baseline.get_dashboard_data()

        assert "current_metrics" in dashboard
        assert "baselines" in dashboard
        assert "anomalies" in dashboard
        assert "trends" in dashboard
        assert "summary" in dashboard
        assert "generated_at" in dashboard

        summary = dashboard["summary"]
        assert "total_anomalies" in summary
        assert "critical_anomalies" in summary
        assert "degrading_trends" in summary
        assert "improving_trends" in summary
