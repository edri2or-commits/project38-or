"""Anomaly Response Integrator - Bridges ML Detection with Autonomous Healing.

This module connects MLAnomalyDetector (Phase 12) with AutonomousController (Phase 11)
to create a closed-loop self-healing system.

Flow:
    Metrics → MLAnomalyDetector → AnomalyResponseIntegrator → AutonomousController
                                                                    ↓
                                                            Self-Healing Actions

Example:
    >>> from src.anomaly_response_integrator import AnomalyResponseIntegrator
    >>> from src.ml_anomaly_detector import MLAnomalyDetector
    >>> from src.autonomous_controller import AutonomousController
    >>>
    >>> integrator = AnomalyResponseIntegrator(
    ...     detector=detector,
    ...     controller=controller,
    ... )
    >>> await integrator.run_detection_cycle()
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from src.autonomous_controller import (
    AutonomousController,
    HealthStatus,
    SelfHealingAction,
)
from src.ml_anomaly_detector import (
    AnomalySeverity,
    MLAnomaly,
    MLAnomalyDetector,
)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================
class ResponseStrategy(str, Enum):
    """Strategy for responding to anomalies."""

    IMMEDIATE = "immediate"  # Respond immediately to any anomaly
    CONFIRM_PATTERN = "confirm_pattern"  # Wait for pattern confirmation
    ESCALATE_ONLY = "escalate_only"  # Only escalate, no auto-action
    LEARNING = "learning"  # Observe and learn, no action


class MetricCategory(str, Enum):
    """Categories of metrics for mapping to actions."""

    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    MEMORY = "memory"
    CPU = "cpu"
    CONNECTIONS = "connections"
    CACHE = "cache"
    DISK = "disk"
    CUSTOM = "custom"


# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class AnomalyResponse:
    """Response to a detected anomaly."""

    anomaly: MLAnomaly
    action: SelfHealingAction | None
    executed: bool
    result: dict[str, Any]
    reasoning: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class IntegratorConfig:
    """Configuration for the anomaly response integrator."""

    # Response thresholds
    min_confidence_for_action: float = 0.6
    min_severity_for_action: AnomalySeverity = AnomalySeverity.WARNING

    # Pattern confirmation
    confirmation_window: timedelta = timedelta(minutes=5)
    min_anomalies_for_pattern: int = 2

    # Cooldown between actions
    action_cooldown: timedelta = timedelta(minutes=10)

    # Maximum actions per hour per metric
    max_actions_per_metric_hour: int = 3


@dataclass
class IntegratorStatus:
    """Status of the integrator."""

    anomalies_detected: int = 0
    actions_triggered: int = 0
    actions_successful: int = 0
    last_detection_cycle: datetime | None = None
    recent_responses: list[AnomalyResponse] = field(default_factory=list)


# ============================================================================
# METRIC TO ACTION MAPPING
# ============================================================================
METRIC_ACTION_MAPPING: dict[str, list[SelfHealingAction]] = {
    # Latency metrics
    "latency": [SelfHealingAction.RESTART_SERVICE, SelfHealingAction.SCALE_UP],
    "response_time": [SelfHealingAction.RESTART_SERVICE, SelfHealingAction.SCALE_UP],
    "p99_latency": [SelfHealingAction.SCALE_UP, SelfHealingAction.RESTART_SERVICE],
    # Error metrics
    "error_rate": [SelfHealingAction.RESTART_SERVICE, SelfHealingAction.CLEAR_CACHE],
    "error_count": [SelfHealingAction.RESTART_SERVICE],
    "5xx_rate": [SelfHealingAction.RESTART_SERVICE, SelfHealingAction.SCALE_UP],
    # Memory metrics
    "memory_usage": [SelfHealingAction.CLEANUP_MEMORY, SelfHealingAction.RESTART_SERVICE],
    "memory_percent": [SelfHealingAction.CLEANUP_MEMORY, SelfHealingAction.SCALE_UP],
    "heap_used": [SelfHealingAction.CLEANUP_MEMORY],
    # CPU metrics
    "cpu_usage": [SelfHealingAction.SCALE_UP, SelfHealingAction.RESTART_SERVICE],
    "cpu_percent": [SelfHealingAction.SCALE_UP],
    # Connection metrics
    "connection_count": [SelfHealingAction.RESET_CONNECTIONS],
    "active_connections": [SelfHealingAction.RESET_CONNECTIONS, SelfHealingAction.SCALE_UP],
    "connection_errors": [SelfHealingAction.RESET_CONNECTIONS],
    "db_connections": [SelfHealingAction.RESET_CONNECTIONS],
    # Cache metrics
    "cache_hit_rate": [SelfHealingAction.CLEAR_CACHE],
    "cache_miss_rate": [SelfHealingAction.CLEAR_CACHE],
    "cache_size": [SelfHealingAction.CLEAR_CACHE],
    # Disk metrics
    "disk_usage": [SelfHealingAction.CLEANUP_MEMORY],
    "disk_io": [SelfHealingAction.RESTART_SERVICE],
}

SEVERITY_TO_HEALTH: dict[AnomalySeverity, HealthStatus] = {
    AnomalySeverity.INFO: HealthStatus.HEALTHY,
    AnomalySeverity.WARNING: HealthStatus.DEGRADED,
    AnomalySeverity.CRITICAL: HealthStatus.UNHEALTHY,
}


# ============================================================================
# ANOMALY RESPONSE INTEGRATOR
# ============================================================================
class AnomalyResponseIntegrator:
    """Integrates ML anomaly detection with autonomous self-healing.

    This class bridges MLAnomalyDetector (Phase 12) with AutonomousController
    (Phase 11) to create a closed-loop self-healing system.

    Attributes:
        detector: ML anomaly detector instance
        controller: Autonomous controller instance
        config: Configuration for response behavior
        status: Current integrator status

    Example:
        >>> integrator = AnomalyResponseIntegrator(detector, controller)
        >>> await integrator.run_detection_cycle()
        >>> print(integrator.status.actions_triggered)
    """

    def __init__(
        self,
        detector: MLAnomalyDetector,
        controller: AutonomousController,
        config: IntegratorConfig | None = None,
        strategy: ResponseStrategy = ResponseStrategy.CONFIRM_PATTERN,
    ) -> None:
        """Initialize the integrator.

        Args:
            detector: ML anomaly detector
            controller: Autonomous controller
            config: Optional configuration
            strategy: Response strategy to use
        """
        self.detector = detector
        self.controller = controller
        self.config = config or IntegratorConfig()
        self.strategy = strategy
        self.status = IntegratorStatus()
        self.logger = logging.getLogger(__name__)

        # Track anomalies for pattern confirmation
        self._anomaly_history: list[MLAnomaly] = []
        self._action_history: dict[str, list[datetime]] = {}

    # ========================================================================
    # CORE DETECTION CYCLE
    # ========================================================================

    async def run_detection_cycle(
        self,
        metrics: dict[str, float] | None = None,
    ) -> list[AnomalyResponse]:
        """Run a full detection and response cycle.

        Args:
            metrics: Optional dict of metric name → value to check.
                    If None, uses existing data in detector.

        Returns:
            List of responses to detected anomalies
        """
        self.status.last_detection_cycle = datetime.now(UTC)
        responses: list[AnomalyResponse] = []

        # Add new metrics if provided
        if metrics:
            timestamp = datetime.now(UTC)
            for metric, value in metrics.items():
                self.detector.add_data_point(metric, value, timestamp)

        # Detect anomalies across all tracked metrics
        anomalies = self._detect_all_anomalies(metrics)
        self.status.anomalies_detected += len(anomalies)

        # Process each anomaly
        for anomaly in anomalies:
            response = await self._process_anomaly(anomaly)
            responses.append(response)
            self.status.recent_responses.append(response)

        # Trim response history
        self._trim_history()

        return responses

    def _detect_all_anomalies(
        self,
        metrics: dict[str, float] | None,
    ) -> list[MLAnomaly]:
        """Detect anomalies in all metrics.

        Args:
            metrics: Dict of metric → value, or None to use latest values

        Returns:
            List of detected anomalies
        """
        anomalies: list[MLAnomaly] = []

        if metrics:
            # Check provided metrics
            for metric, value in metrics.items():
                result = self.detector.detect_anomaly(metric, value)
                if result:
                    anomalies.append(result)
        else:
            # Check latest value of each tracked metric
            for metric, points in self.detector.data.items():
                if points:
                    latest = points[-1]
                    result = self.detector.detect_anomaly(metric, latest.value)
                    if result:
                        anomalies.append(result)

        return anomalies

    async def _process_anomaly(self, anomaly: MLAnomaly) -> AnomalyResponse:
        """Process a single anomaly and potentially trigger action.

        Args:
            anomaly: Detected anomaly

        Returns:
            Response indicating what action was taken
        """
        # Record in history
        self._anomaly_history.append(anomaly)

        # Check if we should take action based on strategy
        should_act, reasoning = self._should_take_action(anomaly)

        if not should_act:
            return AnomalyResponse(
                anomaly=anomaly,
                action=None,
                executed=False,
                result={},
                reasoning=reasoning,
            )

        # Determine appropriate action
        action = self._map_anomaly_to_action(anomaly)

        if not action:
            return AnomalyResponse(
                anomaly=anomaly,
                action=None,
                executed=False,
                result={},
                reasoning=f"No action mapped for metric: {anomaly.metric}",
            )

        # Check cooldown
        if self._is_in_cooldown(anomaly.metric, action):
            return AnomalyResponse(
                anomaly=anomaly,
                action=action,
                executed=False,
                result={},
                reasoning=f"Action {action.value} in cooldown for {anomaly.metric}",
            )

        # Execute healing action
        result = await self._execute_healing_action(anomaly, action)

        # Record action
        self._record_action(anomaly.metric, action)
        self.status.actions_triggered += 1
        if result.get("success", False):
            self.status.actions_successful += 1

        return AnomalyResponse(
            anomaly=anomaly,
            action=action,
            executed=True,
            result=result,
            reasoning=f"Triggered {action.value} for {anomaly.metric}",
        )

    # ========================================================================
    # ACTION DECISION LOGIC
    # ========================================================================

    def _should_take_action(self, anomaly: MLAnomaly) -> tuple[bool, str]:
        """Determine if action should be taken for anomaly.

        Args:
            anomaly: Detected anomaly

        Returns:
            Tuple of (should_act, reasoning)
        """
        # Check kill switch
        if self.controller.safety_metrics.kill_switch_triggered:
            return False, "Kill switch is active"

        # Check minimum confidence
        if anomaly.confidence < self.config.min_confidence_for_action:
            msg = f"Confidence {anomaly.confidence:.2f} below threshold"
            return False, msg

        # Check minimum severity
        severity_order = [AnomalySeverity.INFO, AnomalySeverity.WARNING, AnomalySeverity.CRITICAL]
        if severity_order.index(anomaly.severity) < severity_order.index(
            self.config.min_severity_for_action
        ):
            return False, f"Severity {anomaly.severity.value} below threshold"

        # Strategy-specific checks
        if self.strategy == ResponseStrategy.ESCALATE_ONLY:
            return False, "Strategy is escalate-only"

        if self.strategy == ResponseStrategy.LEARNING:
            return False, "Strategy is learning mode"

        if self.strategy == ResponseStrategy.CONFIRM_PATTERN:
            if not self._is_pattern_confirmed(anomaly):
                return False, "Waiting for pattern confirmation"

        return True, "All checks passed"

    def _is_pattern_confirmed(self, anomaly: MLAnomaly) -> bool:
        """Check if anomaly pattern is confirmed by recent history.

        Args:
            anomaly: Current anomaly

        Returns:
            True if pattern is confirmed
        """
        cutoff = datetime.now(UTC) - self.config.confirmation_window
        recent = [
            a for a in self._anomaly_history if a.metric == anomaly.metric and a.timestamp > cutoff
        ]

        return len(recent) >= self.config.min_anomalies_for_pattern

    def _map_anomaly_to_action(
        self,
        anomaly: MLAnomaly,
    ) -> SelfHealingAction | None:
        """Map anomaly to appropriate healing action.

        Args:
            anomaly: Detected anomaly

        Returns:
            Recommended action or None
        """
        # Check direct metric mapping
        if anomaly.metric in METRIC_ACTION_MAPPING:
            actions = METRIC_ACTION_MAPPING[anomaly.metric]
            return actions[0] if actions else None

        # Check partial metric name matches
        metric_lower = anomaly.metric.lower()
        for pattern, actions in METRIC_ACTION_MAPPING.items():
            if pattern in metric_lower:
                return actions[0] if actions else None

        # Severity-based fallback
        if anomaly.severity == AnomalySeverity.CRITICAL:
            return SelfHealingAction.RESTART_SERVICE

        return None

    def _is_in_cooldown(self, metric: str, action: SelfHealingAction) -> bool:
        """Check if action is in cooldown for metric.

        Args:
            metric: Metric name
            action: Action to check

        Returns:
            True if in cooldown
        """
        key = f"{metric}:{action.value}"
        if key not in self._action_history:
            return False

        cutoff = datetime.now(UTC) - self.config.action_cooldown
        recent = [t for t in self._action_history[key] if t > cutoff]

        # Also check max actions per hour
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        actions_last_hour = [t for t in self._action_history.get(key, []) if t > hour_ago]

        if len(actions_last_hour) >= self.config.max_actions_per_metric_hour:
            return True

        return len(recent) > 0

    def _record_action(self, metric: str, action: SelfHealingAction) -> None:
        """Record action execution for cooldown tracking.

        Args:
            metric: Metric name
            action: Action executed
        """
        key = f"{metric}:{action.value}"
        if key not in self._action_history:
            self._action_history[key] = []
        self._action_history[key].append(datetime.now(UTC))

    # ========================================================================
    # HEALING EXECUTION
    # ========================================================================

    async def _execute_healing_action(
        self,
        anomaly: MLAnomaly,
        action: SelfHealingAction,
    ) -> dict[str, Any]:
        """Execute a self-healing action through the controller.

        Args:
            anomaly: Anomaly triggering the action
            action: Action to execute

        Returns:
            Result dictionary
        """
        self.logger.info(f"Executing {action.value} for anomaly in {anomaly.metric}")

        # Use controller's healing mechanism
        try:
            result = await self.controller.trigger_self_healing(
                action,
                reason=f"Anomaly in {anomaly.metric}: {anomaly.message}",
            )
            return {"success": True, "action": action.value, "result": result}
        except Exception as e:
            self.logger.error(f"Healing action failed: {e}")
            return {"success": False, "action": action.value, "error": str(e)}

    def _severity_to_score(self, severity: AnomalySeverity) -> float:
        """Convert severity to numeric score.

        Args:
            severity: Anomaly severity

        Returns:
            Score from 0.0 to 1.0
        """
        mapping = {
            AnomalySeverity.INFO: 0.3,
            AnomalySeverity.WARNING: 0.6,
            AnomalySeverity.CRITICAL: 0.9,
        }
        return mapping.get(severity, 0.5)

    # ========================================================================
    # STATUS AND MONITORING
    # ========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get current integrator status.

        Returns:
            Status dictionary
        """
        return {
            "strategy": self.strategy.value,
            "anomalies_detected": self.status.anomalies_detected,
            "actions_triggered": self.status.actions_triggered,
            "actions_successful": self.status.actions_successful,
            "success_rate": (
                self.status.actions_successful / self.status.actions_triggered
                if self.status.actions_triggered > 0
                else 0.0
            ),
            "last_detection_cycle": (
                self.status.last_detection_cycle.isoformat()
                if self.status.last_detection_cycle
                else None
            ),
            "recent_responses_count": len(self.status.recent_responses),
            "config": {
                "min_confidence": self.config.min_confidence_for_action,
                "min_severity": self.config.min_severity_for_action.value,
                "confirmation_window_minutes": (
                    self.config.confirmation_window.total_seconds() / 60
                ),
                "action_cooldown_minutes": (self.config.action_cooldown.total_seconds() / 60),
            },
        }

    def get_recent_responses(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent anomaly responses.

        Args:
            limit: Maximum responses to return

        Returns:
            List of response dictionaries
        """
        responses = self.status.recent_responses[-limit:]
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "metric": r.anomaly.metric,
                "severity": r.anomaly.severity.value,
                "confidence": r.anomaly.confidence,
                "action": r.action.value if r.action else None,
                "executed": r.executed,
                "reasoning": r.reasoning,
            }
            for r in responses
        ]

    def _trim_history(self) -> None:
        """Trim old entries from history to prevent memory growth."""
        # Keep only last 100 responses
        if len(self.status.recent_responses) > 100:
            self.status.recent_responses = self.status.recent_responses[-100:]

        # Keep only anomalies from last hour
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        self._anomaly_history = [a for a in self._anomaly_history if a.timestamp > hour_ago]

        # Trim action history
        for key in list(self._action_history.keys()):
            self._action_history[key] = [t for t in self._action_history[key] if t > hour_ago]
            if not self._action_history[key]:
                del self._action_history[key]

    # ========================================================================
    # CONFIGURATION
    # ========================================================================

    def set_strategy(self, strategy: ResponseStrategy) -> None:
        """Change response strategy.

        Args:
            strategy: New strategy to use
        """
        self.logger.info(f"Strategy changed: {self.strategy.value} → {strategy.value}")
        self.strategy = strategy

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration values.

        Args:
            **kwargs: Configuration keys and values to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                self.logger.info(f"Config updated: {key} = {value}")

    def add_metric_mapping(
        self,
        metric: str,
        actions: list[SelfHealingAction],
    ) -> None:
        """Add custom metric to action mapping.

        Args:
            metric: Metric name
            actions: List of actions (in priority order)
        """
        METRIC_ACTION_MAPPING[metric] = actions
        self.logger.info(f"Added mapping: {metric} → {[a.value for a in actions]}")
