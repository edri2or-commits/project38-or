"""Tests for Anomaly Response Integrator.

Tests cover:
- Anomaly to action mapping
- Response strategy behavior
- Pattern confirmation logic
- Cooldown and rate limiting
- Integration with controller
- Status and monitoring
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.anomaly_response_integrator import (
    METRIC_ACTION_MAPPING,
    AnomalyResponse,
    AnomalyResponseIntegrator,
    IntegratorConfig,
    ResponseStrategy,
)
from src.autonomous_controller import AutonomousController, SelfHealingAction
from src.ml_anomaly_detector import (
    AnomalySeverity,
    DetectionMethod,
    MLAnomaly,
    MLAnomalyDetector,
)


# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def mock_detector():
    """Create a mock ML anomaly detector."""
    detector = MagicMock(spec=MLAnomalyDetector)
    detector.data = {}
    detector.stats = {}
    return detector


@pytest.fixture
def mock_controller():
    """Create a mock autonomous controller."""
    controller = MagicMock(spec=AutonomousController)
    controller.safety_metrics = MagicMock()
    controller.safety_metrics.kill_switch_triggered = False
    controller.trigger_self_healing = AsyncMock(
        return_value={"status": "success", "action": "restart_service"}
    )
    return controller


@pytest.fixture
def integrator(mock_detector, mock_controller):
    """Create an integrator with mocked components."""
    return AnomalyResponseIntegrator(
        detector=mock_detector,
        controller=mock_controller,
        strategy=ResponseStrategy.IMMEDIATE,
    )


@pytest.fixture
def sample_anomaly():
    """Create a sample anomaly for testing."""
    return MLAnomaly(
        metric="latency",
        timestamp=datetime.now(UTC),
        value=150.0,
        expected=100.0,
        deviation=2.5,
        severity=AnomalySeverity.WARNING,
        confidence=0.75,
        methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE, DetectionMethod.EMA_DEVIATION],
        message="Latency above threshold",
    )


@pytest.fixture
def critical_anomaly():
    """Create a critical severity anomaly."""
    return MLAnomaly(
        metric="error_rate",
        timestamp=datetime.now(UTC),
        value=0.15,
        expected=0.01,
        deviation=4.5,
        severity=AnomalySeverity.CRITICAL,
        confidence=0.9,
        methods_triggered=[
            DetectionMethod.ADAPTIVE_ZSCORE,
            DetectionMethod.EMA_DEVIATION,
            DetectionMethod.IQR_OUTLIER,
        ],
        message="Critical error rate spike",
    )


# ============================================================================
# METRIC MAPPING TESTS
# ============================================================================
class TestMetricMapping:
    """Tests for metric to action mapping."""

    def test_latency_maps_to_restart(self, integrator, sample_anomaly):
        """Test latency anomaly maps to restart action."""
        action = integrator._map_anomaly_to_action(sample_anomaly)
        assert action == SelfHealingAction.RESTART_SERVICE

    def test_memory_maps_to_cleanup(self, integrator):
        """Test memory anomaly maps to cleanup action."""
        anomaly = MLAnomaly(
            metric="memory_usage",
            timestamp=datetime.now(UTC),
            value=95.0,
            expected=70.0,
            deviation=3.0,
            severity=AnomalySeverity.WARNING,
            confidence=0.8,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="High memory usage",
        )
        action = integrator._map_anomaly_to_action(anomaly)
        assert action == SelfHealingAction.CLEANUP_MEMORY

    def test_connection_maps_to_reset(self, integrator):
        """Test connection anomaly maps to reset action."""
        anomaly = MLAnomaly(
            metric="connection_count",
            timestamp=datetime.now(UTC),
            value=1000.0,
            expected=200.0,
            deviation=4.0,
            severity=AnomalySeverity.WARNING,
            confidence=0.85,
            methods_triggered=[DetectionMethod.IQR_OUTLIER],
            message="Connection count spike",
        )
        action = integrator._map_anomaly_to_action(anomaly)
        assert action == SelfHealingAction.RESET_CONNECTIONS

    def test_unknown_metric_critical_uses_restart(self, integrator):
        """Test unknown metric with critical severity uses restart."""
        anomaly = MLAnomaly(
            metric="custom_metric_xyz",
            timestamp=datetime.now(UTC),
            value=100.0,
            expected=50.0,
            deviation=5.0,
            severity=AnomalySeverity.CRITICAL,
            confidence=0.9,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="Unknown critical anomaly",
        )
        action = integrator._map_anomaly_to_action(anomaly)
        assert action == SelfHealingAction.RESTART_SERVICE

    def test_unknown_metric_low_severity_returns_none(self, integrator):
        """Test unknown metric with low severity returns None."""
        anomaly = MLAnomaly(
            metric="custom_metric_xyz",
            timestamp=datetime.now(UTC),
            value=60.0,
            expected=50.0,
            deviation=1.0,
            severity=AnomalySeverity.INFO,
            confidence=0.5,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="Minor anomaly",
        )
        action = integrator._map_anomaly_to_action(anomaly)
        assert action is None

    def test_partial_metric_match(self, integrator):
        """Test partial metric name matching."""
        anomaly = MLAnomaly(
            metric="api_response_time_p95",
            timestamp=datetime.now(UTC),
            value=500.0,
            expected=100.0,
            deviation=4.0,
            severity=AnomalySeverity.WARNING,
            confidence=0.8,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="High response time",
        )
        action = integrator._map_anomaly_to_action(anomaly)
        # Should match "response_time" pattern
        assert action == SelfHealingAction.RESTART_SERVICE


# ============================================================================
# RESPONSE STRATEGY TESTS
# ============================================================================
class TestResponseStrategy:
    """Tests for different response strategies."""

    def test_immediate_strategy_acts_on_first_anomaly(
        self, mock_detector, mock_controller, sample_anomaly
    ):
        """Test IMMEDIATE strategy acts on first anomaly."""
        integrator = AnomalyResponseIntegrator(
            detector=mock_detector,
            controller=mock_controller,
            strategy=ResponseStrategy.IMMEDIATE,
        )
        should_act, reason = integrator._should_take_action(sample_anomaly)
        assert should_act is True

    def test_confirm_pattern_waits_for_multiple(
        self, mock_detector, mock_controller, sample_anomaly
    ):
        """Test CONFIRM_PATTERN strategy waits for multiple anomalies."""
        integrator = AnomalyResponseIntegrator(
            detector=mock_detector,
            controller=mock_controller,
            strategy=ResponseStrategy.CONFIRM_PATTERN,
        )
        # First anomaly should not trigger action
        should_act, reason = integrator._should_take_action(sample_anomaly)
        assert should_act is False
        assert "pattern confirmation" in reason.lower()

    def test_confirm_pattern_acts_after_pattern(
        self, mock_detector, mock_controller, sample_anomaly
    ):
        """Test CONFIRM_PATTERN acts after pattern is confirmed."""
        integrator = AnomalyResponseIntegrator(
            detector=mock_detector,
            controller=mock_controller,
            strategy=ResponseStrategy.CONFIRM_PATTERN,
            config=IntegratorConfig(min_anomalies_for_pattern=2),
        )
        # Add anomalies to history
        integrator._anomaly_history.append(sample_anomaly)
        integrator._anomaly_history.append(sample_anomaly)

        should_act, _ = integrator._should_take_action(sample_anomaly)
        assert should_act is True

    def test_escalate_only_never_acts(self, mock_detector, mock_controller, critical_anomaly):
        """Test ESCALATE_ONLY strategy never auto-acts."""
        integrator = AnomalyResponseIntegrator(
            detector=mock_detector,
            controller=mock_controller,
            strategy=ResponseStrategy.ESCALATE_ONLY,
        )
        should_act, reason = integrator._should_take_action(critical_anomaly)
        assert should_act is False
        assert "escalate-only" in reason.lower()

    def test_learning_mode_never_acts(self, mock_detector, mock_controller, critical_anomaly):
        """Test LEARNING strategy never auto-acts."""
        integrator = AnomalyResponseIntegrator(
            detector=mock_detector,
            controller=mock_controller,
            strategy=ResponseStrategy.LEARNING,
        )
        should_act, reason = integrator._should_take_action(critical_anomaly)
        assert should_act is False
        assert "learning" in reason.lower()


# ============================================================================
# CONFIDENCE AND SEVERITY THRESHOLD TESTS
# ============================================================================
class TestThresholds:
    """Tests for confidence and severity thresholds."""

    def test_low_confidence_blocked(self, integrator):
        """Test low confidence anomalies are blocked."""
        anomaly = MLAnomaly(
            metric="latency",
            timestamp=datetime.now(UTC),
            value=120.0,
            expected=100.0,
            deviation=1.5,
            severity=AnomalySeverity.WARNING,
            confidence=0.3,  # Below default 0.6 threshold
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="Low confidence anomaly",
        )
        should_act, reason = integrator._should_take_action(anomaly)
        assert should_act is False
        assert "confidence" in reason.lower()

    def test_info_severity_blocked_by_default(self, integrator):
        """Test INFO severity is blocked by default threshold."""
        anomaly = MLAnomaly(
            metric="latency",
            timestamp=datetime.now(UTC),
            value=105.0,
            expected=100.0,
            deviation=0.5,
            severity=AnomalySeverity.INFO,  # Below default WARNING threshold
            confidence=0.8,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="Info level anomaly",
        )
        should_act, reason = integrator._should_take_action(anomaly)
        assert should_act is False
        assert "severity" in reason.lower()

    def test_custom_thresholds(self, mock_detector, mock_controller):
        """Test custom threshold configuration."""
        config = IntegratorConfig(
            min_confidence_for_action=0.9,
            min_severity_for_action=AnomalySeverity.CRITICAL,
        )
        integrator = AnomalyResponseIntegrator(
            detector=mock_detector,
            controller=mock_controller,
            config=config,
            strategy=ResponseStrategy.IMMEDIATE,
        )

        # WARNING severity should be blocked
        anomaly = MLAnomaly(
            metric="latency",
            timestamp=datetime.now(UTC),
            value=150.0,
            expected=100.0,
            deviation=2.5,
            severity=AnomalySeverity.WARNING,
            confidence=0.95,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="Warning anomaly",
        )
        should_act, reason = integrator._should_take_action(anomaly)
        assert should_act is False


# ============================================================================
# COOLDOWN AND RATE LIMITING TESTS
# ============================================================================
class TestCooldown:
    """Tests for cooldown and rate limiting."""

    def test_action_in_cooldown(self, integrator):
        """Test action is blocked during cooldown."""
        # Record a recent action
        integrator._record_action("latency", SelfHealingAction.RESTART_SERVICE)

        # Check cooldown
        in_cooldown = integrator._is_in_cooldown("latency", SelfHealingAction.RESTART_SERVICE)
        assert in_cooldown is True

    def test_cooldown_expires(self, integrator):
        """Test cooldown expires after configured time."""
        # Record an old action
        key = "latency:restart_service"
        old_time = datetime.now(UTC) - timedelta(minutes=15)
        integrator._action_history[key] = [old_time]

        # Should not be in cooldown (default 10 min)
        in_cooldown = integrator._is_in_cooldown("latency", SelfHealingAction.RESTART_SERVICE)
        assert in_cooldown is False

    def test_max_actions_per_hour(self, integrator):
        """Test max actions per hour per metric is enforced."""
        # Record multiple actions
        key = "latency:restart_service"
        integrator._action_history[key] = [
            datetime.now(UTC) - timedelta(minutes=i * 15)
            for i in range(3)  # 3 actions in last hour
        ]

        # Default max is 3, so should be in cooldown
        in_cooldown = integrator._is_in_cooldown("latency", SelfHealingAction.RESTART_SERVICE)
        assert in_cooldown is True


# ============================================================================
# KILL SWITCH TESTS
# ============================================================================
class TestKillSwitch:
    """Tests for kill switch integration."""

    def test_kill_switch_blocks_action(self, integrator, sample_anomaly):
        """Test kill switch blocks all actions."""
        integrator.controller.safety_metrics.kill_switch_triggered = True

        should_act, reason = integrator._should_take_action(sample_anomaly)
        assert should_act is False
        assert "kill switch" in reason.lower()


# ============================================================================
# DETECTION CYCLE TESTS
# ============================================================================
class TestDetectionCycle:
    """Tests for full detection cycle."""

    @pytest.mark.asyncio
    async def test_cycle_with_metrics(self, integrator, mock_detector):
        """Test detection cycle with provided metrics."""
        mock_detector.detect_anomaly = MagicMock(return_value=None)

        await integrator.run_detection_cycle(metrics={"latency": 100.0, "memory_usage": 70.0})

        # Should have called add_data_point for each metric
        assert mock_detector.add_data_point.call_count == 2

    @pytest.mark.asyncio
    async def test_cycle_detects_anomaly(self, integrator, mock_detector, sample_anomaly):
        """Test detection cycle processes detected anomaly."""
        mock_detector.detect_anomaly = MagicMock(return_value=sample_anomaly)

        responses = await integrator.run_detection_cycle(metrics={"latency": 150.0})

        assert len(responses) == 1
        assert responses[0].anomaly == sample_anomaly

    @pytest.mark.asyncio
    async def test_cycle_triggers_healing(
        self, integrator, mock_detector, mock_controller, sample_anomaly
    ):
        """Test detection cycle triggers healing action."""
        mock_detector.detect_anomaly = MagicMock(return_value=sample_anomaly)

        responses = await integrator.run_detection_cycle(metrics={"latency": 150.0})

        assert len(responses) == 1
        assert responses[0].executed is True
        mock_controller.trigger_self_healing.assert_called_once()


# ============================================================================
# STATUS AND MONITORING TESTS
# ============================================================================
class TestStatus:
    """Tests for status and monitoring."""

    def test_get_status(self, integrator):
        """Test status retrieval."""
        status = integrator.get_status()

        assert "strategy" in status
        assert "anomalies_detected" in status
        assert "actions_triggered" in status
        assert "config" in status
        assert status["strategy"] == "immediate"

    def test_status_updates_after_cycle(self, integrator, mock_detector, sample_anomaly):
        """Test status updates after detection cycle."""
        mock_detector.detect_anomaly = MagicMock(return_value=sample_anomaly)

        # Run a cycle
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            integrator.run_detection_cycle(metrics={"latency": 150.0})
        )

        status = integrator.get_status()
        assert status["anomalies_detected"] >= 1

    def test_get_recent_responses(self, integrator, sample_anomaly):
        """Test recent responses retrieval."""
        # Add a response
        response = AnomalyResponse(
            anomaly=sample_anomaly,
            action=SelfHealingAction.RESTART_SERVICE,
            executed=True,
            result={"status": "success"},
            reasoning="Test action",
        )
        integrator.status.recent_responses.append(response)

        responses = integrator.get_recent_responses(limit=5)
        assert len(responses) == 1
        assert responses[0]["metric"] == "latency"


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================
class TestConfiguration:
    """Tests for configuration management."""

    def test_set_strategy(self, integrator):
        """Test strategy can be changed."""
        integrator.set_strategy(ResponseStrategy.LEARNING)
        assert integrator.strategy == ResponseStrategy.LEARNING

    def test_update_config(self, integrator):
        """Test configuration can be updated."""
        integrator.update_config(min_confidence_for_action=0.9)
        assert integrator.config.min_confidence_for_action == 0.9

    def test_add_metric_mapping(self, integrator):
        """Test custom metric mapping can be added."""
        integrator.add_metric_mapping(
            "custom_metric",
            [SelfHealingAction.SCALE_UP, SelfHealingAction.RESTART_SERVICE],
        )
        assert "custom_metric" in METRIC_ACTION_MAPPING


# ============================================================================
# HISTORY MANAGEMENT TESTS
# ============================================================================
class TestHistoryManagement:
    """Tests for history trimming."""

    def test_trim_old_anomalies(self, integrator, sample_anomaly):
        """Test old anomalies are trimmed from history."""
        # Add old anomaly
        old_anomaly = MLAnomaly(
            metric="latency",
            timestamp=datetime.now(UTC) - timedelta(hours=2),
            value=150.0,
            expected=100.0,
            deviation=2.5,
            severity=AnomalySeverity.WARNING,
            confidence=0.75,
            methods_triggered=[DetectionMethod.ADAPTIVE_ZSCORE],
            message="Old anomaly",
        )
        integrator._anomaly_history.append(old_anomaly)
        integrator._anomaly_history.append(sample_anomaly)

        integrator._trim_history()

        # Old anomaly should be removed
        assert len(integrator._anomaly_history) == 1
        assert integrator._anomaly_history[0] == sample_anomaly

    def test_trim_responses_limit(self, integrator, sample_anomaly):
        """Test response history is limited."""
        # Add 150 responses
        for i in range(150):
            response = AnomalyResponse(
                anomaly=sample_anomaly,
                action=None,
                executed=False,
                result={},
                reasoning=f"Test {i}",
            )
            integrator.status.recent_responses.append(response)

        integrator._trim_history()

        # Should be trimmed to 100
        assert len(integrator.status.recent_responses) == 100
