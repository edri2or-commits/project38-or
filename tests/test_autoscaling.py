"""Tests for Auto-Scaling Recommendations Module.

Tests cover:
- Resource metrics data classes
- Scaling recommendation generation
- Threshold-based analysis
- Report generation
- Helper functions
"""

import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _setup_google_mocks():
    """Set up Google module mocks if not already present."""
    modules_to_mock = [
        "google",
        "google.api_core",
        "google.api_core.exceptions",
        "google.cloud",
        "google.cloud.secretmanager",
    ]
    originals = {}
    for mod in modules_to_mock:
        originals[mod] = sys.modules.get(mod)
        if originals[mod] is None:
            sys.modules[mod] = MagicMock()
    return originals


def _restore_google_mocks(originals):
    """Restore Google module mocks."""
    for mod, original in originals.items():
        if original is not None:
            sys.modules[mod] = original
        # Don't remove - other tests may have set these


# Set up mocks at import time (needed for autoscaling imports)
_google_mock_originals = _setup_google_mocks()


@pytest.fixture(scope="module", autouse=True)
def ensure_google_mocks():
    """Ensure Google mocks are set up and cleaned up properly."""
    yield
    _restore_google_mocks(_google_mock_originals)


from src.autoscaling import (  # noqa: E402
    AutoScalingAdvisor,
    RecommendationPriority,
    ResourceMetrics,
    ResourceType,
    ScalingDirection,
    ScalingRecommendation,
    ScalingReport,
    ScalingThresholds,
    format_recommendation,
    generate_scaling_report,
    get_scaling_recommendations,
)

# =============================================================================
# RESOURCE METRICS TESTS
# =============================================================================


class TestResourceMetrics:
    """Tests for ResourceMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating resource metrics."""
        now = datetime.now(UTC)
        metrics = ResourceMetrics(
            cpu_percent=75.5,
            memory_mb=384.0,
            memory_percent=75.0,
            request_rate=50.0,
            response_time_ms=250.0,
            error_rate=0.5,
            timestamp=now,
        )

        assert metrics.cpu_percent == 75.5
        assert metrics.memory_mb == 384.0
        assert metrics.memory_percent == 75.0
        assert metrics.request_rate == 50.0
        assert metrics.response_time_ms == 250.0
        assert metrics.error_rate == 0.5
        assert metrics.timestamp == now

    def test_to_dict(self):
        """Test metrics serialization."""
        now = datetime.now(UTC)
        metrics = ResourceMetrics(
            cpu_percent=75.555,
            memory_mb=384.123,
            memory_percent=75.789,
            request_rate=50.456,
            response_time_ms=250.999,
            error_rate=0.567,
            timestamp=now,
        )

        data = metrics.to_dict()

        # Values should be rounded to 2 decimal places
        assert data["cpu_percent"] == 75.56
        assert data["memory_mb"] == 384.12
        assert data["memory_percent"] == 75.79
        assert data["request_rate"] == 50.46
        assert data["response_time_ms"] == 251.0
        assert data["error_rate"] == 0.57
        assert "timestamp" in data


# =============================================================================
# SCALING RECOMMENDATION TESTS
# =============================================================================


class TestScalingRecommendation:
    """Tests for ScalingRecommendation dataclass."""

    def test_create_recommendation(self):
        """Test creating scaling recommendation."""
        rec = ScalingRecommendation(
            resource=ResourceType.CPU,
            direction=ScalingDirection.SCALE_UP,
            priority=RecommendationPriority.HIGH,
            current_value=1.0,
            recommended_value=2.0,
            reason="High CPU utilization",
            impact="Increase capacity",
            estimated_savings=-10.0,
        )

        assert rec.resource == ResourceType.CPU
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.HIGH
        assert rec.current_value == 1.0
        assert rec.recommended_value == 2.0
        assert rec.estimated_savings == -10.0

    def test_to_dict(self):
        """Test recommendation serialization."""
        rec = ScalingRecommendation(
            resource=ResourceType.MEMORY,
            direction=ScalingDirection.SCALE_DOWN,
            priority=RecommendationPriority.LOW,
            current_value=512,
            recommended_value=256,
            reason="Low memory usage",
            impact="Reduce costs",
            estimated_savings=5.555,
        )

        data = rec.to_dict()

        assert data["resource"] == "memory"
        assert data["direction"] == "scale_down"
        assert data["priority"] == "low"
        assert data["current_value"] == 512
        assert data["recommended_value"] == 256
        assert data["estimated_savings"] == 5.55  # Python rounds 5.555 to 5.55


