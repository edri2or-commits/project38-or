"""Autonomous Controller for Full Autonomous Operations.

Wraps MainOrchestrator with advanced autonomous capabilities:
- Confidence-based decision making (auto-execute high confidence decisions)
- Self-healing actions (restart, cache clear, scale, etc.)
- Predictive analysis (detect issues before failures)
- Safety guardrails (kill switch, rate limiting, blast radius limits)
- Autonomous learning (learn from past decisions)

Architecture:
    ┌─────────────────────────────────────────────────┐
    │           AutonomousController                   │
    │  ┌───────────────────────────────────────────┐  │
    │  │  Safety Guardrails                        │  │
    │  │  - Kill Switch                            │  │
    │  │  - Rate Limiter                           │  │
    │  │  - Blast Radius Limiter                   │  │
    │  └───────────────────────────────────────────┘  │
    │  ┌───────────────────────────────────────────┐  │
    │  │  Decision Engine                          │  │
    │  │  - Confidence Calculator                  │  │
    │  │  - Auto-Execute / Request Approval        │  │
    │  │  - Predictive Analyzer                    │  │
    │  └───────────────────────────────────────────┘  │
    │  ┌───────────────────────────────────────────┐  │
    │  │  Self-Healing Engine                      │  │
    │  │  - Service Restart                        │  │
    │  │  - Cache Invalidation                     │  │
    │  │  - Connection Reset                       │  │
    │  │  - Memory Cleanup                         │  │
    │  └───────────────────────────────────────────┘  │
    │  ┌───────────────────────────────────────────┐  │
    │  │  MainOrchestrator (OODA Loop)             │  │
    │  └───────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────┘

Example:
    >>> from src.autonomous_controller import AutonomousController
    >>> from src.orchestrator import MainOrchestrator
    >>>
    >>> controller = AutonomousController(
    ...     orchestrator=orchestrator,
    ...     confidence_threshold=0.8,  # Auto-execute if confidence >= 80%
    ...     max_actions_per_hour=20,
    ...     kill_switch_enabled=False
    ... )
    >>>
    >>> # Run full autonomous operations
    >>> await controller.run_autonomous()
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from src.orchestrator import ActionType, Decision, MainOrchestrator


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================
class AutonomyLevel(str, Enum):
    """Levels of autonomous operation."""

    MANUAL = "manual"  # All decisions require human approval
    SUPERVISED = "supervised"  # High-confidence auto, low-confidence manual
    AUTONOMOUS = "autonomous"  # All decisions auto-executed with guardrails
    FULL_AUTONOMOUS = "full_autonomous"  # No human intervention (emergency use)


class SelfHealingAction(str, Enum):
    """Available self-healing actions."""

    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    RESET_CONNECTIONS = "reset_connections"
    CLEANUP_MEMORY = "cleanup_memory"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    ROTATE_CREDENTIALS = "rotate_credentials"
    INVALIDATE_DNS = "invalidate_dns"


class HealthStatus(str, Enum):
    """System health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class ConfidenceScore:
    """Confidence score for a decision."""

    score: float  # 0.0 to 1.0
    factors: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""

    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence is high enough for auto-execution."""
        return self.score >= 0.8

    def __str__(self) -> str:
        """String representation."""
        return f"Confidence({self.score:.2%}, factors={self.factors})"


@dataclass
class ActionRecord:
    """Record of an executed action."""

    timestamp: datetime
    action_type: ActionType
    decision: Decision
    result: dict[str, Any]
    success: bool
    confidence: ConfidenceScore
    autonomous: bool  # Whether auto-executed or human-approved


@dataclass
class SafetyMetrics:
    """Safety metrics for monitoring."""

    actions_last_hour: int = 0
    actions_last_day: int = 0
    failed_actions_last_hour: int = 0
    rollbacks_last_hour: int = 0
    kill_switch_triggered: bool = False
    last_human_override: datetime | None = None


@dataclass
class PredictiveInsight:
    """Predictive insight about potential issues."""

    issue_type: str
    probability: float  # 0.0 to 1.0
    time_to_impact: timedelta
    recommended_action: SelfHealingAction | ActionType
    reasoning: str
    data_points: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# AUTONOMOUS CONTROLLER
# ============================================================================
class AutonomousController:
    """Controller for full autonomous operations with safety guardrails.

    Wraps MainOrchestrator to provide:
    - Confidence-based auto-execution
    - Self-healing capabilities
    - Predictive failure detection
    - Safety guardrails (rate limits, kill switch, blast radius)

    Attributes:
        orchestrator: The underlying OODA loop orchestrator
        autonomy_level: Current level of autonomous operation
        confidence_threshold: Min confidence for auto-execution (0.0-1.0)
        max_actions_per_hour: Rate limit for actions
        kill_switch_enabled: Whether autonomous ops are halted
    """

    def __init__(
        self,
        orchestrator: MainOrchestrator,
        autonomy_level: AutonomyLevel = AutonomyLevel.SUPERVISED,
        confidence_threshold: float = 0.8,
        max_actions_per_hour: int = 20,
        max_blast_radius: int = 3,  # Max services affected per action
        learning_enabled: bool = True,
    ):
        """Initialize autonomous controller.

        Args:
            orchestrator: MainOrchestrator instance
            autonomy_level: Level of autonomous operation
            confidence_threshold: Minimum confidence for auto-execution
            max_actions_per_hour: Maximum actions allowed per hour
            max_blast_radius: Maximum number of services affected per action
            learning_enabled: Whether to learn from past decisions
        """
        self.orchestrator = orchestrator
        self.autonomy_level = autonomy_level
        self.confidence_threshold = confidence_threshold
        self.max_actions_per_hour = max_actions_per_hour
        self.max_blast_radius = max_blast_radius
        self.learning_enabled = learning_enabled

        # Safety state
        self.kill_switch_enabled = False
        self.safety_metrics = SafetyMetrics()

        # Action history for learning
        self.action_history: list[ActionRecord] = []
        self.decision_patterns: dict[str, list[ActionRecord]] = defaultdict(list)

        # Approval queue for low-confidence decisions
        self.pending_approvals: list[tuple[Decision, ConfidenceScore]] = []

        # Self-healing state
        self.healing_in_progress: set[str] = set()
        self.recent_healings: list[tuple[datetime, SelfHealingAction]] = []

        # Logging
        self.logger = logging.getLogger(__name__)

    # ========================================================================
    # SAFETY GUARDRAILS
    # ========================================================================

    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        """Activate kill switch to halt all autonomous operations.

        Args:
            reason: Reason for activation
        """
        self.kill_switch_enabled = True
        self.safety_metrics.kill_switch_triggered = True
        self.logger.critical(f"KILL SWITCH ACTIVATED: {reason}")

    def deactivate_kill_switch(self) -> None:
        """Deactivate kill switch to resume autonomous operations."""
        self.kill_switch_enabled = False
        self.safety_metrics.last_human_override = datetime.now(UTC)
        self.logger.warning("Kill switch deactivated - autonomous operations resumed")

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows new action.

        Returns:
            True if action is allowed, False if rate limited
        """
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        recent_actions = [a for a in self.action_history if a.timestamp > one_hour_ago]
        self.safety_metrics.actions_last_hour = len(recent_actions)

        if len(recent_actions) >= self.max_actions_per_hour:
            msg = f"Rate limit reached: {len(recent_actions)}/{self.max_actions_per_hour}/hr"
            self.logger.warning(msg)
            return False
        return True

    def _check_blast_radius(self, decision: Decision) -> bool:
        """Check if action affects too many services.

        Args:
            decision: Decision to check

        Returns:
            True if blast radius is acceptable
        """
        # Estimate affected services from decision parameters
        affected = decision.parameters.get("affected_services", 1)
        if affected > self.max_blast_radius:
            self.logger.warning(
                f"Blast radius too large: {affected} > {self.max_blast_radius} services"
            )
            return False
        return True

    def _check_safety_guardrails(self, decision: Decision) -> tuple[bool, str]:
        """Check all safety guardrails before action execution.

        Args:
            decision: Decision to check

        Returns:
            Tuple of (allowed, reason)
        """
        # Kill switch check
        if self.kill_switch_enabled:
            return False, "Kill switch is active"

        # Rate limit check
        if not self._check_rate_limit():
            return False, "Rate limit exceeded"

        # Blast radius check
        if not self._check_blast_radius(decision):
            return False, "Blast radius too large"

        # Check for cascading failures (multiple rollbacks in short time)
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        recent_rollbacks = [
            a
            for a in self.action_history
            if a.timestamp > one_hour_ago and a.action_type == ActionType.ROLLBACK
        ]
        self.safety_metrics.rollbacks_last_hour = len(recent_rollbacks)

        if len(recent_rollbacks) >= 3:
            self.logger.error("Too many rollbacks - possible cascading failure")
            self.activate_kill_switch("Cascading failure detected: 3+ rollbacks/hour")
            return False, "Cascading failure protection triggered"

        return True, "All guardrails passed"

    # ========================================================================
    # CONFIDENCE CALCULATION
    # ========================================================================

    def _calculate_confidence(self, decision: Decision) -> ConfidenceScore:
        """Calculate confidence score for a decision.

        Uses multiple factors:
        - Historical success rate for this action type
        - Current system health
        - Time since last similar action
        - Severity of the action

        Args:
            decision: Decision to evaluate

        Returns:
            ConfidenceScore with detailed breakdown
        """
        factors: dict[str, float] = {}

        # Factor 1: Historical success rate (40% weight)
        similar_actions = self.decision_patterns.get(decision.action.value, [])
        if similar_actions:
            success_count = sum(1 for a in similar_actions if a.success)
            success_rate = success_count / len(similar_actions)
            factors["historical_success"] = success_rate
        else:
            # No history - moderate confidence
            factors["historical_success"] = 0.6

        # Factor 2: Action severity (20% weight)
        severity_scores = {
            ActionType.ALERT: 0.95,  # Very safe
            ActionType.CREATE_ISSUE: 0.90,  # Safe
            ActionType.EXECUTE_WORKFLOW: 0.85,  # Mostly safe
            ActionType.MERGE_PR: 0.70,  # Moderate risk
            ActionType.DEPLOY: 0.60,  # Higher risk
            ActionType.ROLLBACK: 0.75,  # Medium risk (but necessary)
            ActionType.SCALE: 0.65,  # Medium risk
        }
        factors["action_severity"] = severity_scores.get(decision.action, 0.5)

        # Factor 3: Priority alignment (20% weight)
        # High priority decisions should be acted on quickly
        priority_confidence = min(decision.priority / 10.0, 1.0)
        factors["priority_alignment"] = priority_confidence

        # Factor 4: System health context (20% weight)
        # In degraded state, be more conservative
        health_scores = {
            HealthStatus.HEALTHY: 1.0,
            HealthStatus.DEGRADED: 0.7,
            HealthStatus.UNHEALTHY: 0.4,
            HealthStatus.CRITICAL: 0.2,
        }
        current_health = self._assess_system_health()
        factors["system_health"] = health_scores.get(current_health, 0.5)

        # Calculate weighted score
        weights = {
            "historical_success": 0.40,
            "action_severity": 0.20,
            "priority_alignment": 0.20,
            "system_health": 0.20,
        }

        total_score = sum(factors[k] * weights[k] for k in factors)

        reasoning = (
            f"Confidence based on: history={factors['historical_success']:.2%}, "
            f"severity={factors['action_severity']:.2%}, "
            f"priority={factors['priority_alignment']:.2%}, "
            f"health={factors['system_health']:.2%}"
        )

        return ConfidenceScore(score=total_score, factors=factors, reasoning=reasoning)

    def _assess_system_health(self) -> HealthStatus:
        """Assess current system health from world model.

        Returns:
            Current health status
        """
        world_model = self.orchestrator.world_model

        # Check Railway health
        railway_state = world_model.railway_state
        if railway_state.get("deployment_failed"):
            return HealthStatus.CRITICAL

        # Check for degraded services
        services = railway_state.get("services", [])
        unhealthy_count = 0
        for service in services:
            deployment = service.get("latestDeployment", {})
            if deployment.get("status") in ["FAILED", "CRASHED"]:
                unhealthy_count += 1

        if unhealthy_count > 0:
            return HealthStatus.UNHEALTHY if unhealthy_count > 1 else HealthStatus.DEGRADED

        # Check GitHub CI health
        github_state = world_model.github_state
        workflow_runs = github_state.get("workflow_runs", {}).get("data", [])
        if workflow_runs:
            failed = [r for r in workflow_runs[:5] if r.get("conclusion") == "failure"]
            if len(failed) >= 3:
                return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    # ========================================================================
    # SELF-HEALING ENGINE
    # ========================================================================

    async def _execute_self_healing(
        self, action: SelfHealingAction, target: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a self-healing action.

        Args:
            action: Self-healing action to execute
            target: Target service/resource identifier
            params: Additional parameters

        Returns:
            Result of the healing action
        """
        params = params or {}
        healing_key = f"{action.value}:{target}"

        # Prevent duplicate healing
        if healing_key in self.healing_in_progress:
            self.logger.warning(f"Healing already in progress: {healing_key}")
            return {"status": "skipped", "reason": "Already in progress"}

        self.healing_in_progress.add(healing_key)
        self.logger.info(f"Executing self-healing: {action.value} on {target}")

        try:
            result = await self._perform_healing_action(action, target, params)
            self.recent_healings.append((datetime.now(UTC), action))
            return result
        finally:
            self.healing_in_progress.discard(healing_key)

    async def _perform_healing_action(
        self, action: SelfHealingAction, target: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Perform the actual healing action.

        Args:
            action: Self-healing action
            target: Target identifier
            params: Additional parameters

        Returns:
            Result of the action
        """
        if action == SelfHealingAction.RESTART_SERVICE:
            # Trigger redeployment via Railway
            deployment = await self.orchestrator.railway.trigger_deployment(
                project_id=self.orchestrator.project_id,
                environment_id=self.orchestrator.environment_id,
            )
            return {"status": "restarted", "deployment_id": deployment["id"]}

        elif action == SelfHealingAction.CLEAR_CACHE:
            # Execute cache clear workflow via n8n
            execution_id = await self.orchestrator.n8n.execute_workflow(
                workflow_id="cache-clear-workflow", data={"target": target}
            )
            return {"status": "cache_cleared", "execution_id": execution_id}

        elif action == SelfHealingAction.SCALE_UP:
            # Create scale-up decision
            scale_factor = params.get("scale_factor", 1.5)
            execution_id = await self.orchestrator.n8n.execute_workflow(
                workflow_id="scale-workflow",
                data={"target": target, "action": "up", "factor": scale_factor},
            )
            return {"status": "scaled_up", "execution_id": execution_id}

        elif action == SelfHealingAction.SCALE_DOWN:
            scale_factor = params.get("scale_factor", 0.5)
            execution_id = await self.orchestrator.n8n.execute_workflow(
                workflow_id="scale-workflow",
                data={"target": target, "action": "down", "factor": scale_factor},
            )
            return {"status": "scaled_down", "execution_id": execution_id}

        elif action == SelfHealingAction.RESET_CONNECTIONS:
            # Restart with connection pool reset
            deployment = await self.orchestrator.railway.trigger_deployment(
                project_id=self.orchestrator.project_id,
                environment_id=self.orchestrator.environment_id,
            )
            return {"status": "connections_reset", "deployment_id": deployment["id"]}

        else:
            self.logger.warning(f"Unhandled healing action: {action}")
            return {"status": "not_implemented", "action": action.value}

    async def trigger_self_healing(
        self,
        action: SelfHealingAction,
        target: str = "default",
        reason: str = "",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Public method to trigger self-healing action.

        This method is designed to be called by external integrators like
        AnomalyResponseIntegrator to trigger healing based on detected anomalies.

        Args:
            action: Self-healing action to execute
            target: Target service/resource identifier (default: "default")
            reason: Human-readable reason for triggering
            params: Additional parameters for the action

        Returns:
            Result dictionary with status and details

        Example:
            >>> result = await controller.trigger_self_healing(
            ...     action=SelfHealingAction.RESTART_SERVICE,
            ...     reason="High latency detected by ML anomaly detector",
            ... )
        """
        # Check safety guardrails
        if self.safety_metrics.kill_switch_triggered:
            return {"status": "blocked", "reason": "Kill switch is active"}

        if not self._check_rate_limit():
            return {"status": "blocked", "reason": "Rate limit exceeded"}

        self.logger.info(f"Self-healing triggered: {action.value} - {reason}")

        # Execute the healing action
        result = await self._execute_self_healing(action, target, params)
        result["triggered_by"] = "external"
        result["reason"] = reason

        return result

    # ========================================================================
    # PREDICTIVE ANALYSIS
    # ========================================================================

    async def _analyze_predictive_insights(self) -> list[PredictiveInsight]:
        """Analyze current state for predictive insights.

        Returns:
            List of predictive insights about potential issues
        """
        insights: list[PredictiveInsight] = []
        world_model = self.orchestrator.world_model

        # Pattern 1: High error rate trending up
        # (Would use metrics from performance baseline in production)
        recent_observations = world_model.get_recent_observations(limit=10)
        error_observations = [
            obs
            for obs in recent_observations
            if obs.data.get("error_rate", 0) > 0.01  # 1% error rate
        ]
        if len(error_observations) >= 3:
            insights.append(
                PredictiveInsight(
                    issue_type="error_rate_spike",
                    probability=0.75,
                    time_to_impact=timedelta(minutes=15),
                    recommended_action=SelfHealingAction.RESTART_SERVICE,
                    reasoning="Error rate trending up - restart may resolve transient issues",
                    data_points={"error_count": len(error_observations)},
                )
            )

        # Pattern 2: Memory pressure detected
        railway_state = world_model.railway_state
        for service in railway_state.get("services", []):
            memory_usage = service.get("memoryUsage", 0)
            if memory_usage > 0.85:  # 85% memory usage
                insights.append(
                    PredictiveInsight(
                        issue_type="memory_pressure",
                        probability=0.80,
                        time_to_impact=timedelta(minutes=10),
                        recommended_action=SelfHealingAction.SCALE_UP,
                        reasoning="Memory usage > 85% - scaling up recommended",
                        data_points={"memory_usage": memory_usage},
                    )
                )

        # Pattern 3: CI failures predict deployment issues
        github_state = world_model.github_state
        workflow_runs = github_state.get("workflow_runs", {}).get("data", [])
        if workflow_runs:
            failed_runs = [r for r in workflow_runs[:5] if r.get("conclusion") == "failure"]
            if len(failed_runs) >= 2:
                insights.append(
                    PredictiveInsight(
                        issue_type="ci_instability",
                        probability=0.60,
                        time_to_impact=timedelta(hours=1),
                        recommended_action=ActionType.CREATE_ISSUE,
                        reasoning="Multiple CI failures - investigate before deploying",
                        data_points={"failure_count": len(failed_runs)},
                    )
                )

        return insights

    # ========================================================================
    # AUTONOMOUS EXECUTION
    # ========================================================================

    async def _should_auto_execute(self, decision: Decision, confidence: ConfidenceScore) -> bool:
        """Determine if a decision should be auto-executed.

        Args:
            decision: Decision to evaluate
            confidence: Calculated confidence score

        Returns:
            True if should auto-execute, False if needs approval
        """
        # Manual mode - never auto-execute
        if self.autonomy_level == AutonomyLevel.MANUAL:
            return False

        # Full autonomous - always auto-execute (with guardrails)
        if self.autonomy_level == AutonomyLevel.FULL_AUTONOMOUS:
            return True

        # Supervised mode - check confidence threshold
        if self.autonomy_level == AutonomyLevel.SUPERVISED:
            return confidence.score >= self.confidence_threshold

        # Autonomous mode - auto-execute unless very low confidence
        if self.autonomy_level == AutonomyLevel.AUTONOMOUS:
            return confidence.score >= 0.5

        return False

    async def _record_action(
        self,
        decision: Decision,
        result: dict[str, Any],
        success: bool,
        confidence: ConfidenceScore,
        autonomous: bool,
    ) -> None:
        """Record an executed action for learning.

        Args:
            decision: Decision that was executed
            result: Result of execution
            success: Whether execution succeeded
            confidence: Confidence score at decision time
            autonomous: Whether auto-executed
        """
        record = ActionRecord(
            timestamp=datetime.now(UTC),
            action_type=decision.action,
            decision=decision,
            result=result,
            success=success,
            confidence=confidence,
            autonomous=autonomous,
        )

        self.action_history.append(record)
        self.decision_patterns[decision.action.value].append(record)

        # Update daily metrics
        one_day_ago = datetime.now(UTC) - timedelta(days=1)
        self.safety_metrics.actions_last_day = len(
            [a for a in self.action_history if a.timestamp > one_day_ago]
        )

        if not success:
            one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
            self.safety_metrics.failed_actions_last_hour = len(
                [a for a in self.action_history if a.timestamp > one_hour_ago and not a.success]
            )

    async def execute_with_confidence(self, decision: Decision) -> dict[str, Any]:
        """Execute a decision with confidence-based auto-execution.

        Args:
            decision: Decision to execute

        Returns:
            Result of execution or pending approval status
        """
        # Calculate confidence
        confidence = self._calculate_confidence(decision)
        self.logger.info(f"Decision confidence: {confidence}")

        # Check safety guardrails
        safe, reason = self._check_safety_guardrails(decision)
        if not safe:
            self.logger.warning(f"Decision blocked by safety guardrails: {reason}")
            return {"status": "blocked", "reason": reason}

        # Determine if auto-execute
        should_auto = await self._should_auto_execute(decision, confidence)

        if should_auto:
            self.logger.info(f"Auto-executing decision: {decision.action.value}")
            try:
                result = await self.orchestrator.act(decision)
                await self._record_action(decision, result, True, confidence, autonomous=True)
                return {"status": "executed", "result": result, "autonomous": True}
            except Exception as e:
                self.logger.error(f"Auto-execution failed: {e}")
                err_result = {"error": str(e)}
                await self._record_action(decision, err_result, False, confidence, autonomous=True)
                return {"status": "failed", "error": str(e)}
        else:
            # Queue for human approval
            self.pending_approvals.append((decision, confidence))
            self.logger.info(f"Decision queued for approval: {decision.action.value}")
            return {
                "status": "pending_approval",
                "confidence": confidence.score,
                "reasoning": confidence.reasoning,
            }

    # ========================================================================
    # MAIN AUTONOMOUS LOOP
    # ========================================================================

    async def run_autonomous_cycle(self) -> dict[str, Any]:
        """Run a single autonomous cycle with all enhancements.

        Returns:
            Summary of cycle execution
        """
        cycle_result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "decisions_made": 0,
            "decisions_auto_executed": 0,
            "decisions_pending_approval": 0,
            "self_healing_actions": 0,
            "predictive_insights": 0,
        }

        # Check kill switch
        if self.kill_switch_enabled:
            cycle_result["status"] = "halted"
            cycle_result["reason"] = "Kill switch active"
            return cycle_result

        # Phase 1: Run OODA cycle
        decision = await self.orchestrator.run_cycle()

        if decision:
            cycle_result["decisions_made"] = 1
            exec_result = await self.execute_with_confidence(decision)

            if exec_result.get("status") == "executed":
                cycle_result["decisions_auto_executed"] = 1
            elif exec_result.get("status") == "pending_approval":
                cycle_result["decisions_pending_approval"] = 1

        # Phase 2: Predictive analysis
        insights = await self._analyze_predictive_insights()
        cycle_result["predictive_insights"] = len(insights)

        # Phase 3: Self-healing for high-probability predictions
        for insight in insights:
            if insight.probability >= 0.75:
                if isinstance(insight.recommended_action, SelfHealingAction):
                    healing_result = await self._execute_self_healing(
                        action=insight.recommended_action,
                        target="primary-service",
                        params=insight.data_points,
                    )
                    if healing_result.get("status") not in ["skipped", "not_implemented"]:
                        cycle_result["self_healing_actions"] += 1

        cycle_result["status"] = "completed"
        return cycle_result

    async def run_autonomous(self, interval_seconds: int = 60) -> None:
        """Run continuous autonomous operations.

        Args:
            interval_seconds: Seconds between cycles
        """
        self.logger.info(
            f"Starting autonomous operations at {self.autonomy_level.value} level, "
            f"interval={interval_seconds}s"
        )

        while True:
            try:
                if self.kill_switch_enabled:
                    self.logger.warning("Autonomous operations paused - kill switch active")
                    await asyncio.sleep(interval_seconds)
                    continue

                result = await self.run_autonomous_cycle()
                self.logger.info(f"Autonomous cycle completed: {result}")

            except Exception as e:
                self.logger.error(f"Autonomous cycle error: {e}")
                # Increment failure counter for potential kill switch trigger
                self.safety_metrics.failed_actions_last_hour += 1

            await asyncio.sleep(interval_seconds)

    # ========================================================================
    # APPROVAL MANAGEMENT
    # ========================================================================

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get list of decisions pending human approval.

        Returns:
            List of pending decisions with confidence scores
        """
        return [
            {
                "decision": {
                    "action": decision.action.value,
                    "reasoning": decision.reasoning,
                    "parameters": decision.parameters,
                    "priority": decision.priority,
                },
                "confidence": {
                    "score": confidence.score,
                    "factors": confidence.factors,
                    "reasoning": confidence.reasoning,
                },
            }
            for decision, confidence in self.pending_approvals
        ]

    async def approve_decision(self, index: int) -> dict[str, Any]:
        """Approve a pending decision for execution.

        Args:
            index: Index of decision in pending_approvals list

        Returns:
            Result of execution
        """
        if index < 0 or index >= len(self.pending_approvals):
            return {"status": "error", "reason": "Invalid index"}

        decision, confidence = self.pending_approvals.pop(index)
        self.safety_metrics.last_human_override = datetime.now(UTC)

        try:
            result = await self.orchestrator.act(decision)
            await self._record_action(decision, result, True, confidence, autonomous=False)
            return {"status": "executed", "result": result, "autonomous": False}
        except Exception as e:
            err_result = {"error": str(e)}
            await self._record_action(decision, err_result, False, confidence, autonomous=False)
            return {"status": "failed", "error": str(e)}

    def reject_decision(self, index: int, reason: str = "") -> dict[str, Any]:
        """Reject a pending decision.

        Args:
            index: Index of decision in pending_approvals list
            reason: Reason for rejection

        Returns:
            Confirmation of rejection
        """
        if index < 0 or index >= len(self.pending_approvals):
            return {"status": "error", "reason": "Invalid index"}

        decision, confidence = self.pending_approvals.pop(index)
        self.safety_metrics.last_human_override = datetime.now(UTC)

        self.logger.info(f"Decision rejected: {decision.action.value}, reason: {reason}")
        return {
            "status": "rejected",
            "decision": decision.action.value,
            "reason": reason,
        }

    # ========================================================================
    # STATUS AND METRICS
    # ========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get current autonomous controller status.

        Returns:
            Status summary including safety metrics
        """
        return {
            "autonomy_level": self.autonomy_level.value,
            "kill_switch_enabled": self.kill_switch_enabled,
            "confidence_threshold": self.confidence_threshold,
            "max_actions_per_hour": self.max_actions_per_hour,
            "current_health": self._assess_system_health().value,
            "safety_metrics": {
                "actions_last_hour": self.safety_metrics.actions_last_hour,
                "actions_last_day": self.safety_metrics.actions_last_day,
                "failed_actions_last_hour": self.safety_metrics.failed_actions_last_hour,
                "rollbacks_last_hour": self.safety_metrics.rollbacks_last_hour,
                "kill_switch_triggered": self.safety_metrics.kill_switch_triggered,
                "last_human_override": (
                    self.safety_metrics.last_human_override.isoformat()
                    if self.safety_metrics.last_human_override
                    else None
                ),
            },
            "pending_approvals": len(self.pending_approvals),
            "healing_in_progress": list(self.healing_in_progress),
            "total_actions_recorded": len(self.action_history),
        }

    def get_learning_summary(self) -> dict[str, Any]:
        """Get summary of learned patterns.

        Returns:
            Summary of action patterns and success rates
        """
        summary: dict[str, Any] = {}

        for action_type, records in self.decision_patterns.items():
            if records:
                success_count = sum(1 for r in records if r.success)
                avg_confidence = sum(r.confidence.score for r in records) / len(records)
                autonomous_count = sum(1 for r in records if r.autonomous)

                summary[action_type] = {
                    "total_executions": len(records),
                    "success_rate": success_count / len(records),
                    "average_confidence": avg_confidence,
                    "autonomous_rate": autonomous_count / len(records),
                }

        return summary
