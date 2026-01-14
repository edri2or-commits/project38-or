"""Tests for Railway cost monitoring module.

Tests cover:
- Pricing configuration
- Cost estimation
- Usage tracking
- Budget alerts
- Optimization recommendations
- Report generation
"""

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock google module before importing cost_monitor
sys.modules["google"] = MagicMock()
sys.modules["google.api_core"] = MagicMock()
sys.modules["google.api_core.exceptions"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.secretmanager"] = MagicMock()

from src.cost_monitor import (  # noqa: E402
    CostEstimate,
    CostMonitor,
    RailwayPricing,
    UsageSnapshot,
    estimate_monthly_from_daily,
    format_cost,
)

# =============================================================================
# PRICING TESTS
# =============================================================================


class TestRailwayPricing:
    """Tests for RailwayPricing configuration."""

    def test_hobby_pricing(self):
        """Test hobby plan pricing values."""
        pricing = RailwayPricing.hobby()

        assert pricing.plan_name == "Hobby"
        assert pricing.base_monthly_cost == 5.0
        assert pricing.vcpu_per_minute == 0.000231
        assert pricing.memory_per_gb_minute == 0.000231
        assert pricing.egress_per_gb == 0.10

    def test_pro_pricing(self):
        """Test pro plan pricing values."""
        pricing = RailwayPricing.pro()

        assert pricing.plan_name == "Pro"
        assert pricing.base_monthly_cost == 20.0
        assert pricing.vcpu_per_minute == 0.000231
        assert pricing.memory_per_gb_minute == 0.000231

    def test_custom_pricing(self):
        """Test custom pricing configuration."""
        pricing = RailwayPricing(
            base_monthly_cost=50.0,
            vcpu_per_minute=0.0005,
            memory_per_gb_minute=0.0003,
            egress_per_gb=0.15,
            plan_name="Enterprise",
        )

        assert pricing.plan_name == "Enterprise"
        assert pricing.base_monthly_cost == 50.0


# =============================================================================
# COST ESTIMATE TESTS
# =============================================================================


class TestCostEstimate:
    """Tests for CostEstimate dataclass."""

    def test_to_dict(self):
        """Test cost estimate serialization."""
        now = datetime.now(UTC)
        estimate = CostEstimate(
            period_start=now - timedelta(days=30),
            period_end=now,
            vcpu_minutes=10000,
            memory_gb_minutes=5000,
            egress_gb=2.5,
            vcpu_cost=2.31,
            memory_cost=1.155,
            egress_cost=0.25,
            base_cost=5.0,
            total_cost=8.715,
        )

        result = estimate.to_dict()

        assert "period_start" in result
        assert "period_end" in result
        assert result["usage"]["vcpu_minutes"] == 10000
        assert result["usage"]["memory_gb_minutes"] == 5000
        assert result["usage"]["egress_gb"] == 2.5
        assert abs(result["costs"]["total"] - 8.715) < 0.01  # Rounded
        assert result["currency"] == "USD"


# =============================================================================
# USAGE SNAPSHOT TESTS
# =============================================================================


class TestUsageSnapshot:
    """Tests for UsageSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a usage snapshot."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            service_name="web-service",
            cpu_percent=45.5,
            memory_mb=512.0,
            request_count=1000,
        )

        assert snapshot.service_name == "web-service"
        assert snapshot.cpu_percent == 45.5
        assert snapshot.memory_mb == 512.0
        assert snapshot.request_count == 1000


# =============================================================================
# COST MONITOR TESTS
# =============================================================================


class TestCostMonitor:
    """Tests for CostMonitor class."""

    @pytest.fixture
    def mock_railway_client(self):
        """Create mock Railway client."""
        client = MagicMock()
        client.get_deployment_metrics = AsyncMock(
            return_value={
                "cpuUsage": 25.0,
                "memoryUsage": 256.0,
                "requestCount": 500,
                "responseTime": 150.0,
            }
        )
        return client

    @pytest.fixture
    def monitor(self, mock_railway_client):
        """Create CostMonitor with mocked client."""
        return CostMonitor(
            railway_client=mock_railway_client,
            pricing=RailwayPricing.hobby(),
        )

    @pytest.mark.asyncio
    async def test_get_current_usage(self, monitor, mock_railway_client):
        """Test getting current usage metrics."""
        snapshot = await monitor.get_current_usage("deployment-123")

        assert snapshot.cpu_percent == 25.0
        assert snapshot.memory_mb == 256.0
        assert snapshot.request_count == 500
        mock_railway_client.get_deployment_metrics.assert_called_once_with(
            "deployment-123"
        )

    @pytest.mark.asyncio
    async def test_usage_history_tracking(self, monitor):
        """Test that usage history is maintained."""
        await monitor.get_current_usage("deployment-123")
        await monitor.get_current_usage("deployment-123")
        await monitor.get_current_usage("deployment-123")

        assert len(monitor._usage_history) == 3

    @pytest.mark.asyncio
    async def test_usage_history_limit(self, monitor):
        """Test that usage history doesn't exceed max size."""
        monitor._max_history_size = 5

        for _ in range(10):
            await monitor.get_current_usage("deployment-123")

        assert len(monitor._usage_history) == 5

    def test_estimate_cost_basic(self, monitor):
        """Test basic cost estimation."""
        estimate = monitor.estimate_cost(
            vcpu_minutes=1000,
            memory_gb_minutes=500,
            egress_gb=1.0,
            period_days=30,
        )

        # Base cost: $5.00
        # vCPU: 1000 * 0.000231 = $0.231
        # Memory: 500 * 0.000231 = $0.1155
        # Egress: 1 * 0.10 = $0.10
        # Total: ~$5.45

        assert estimate.base_cost == 5.0
        assert abs(estimate.vcpu_cost - 0.231) < 0.001
        assert abs(estimate.memory_cost - 0.1155) < 0.001
        assert estimate.egress_cost == 0.10
        assert estimate.total_cost > 5.4

    def test_estimate_cost_prorated(self, monitor):
        """Test prorated base cost for partial month."""
        estimate = monitor.estimate_cost(
            vcpu_minutes=0,
            memory_gb_minutes=0,
            egress_gb=0,
            period_days=15,
        )

        # 15/30 = 0.5 * $5.00 = $2.50
        assert estimate.base_cost == 2.5
        assert estimate.total_cost == 2.5

    @pytest.mark.asyncio
    async def test_get_current_month_cost(self, monitor):
        """Test current month cost projection."""
        estimate = await monitor.get_current_month_cost("deployment-123")

        assert estimate.period_end is not None
        assert estimate.total_cost > 0  # At least base cost

    @pytest.mark.asyncio
    async def test_budget_not_exceeded(self, monitor):
        """Test budget check when under budget."""
        exceeded, cost = await monitor.is_budget_exceeded(
            "deployment-123", budget=100.0
        )

        assert exceeded is False
        assert cost > 0

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, monitor):
        """Test budget check when over budget."""
        # Set very low budget to trigger alert
        exceeded, cost = await monitor.is_budget_exceeded(
            "deployment-123", budget=0.01
        )

        assert exceeded is True
        assert cost > 0.01