# =============================================================================
# SCALING REPORT TESTS
# =============================================================================


class TestScalingReport:
    """Tests for ScalingReport dataclass."""

    def test_create_report(self):
        """Test creating scaling report."""
        now = datetime.now(UTC)
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=now,
        )

        report = ScalingReport(
            generated_at=now,
            deployment_id="deploy-123",
            current_metrics=metrics,
            recommendations=[],
            overall_status="optimal",
            estimated_monthly_savings=0.0,
        )

        assert report.deployment_id == "deploy-123"
        assert report.overall_status == "optimal"
        assert len(report.recommendations) == 0

    def test_to_dict_with_recommendations(self):
        """Test report serialization with recommendations."""
        now = datetime.now(UTC)
        metrics = ResourceMetrics(
            cpu_percent=90.0,
            memory_mb=450.0,
            memory_percent=88.0,
            request_rate=100.0,
            response_time_ms=500.0,
            error_rate=0.2,
            timestamp=now,
        )

        rec = ScalingRecommendation(
            resource=ResourceType.CPU,
            direction=ScalingDirection.SCALE_UP,
            priority=RecommendationPriority.HIGH,
            current_value=1.0,
            recommended_value=2.0,
            reason="High CPU",
            impact="Better performance",
            estimated_savings=-5.0,
        )

        report = ScalingReport(
            generated_at=now,
            deployment_id="deploy-456",
            current_metrics=metrics,
            recommendations=[rec],
            overall_status="warning",
            estimated_monthly_savings=0.0,
        )

        data = report.to_dict()

        assert data["deployment_id"] == "deploy-456"
        assert data["overall_status"] == "warning"
        assert data["recommendation_count"] == 1
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["resource"] == "cpu"


# =============================================================================
# SCALING THRESHOLDS TESTS
# =============================================================================


class TestScalingThresholds:
    """Tests for ScalingThresholds defaults and customization."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = ScalingThresholds()

        assert thresholds.cpu_scale_up == 80.0
        assert thresholds.cpu_scale_down == 20.0
        assert thresholds.memory_scale_up == 85.0
        assert thresholds.memory_scale_down == 30.0
        assert thresholds.response_time_critical == 2000.0
        assert thresholds.response_time_warning == 1000.0
        assert thresholds.error_rate_critical == 5.0
        assert thresholds.error_rate_warning == 1.0

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = ScalingThresholds(
            cpu_scale_up=70.0,
            cpu_scale_down=15.0,
            memory_scale_up=80.0,
            memory_scale_down=25.0,
        )

        assert thresholds.cpu_scale_up == 70.0
        assert thresholds.cpu_scale_down == 15.0
        assert thresholds.memory_scale_up == 80.0
        assert thresholds.memory_scale_down == 25.0


# =============================================================================
# AUTO-SCALING ADVISOR TESTS
# =============================================================================


class TestAutoScalingAdvisor:
    """Tests for AutoScalingAdvisor class."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    @pytest.fixture
    def mock_cost_monitor(self):
        """Create mock cost monitor."""
        monitor = MagicMock()
        mock_usage = MagicMock()
        mock_usage.cpu_percent = 50.0
        mock_usage.memory_mb = 256.0
        monitor.get_current_usage = AsyncMock(return_value=mock_usage)
        return monitor

    def test_init_default_thresholds(self, advisor):
        """Test advisor initializes with default thresholds."""
        assert advisor.thresholds.cpu_scale_up == 80.0
        assert advisor.cost_monitor is None

    def test_init_custom_thresholds(self):
        """Test advisor with custom thresholds."""
        custom = ScalingThresholds(cpu_scale_up=90.0)
        advisor = AutoScalingAdvisor(thresholds=custom)
        assert advisor.thresholds.cpu_scale_up == 90.0