class TestCostOptimizationRecommendations:
    """Tests for cost optimization recommendations."""

    @pytest.fixture
    def monitor(self):
        """Create CostMonitor with mocked client."""
        client = MagicMock()
        return CostMonitor(railway_client=client)

    def test_low_cpu_recommendation(self, monitor):
        """Test recommendation for underutilized CPU."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            service_name="test",
            cpu_percent=5.0,  # Very low
            memory_mb=512.0,
            request_count=100,
        )

        recommendations = monitor.get_cost_optimization_recommendations(snapshot)

        assert len(recommendations) >= 1
        cpu_recs = [r for r in recommendations if r["category"] == "cpu"]
        assert len(cpu_recs) == 1
        assert cpu_recs[0]["priority"] == "high"
        assert "reducing" in cpu_recs[0]["title"].lower()

    def test_high_cpu_recommendation(self, monitor):
        """Test recommendation for high CPU utilization."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            service_name="test",
            cpu_percent=90.0,  # Very high
            memory_mb=512.0,
            request_count=100,
        )

        recommendations = monitor.get_cost_optimization_recommendations(snapshot)

        cpu_recs = [r for r in recommendations if r["category"] == "cpu"]
        assert len(cpu_recs) == 1
        assert "scaling up" in cpu_recs[0]["title"].lower()

    def test_low_memory_recommendation(self, monitor):
        """Test recommendation for underutilized memory."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            service_name="test",
            cpu_percent=50.0,
            memory_mb=128.0,  # Very low
            request_count=100,
        )

        recommendations = monitor.get_cost_optimization_recommendations(snapshot)

        memory_recs = [r for r in recommendations if r["category"] == "memory"]
        assert len(memory_recs) == 1
        assert "reducing" in memory_recs[0]["title"].lower()

    def test_optimal_usage_recommendation(self, monitor):
        """Test recommendation when usage is optimized."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            service_name="test",
            cpu_percent=50.0,  # Moderate
            memory_mb=512.0,  # Moderate
            request_count=1000,
        )

        recommendations = monitor.get_cost_optimization_recommendations(snapshot)

        assert len(recommendations) == 1
        assert recommendations[0]["category"] == "general"
        assert "optimized" in recommendations[0]["title"].lower()