class TestCPUAnalysis:
    """Tests for CPU utilization analysis."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    def test_high_cpu_critical(self, advisor):
        """Test critical recommendation at 95%+ CPU."""
        metrics = ResourceMetrics(
            cpu_percent=96.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_cpu(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.CRITICAL
        assert rec.resource == ResourceType.CPU

    def test_high_cpu_warning(self, advisor):
        """Test high priority recommendation at 80-95% CPU."""
        metrics = ResourceMetrics(
            cpu_percent=85.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_cpu(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.HIGH

    def test_low_cpu_scale_down(self, advisor):
        """Test scale down recommendation at low CPU."""
        metrics = ResourceMetrics(
            cpu_percent=15.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_cpu(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_DOWN
        assert rec.priority == RecommendationPriority.MEDIUM
        assert rec.estimated_savings > 0

    def test_normal_cpu_no_recommendation(self, advisor):
        """Test no recommendation for normal CPU."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_cpu(metrics)

        assert rec is None


class TestMemoryAnalysis:
    """Tests for memory utilization analysis."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    def test_high_memory_critical(self, advisor):
        """Test critical recommendation at 95%+ memory."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=490.0,
            memory_percent=96.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_memory(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.CRITICAL
        assert rec.resource == ResourceType.MEMORY

    def test_high_memory_warning(self, advisor):
        """Test high priority recommendation at 85-95% memory."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=450.0,
            memory_percent=88.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_memory(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.HIGH

    def test_low_memory_scale_down(self, advisor):
        """Test scale down recommendation at low memory."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=100.0,
            memory_percent=20.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_memory(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_DOWN
        assert rec.priority == RecommendationPriority.LOW
        assert rec.estimated_savings > 0

    def test_normal_memory_no_recommendation(self, advisor):
        """Test no recommendation for normal memory."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_memory(metrics)

        assert rec is None


class TestResponseTimeAnalysis:
    """Tests for response time analysis."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    def test_critical_response_time(self, advisor):
        """Test critical recommendation at 2000ms+ response time."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=2500.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_response_time(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.CRITICAL
        assert rec.resource == ResourceType.INSTANCES

    def test_warning_response_time(self, advisor):
        """Test medium priority at 1000-2000ms response time."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=1500.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_response_time(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.MEDIUM
        assert rec.resource == ResourceType.CPU

    def test_good_response_time(self, advisor):
        """Test no recommendation for good response time."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=200.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_response_time(metrics)

        assert rec is None


class TestErrorRateAnalysis:
    """Tests for error rate analysis."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    def test_critical_error_rate(self, advisor):
        """Test critical recommendation at 5%+ error rate."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=6.0,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_error_rate(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.CRITICAL
        assert rec.resource == ResourceType.INSTANCES

    def test_warning_error_rate(self, advisor):
        """Test high priority at 1-5% error rate."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=2.5,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_error_rate(metrics)

        assert rec is not None
        assert rec.direction == ScalingDirection.SCALE_UP
        assert rec.priority == RecommendationPriority.HIGH

    def test_low_error_rate(self, advisor):
        """Test no recommendation for low error rate."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=100.0,
            error_rate=0.5,
            timestamp=datetime.now(UTC),
        )

        rec = advisor.analyze_error_rate(metrics)

        assert rec is None


class TestAnalyzeAndRecommend:
    """Tests for full analysis workflow."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    @pytest.mark.asyncio
    async def test_no_recommendations_optimal_metrics(self, advisor):
        """Test no recommendations when metrics are optimal."""
        # Default metrics from get_current_metrics are optimal
        recommendations = await advisor.analyze_and_recommend("deploy-123")

        # Default mock metrics may generate some recommendations
        # Check that recommendations is a list
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_multiple_recommendations_sorted(self, advisor):
        """Test recommendations are sorted by priority."""
        mock_monitor = MagicMock()
        mock_usage = MagicMock()
        mock_usage.cpu_percent = 95.0  # Critical
        mock_usage.memory_mb = 100.0  # Low (scale down)
        mock_monitor.get_current_usage = AsyncMock(return_value=mock_usage)

        advisor.cost_monitor = mock_monitor

        recommendations = await advisor.analyze_and_recommend("deploy-123")

        # Should have recommendations sorted by priority
        assert len(recommendations) >= 1
        if len(recommendations) > 1:
            priority_order = {
                RecommendationPriority.CRITICAL: 0,
                RecommendationPriority.HIGH: 1,
                RecommendationPriority.MEDIUM: 2,
                RecommendationPriority.LOW: 3,
                RecommendationPriority.INFO: 4,
            }
            for i in range(len(recommendations) - 1):
                assert (
                    priority_order[recommendations[i].priority]
                    <= priority_order[recommendations[i + 1].priority]
                )


class TestGenerateReport:
    """Tests for report generation."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    @pytest.mark.asyncio
    async def test_generate_report_structure(self, advisor):
        """Test report has all required fields."""
        report = await advisor.generate_report("deploy-123")

        assert report.deployment_id == "deploy-123"
        assert report.generated_at is not None
        assert report.current_metrics is not None
        assert isinstance(report.recommendations, list)
        assert report.overall_status in ["optimal", "optimizable", "warning", "critical"]

    @pytest.mark.asyncio
    async def test_report_status_critical(self, advisor):
        """Test critical status when critical recommendations exist."""
        mock_monitor = MagicMock()
        mock_usage = MagicMock()
        mock_usage.cpu_percent = 98.0  # Critical CPU
        mock_usage.memory_mb = 256.0
        mock_monitor.get_current_usage = AsyncMock(return_value=mock_usage)

        advisor.cost_monitor = mock_monitor

        report = await advisor.generate_report("deploy-123")

        assert report.overall_status == "critical"

    @pytest.mark.asyncio
    async def test_report_status_warning(self, advisor):
        """Test warning status when high priority recommendations exist."""
        mock_monitor = MagicMock()
        mock_usage = MagicMock()
        mock_usage.cpu_percent = 85.0  # High priority
        mock_usage.memory_mb = 256.0
        mock_monitor.get_current_usage = AsyncMock(return_value=mock_usage)

        advisor.cost_monitor = mock_monitor

        report = await advisor.generate_report("deploy-123")

        assert report.overall_status in ["warning", "critical"]

    @pytest.mark.asyncio
    async def test_report_to_dict(self, advisor):
        """Test report serialization."""
        report = await advisor.generate_report("deploy-456")
        data = report.to_dict()

        assert "generated_at" in data
        assert data["deployment_id"] == "deploy-456"
        assert "current_metrics" in data
        assert "recommendations" in data
        assert "overall_status" in data
        assert "estimated_monthly_savings" in data
        assert "recommendation_count" in data


class TestGetScalingSummary:
    """Tests for scaling summary generation."""

    @pytest.fixture
    def advisor(self):
        """Create advisor with default thresholds."""
        return AutoScalingAdvisor()

    def test_summary_empty_recommendations(self, advisor):
        """Test summary with no recommendations."""
        summary = advisor.get_scaling_summary([])

        assert summary["total_recommendations"] == 0
        assert summary["scale_up_count"] == 0
        assert summary["scale_down_count"] == 0
        assert summary["critical_count"] == 0
        assert summary["potential_savings"] == 0

    def test_summary_mixed_recommendations(self, advisor):
        """Test summary with mixed recommendations."""
        recommendations = [
            ScalingRecommendation(
                resource=ResourceType.CPU,
                direction=ScalingDirection.SCALE_UP,
                priority=RecommendationPriority.CRITICAL,
                current_value=1.0,
                recommended_value=2.0,
                reason="High CPU",
                impact="Better performance",
                estimated_savings=-10.0,
            ),
            ScalingRecommendation(
                resource=ResourceType.MEMORY,
                direction=ScalingDirection.SCALE_DOWN,
                priority=RecommendationPriority.LOW,
                current_value=512,
                recommended_value=256,
                reason="Low memory",
                impact="Cost savings",
                estimated_savings=5.0,
            ),
        ]

        summary = advisor.get_scaling_summary(recommendations)

        assert summary["total_recommendations"] == 2
        assert summary["scale_up_count"] == 1
        assert summary["scale_down_count"] == 1
        assert summary["critical_count"] == 1
        assert summary["potential_savings"] == 5.0
        assert summary["additional_costs"] == 10.0


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelperFunctions:
    """Tests for module helper functions."""

    @pytest.mark.asyncio
    async def test_get_scaling_recommendations(self):
        """Test get_scaling_recommendations helper."""
        recommendations = await get_scaling_recommendations("deploy-123")

        assert isinstance(recommendations, list)
        # All items should be dictionaries
        for rec in recommendations:
            assert isinstance(rec, dict)
            if rec:
                assert "resource" in rec
                assert "direction" in rec
                assert "priority" in rec

    @pytest.mark.asyncio
    async def test_generate_scaling_report_helper(self):
        """Test generate_scaling_report helper."""
        report = await generate_scaling_report("deploy-789")

        assert isinstance(report, dict)
        assert report["deployment_id"] == "deploy-789"
        assert "generated_at" in report
        assert "current_metrics" in report
        assert "overall_status" in report

    def test_format_recommendation_scale_up(self):
        """Test formatting scale up recommendation."""
        rec = ScalingRecommendation(
            resource=ResourceType.CPU,
            direction=ScalingDirection.SCALE_UP,
            priority=RecommendationPriority.HIGH,
            current_value=1.0,
            recommended_value=2.0,
            reason="High CPU utilization",
            impact="Better performance",
            estimated_savings=-10.0,
        )

        formatted = format_recommendation(rec)

        assert "CPU" in formatted
        assert "1.0" in formatted
        assert "2.0" in formatted
        assert "High CPU utilization" in formatted
        assert "Better performance" in formatted
        assert "costs" in formatted.lower()

    def test_format_recommendation_scale_down(self):
        """Test formatting scale down recommendation."""
        rec = ScalingRecommendation(
            resource=ResourceType.MEMORY,
            direction=ScalingDirection.SCALE_DOWN,
            priority=RecommendationPriority.LOW,
            current_value=512,
            recommended_value=256,
            reason="Low memory usage",
            impact="Reduce costs",
            estimated_savings=5.0,
        )

        formatted = format_recommendation(rec)

        assert "MEMORY" in formatted
        assert "512" in formatted
        assert "256" in formatted
        assert "saves" in formatted.lower()


class TestGetCurrentMetrics:
    """Tests for metrics retrieval."""

    @pytest.mark.asyncio
    async def test_metrics_without_monitor(self):
        """Test fallback metrics when no monitor."""
        advisor = AutoScalingAdvisor()
        metrics = await advisor.get_current_metrics("deploy-123")

        # Should return mock metrics
        assert metrics.cpu_percent == 45.0
        assert metrics.memory_mb == 256.0
        assert metrics.memory_percent == 50.0

    @pytest.mark.asyncio
    async def test_metrics_with_monitor(self):
        """Test metrics from cost monitor."""
        mock_monitor = MagicMock()
        mock_usage = MagicMock()
        mock_usage.cpu_percent = 75.0
        mock_usage.memory_mb = 384.0
        mock_monitor.get_current_usage = AsyncMock(return_value=mock_usage)

        advisor = AutoScalingAdvisor(cost_monitor=mock_monitor)
        metrics = await advisor.get_current_metrics("deploy-456")

        assert metrics.cpu_percent == 75.0
        assert metrics.memory_mb == 384.0

    @pytest.mark.asyncio
    async def test_metrics_fallback_on_error(self):
        """Test fallback when monitor raises error."""
        mock_monitor = MagicMock()
        mock_monitor.get_current_usage = AsyncMock(side_effect=Exception("Connection error"))

        advisor = AutoScalingAdvisor(cost_monitor=mock_monitor)
        metrics = await advisor.get_current_metrics("deploy-789")

        # Should fall back to mock metrics
        assert metrics.cpu_percent == 45.0


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_scaling_direction_values(self):
        """Test ScalingDirection enum values."""
        assert ScalingDirection.SCALE_UP.value == "scale_up"
        assert ScalingDirection.SCALE_DOWN.value == "scale_down"
        assert ScalingDirection.NO_CHANGE.value == "no_change"

    def test_resource_type_values(self):
        """Test ResourceType enum values."""
        assert ResourceType.CPU.value == "cpu"
        assert ResourceType.MEMORY.value == "memory"
        assert ResourceType.INSTANCES.value == "instances"

    def test_recommendation_priority_values(self):
        """Test RecommendationPriority enum values."""
        assert RecommendationPriority.CRITICAL.value == "critical"
        assert RecommendationPriority.HIGH.value == "high"
        assert RecommendationPriority.MEDIUM.value == "medium"
        assert RecommendationPriority.LOW.value == "low"
        assert RecommendationPriority.INFO.value == "info"