class TestUsageTrends:
    """Tests for usage trend analysis."""

    @pytest.fixture
    def monitor(self):
        """Create CostMonitor with usage history."""
        client = MagicMock()
        monitor = CostMonitor(railway_client=client)

        # Add some history
        now = datetime.now(UTC)
        for i in range(10):
            monitor._usage_history.append(
                UsageSnapshot(
                    timestamp=now - timedelta(minutes=10 - i),
                    service_name="test",
                    cpu_percent=20 + i * 5,  # Increasing
                    memory_mb=512.0,
                    request_count=100 * i,
                )
            )

        return monitor

    def test_cpu_trend_increasing(self, monitor):
        """Test detecting increasing CPU trend."""
        trend = monitor.get_usage_trend("cpu", hours=1)

        assert trend["trend"] == "increasing"
        assert trend["min"] < trend["max"]
        assert trend["avg"] > 0

    def test_empty_history(self):
        """Test trend with empty history."""
        client = MagicMock()
        monitor = CostMonitor(railway_client=client)

        trend = monitor.get_usage_trend("cpu", hours=1)

        assert trend["trend"] == "stable"
        assert trend["min"] == 0
        assert trend["max"] == 0


class TestCostReport:
    """Tests for cost report generation."""

    @pytest.fixture
    def monitor(self):
        """Create CostMonitor with usage history."""
        client = MagicMock()
        monitor = CostMonitor(railway_client=client)

        # Add usage history for recommendations
        monitor._usage_history.append(
            UsageSnapshot(
                timestamp=datetime.now(UTC),
                service_name="test",
                cpu_percent=50.0,
                memory_mb=512.0,
                request_count=1000,
            )
        )

        return monitor

    def test_generate_report(self, monitor):
        """Test generating cost report."""
        estimate = monitor.estimate_cost(
            vcpu_minutes=1000,
            memory_gb_minutes=500,
            egress_gb=1.0,
        )

        report = monitor.generate_cost_report(estimate)

        assert "generated_at" in report
        assert report["pricing_plan"] == "Hobby"
        assert "estimate" in report
        assert "budget_status" in report
        assert report["budget_status"]["status"] == "ok"

    def test_report_with_recommendations(self, monitor):
        """Test report includes recommendations."""
        estimate = monitor.estimate_cost(
            vcpu_minutes=1000,
            memory_gb_minutes=500,
            egress_gb=1.0,
        )

        report = monitor.generate_cost_report(estimate, include_recommendations=True)

        assert "recommendations" in report
        assert "trends" in report

    def test_report_budget_warning(self, monitor):
        """Test report shows budget warning."""
        # Create high-cost estimate
        estimate = monitor.estimate_cost(
            vcpu_minutes=100000,
            memory_gb_minutes=100000,
            egress_gb=100.0,
        )

        report = monitor.generate_cost_report(estimate)

        assert report["budget_status"]["status"] in ["warning", "alert"]


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_cost_usd(self):
        """Test formatting cost as USD."""
        assert format_cost(12.345) == "$12.35"
        assert format_cost(0.50) == "$0.50"
        assert format_cost(100.0) == "$100.00"

    def test_format_cost_other_currency(self):
        """Test formatting with other currency."""
        assert format_cost(12.34, "EUR") == "12.34 EUR"

    def test_estimate_monthly_from_daily(self):
        """Test monthly projection from daily cost."""
        # $1/day = $30/month
        assert estimate_monthly_from_daily(1.0, days_elapsed=1) == 30.0

        # $10 over 5 days = $2/day = $60/month
        assert estimate_monthly_from_daily(10.0, days_elapsed=5) == 60.0
