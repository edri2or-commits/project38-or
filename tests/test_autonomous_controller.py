"""Tests for AutonomousController.

Tests cover:
- Safety guardrails (kill switch, rate limiting, blast radius)
- Confidence calculation
- Auto-execution logic
- Self-healing actions
- Predictive analysis
- Approval management
- Status and metrics
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.autonomous_controller import (
    ActionRecord,
    AutonomousController,
    AutonomyLevel,
    ConfidenceScore,
    HealthStatus,
    SelfHealingAction,
)
from src.orchestrator import ActionType, Decision, WorldModel


# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator."""
    orchestrator = MagicMock()
    orchestrator.project_id = "test-project"
    orchestrator.environment_id = "test-env"
    orchestrator.world_model = WorldModel()

    # Mock Railway client
    orchestrator.railway = AsyncMock()
    orchestrator.railway.trigger_deployment = AsyncMock(
        return_value={"id": "deploy-123", "status": "SUCCESS"}
    )
    orchestrator.railway.list_services = AsyncMock(return_value=[])

    # Mock GitHub client
    orchestrator.github = AsyncMock()
    orchestrator.github.create_issue = AsyncMock(
        return_value={"number": 1, "html_url": "https://github.com/test/1"}
    )

    # Mock n8n client
    orchestrator.n8n = AsyncMock()
    orchestrator.n8n.execute_workflow = AsyncMock(return_value="exec-123")

    # Mock OODA methods
    orchestrator.observe = AsyncMock(return_value=[])
    orchestrator.orient = AsyncMock(return_value=orchestrator.world_model)
    orchestrator.decide = AsyncMock(return_value=None)
    orchestrator.act = AsyncMock(return_value={"status": "success"})
    orchestrator.run_cycle = AsyncMock(return_value=None)

    return orchestrator


@pytest.fixture
def controller(mock_orchestrator):
    """Create an AutonomousController instance."""
    return AutonomousController(
        orchestrator=mock_orchestrator,
        autonomy_level=AutonomyLevel.SUPERVISED,
        confidence_threshold=0.8,
        max_actions_per_hour=20,
        max_blast_radius=3,
    )


@pytest.fixture
def sample_decision():
    """Create a sample decision."""
    return Decision(
        action=ActionType.DEPLOY,
        reasoning="Test deployment",
        parameters={"commit": "abc123"},
        priority=8,
    )


@pytest.fixture
def high_confidence_decision():
    """Create a decision for a safe action (high confidence)."""
    return Decision(
        action=ActionType.ALERT,
        reasoning="Send notification",
        parameters={"message": "test"},
        priority=5,
    )


# ============================================================================
# SAFETY GUARDRAILS TESTS
# ============================================================================
class TestSafetyGuardrails:
    """Tests for safety guardrail functionality."""

    def test_kill_switch_activation(self, controller):
        """Test kill switch activation halts operations."""
        controller.activate_kill_switch("Test reason")

        assert controller.kill_switch_enabled is True
        assert controller.safety_metrics.kill_switch_triggered is True

    def test_kill_switch_deactivation(self, controller):
        """Test kill switch deactivation resumes operations."""
        controller.activate_kill_switch("Test")
        controller.deactivate_kill_switch()

        assert controller.kill_switch_enabled is False
        assert controller.safety_metrics.last_human_override is not None

    def test_rate_limit_enforcement(self, controller, sample_decision):
        """Test rate limiting blocks excessive actions."""
        # Fill up action history
        for _ in range(20):
            record = ActionRecord(
                timestamp=datetime.now(UTC),
                action_type=ActionType.DEPLOY,
                decision=sample_decision,
                result={"status": "success"},
                success=True,
                confidence=ConfidenceScore(score=0.9),
                autonomous=True,
            )
            controller.action_history.append(record)

        # Rate limit should now be reached
        assert controller._check_rate_limit() is False

    def test_rate_limit_allows_when_under_limit(self, controller):
        """Test rate limiting allows actions under limit."""
        assert controller._check_rate_limit() is True

    def test_blast_radius_enforcement(self, controller):
        """Test blast radius limits affected services."""
        decision = Decision(
            action=ActionType.DEPLOY,
            reasoning="Large deployment",
            parameters={"affected_services": 5},
            priority=8,
        )

        assert controller._check_blast_radius(decision) is False

    def test_blast_radius_allows_small_changes(self, controller, sample_decision):
        """Test blast radius allows small changes."""
        assert controller._check_blast_radius(sample_decision) is True

    def test_cascading_failure_protection(self, controller, sample_decision):
        """Test cascading failure triggers kill switch."""
        # Add 3 rollbacks in the last hour
        for _ in range(3):
            record = ActionRecord(
                timestamp=datetime.now(UTC),
                action_type=ActionType.ROLLBACK,
                decision=sample_decision,
                result={"status": "rolled_back"},
                success=True,
                confidence=ConfidenceScore(score=0.9),
                autonomous=True,
            )
            controller.action_history.append(record)

        # Check guardrails should trigger kill switch
        safe, reason = controller._check_safety_guardrails(sample_decision)

        assert safe is False
        assert "Cascading failure" in reason
        assert controller.kill_switch_enabled is True

    def test_guardrails_pass_normal_conditions(self, controller, sample_decision):
        """Test guardrails pass under normal conditions."""
        safe, reason = controller._check_safety_guardrails(sample_decision)

        assert safe is True
        assert "passed" in reason.lower()


# ============================================================================
# CONFIDENCE CALCULATION TESTS
# ============================================================================
class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    def test_confidence_score_creation(self):
        """Test ConfidenceScore dataclass."""
        score = ConfidenceScore(
            score=0.85,
            factors={"test": 0.9},
            reasoning="Test reasoning",
        )

        assert score.score == 0.85
        assert score.is_high_confidence is True

    def test_low_confidence_score(self):
        """Test low confidence score detection."""
        score = ConfidenceScore(score=0.5)

        assert score.is_high_confidence is False

    def test_calculate_confidence_safe_action(self, controller, high_confidence_decision):
        """Test confidence calculation for safe action."""
        confidence = controller._calculate_confidence(high_confidence_decision)

        assert confidence.score > 0.7  # Safe actions should have higher confidence
        assert "action_severity" in confidence.factors

    def test_calculate_confidence_risky_action(self, controller, sample_decision):
        """Test confidence calculation for risky action."""
        confidence = controller._calculate_confidence(sample_decision)

        assert confidence.score < 0.9  # Deploy is riskier
        assert "historical_success" in confidence.factors

    def test_confidence_improves_with_history(self, controller, sample_decision):
        """Test confidence improves with successful history."""
        # Add successful deployment history
        for _ in range(5):
            record = ActionRecord(
                timestamp=datetime.now(UTC),
                action_type=ActionType.DEPLOY,
                decision=sample_decision,
                result={"status": "success"},
                success=True,
                confidence=ConfidenceScore(score=0.8),
                autonomous=True,
            )
            controller.action_history.append(record)
            controller.decision_patterns["deploy"].append(record)

        confidence = controller._calculate_confidence(sample_decision)

        # Should have high historical success factor
        assert confidence.factors["historical_success"] == 1.0


# ============================================================================
# HEALTH ASSESSMENT TESTS
# ============================================================================
class TestHealthAssessment:
    """Tests for system health assessment."""

    def test_healthy_status(self, controller):
        """Test healthy status detection."""
        status = controller._assess_system_health()

        assert status == HealthStatus.HEALTHY

    def test_critical_status_on_deployment_failure(self, controller, mock_orchestrator):
        """Test critical status on deployment failure."""
        mock_orchestrator.world_model.railway_state["deployment_failed"] = True

        status = controller._assess_system_health()

        assert status == HealthStatus.CRITICAL

    def test_degraded_status_on_ci_failures(self, controller, mock_orchestrator):
        """Test degraded status on CI failures."""
        mock_orchestrator.world_model.github_state["workflow_runs"] = {
            "data": [
                {"conclusion": "failure"},
                {"conclusion": "failure"},
                {"conclusion": "failure"},
            ]
        }

        status = controller._assess_system_health()

        assert status == HealthStatus.DEGRADED


# ============================================================================
# AUTONOMY LEVEL TESTS
# ============================================================================
class TestAutonomyLevels:
    """Tests for different autonomy levels."""

    @pytest.mark.asyncio
    async def test_manual_mode_never_auto_executes(self, controller, sample_decision):
        """Test manual mode always requires approval."""
        controller.autonomy_level = AutonomyLevel.MANUAL
        confidence = ConfidenceScore(score=0.99)

        should_auto = await controller._should_auto_execute(sample_decision, confidence)

        assert should_auto is False

    @pytest.mark.asyncio
    async def test_full_autonomous_always_executes(self, controller, sample_decision):
        """Test full autonomous mode always executes."""
        controller.autonomy_level = AutonomyLevel.FULL_AUTONOMOUS
        confidence = ConfidenceScore(score=0.1)

        should_auto = await controller._should_auto_execute(sample_decision, confidence)

        assert should_auto is True

    @pytest.mark.asyncio
    async def test_supervised_checks_threshold(self, controller, sample_decision):
        """Test supervised mode checks confidence threshold."""
        controller.autonomy_level = AutonomyLevel.SUPERVISED
        controller.confidence_threshold = 0.8

        high_conf = ConfidenceScore(score=0.85)
        low_conf = ConfidenceScore(score=0.75)

        assert await controller._should_auto_execute(sample_decision, high_conf) is True
        assert await controller._should_auto_execute(sample_decision, low_conf) is False

    @pytest.mark.asyncio
    async def test_autonomous_has_lower_threshold(self, controller, sample_decision):
        """Test autonomous mode has lower threshold."""
        controller.autonomy_level = AutonomyLevel.AUTONOMOUS
        confidence = ConfidenceScore(score=0.6)

        should_auto = await controller._should_auto_execute(sample_decision, confidence)

        assert should_auto is True


# ============================================================================
# EXECUTION TESTS
# ============================================================================
class TestExecution:
    """Tests for decision execution."""

    @pytest.mark.asyncio
    async def test_execute_with_high_confidence(self, controller, high_confidence_decision):
        """Test auto-execution with high confidence."""
        result = await controller.execute_with_confidence(high_confidence_decision)

        assert result["status"] == "executed"
        assert result["autonomous"] is True

    @pytest.mark.asyncio
    async def test_execute_with_low_confidence_queues(self, controller, sample_decision):
        """Test low confidence queues for approval."""
        controller.confidence_threshold = 0.99  # Make threshold very high

        result = await controller.execute_with_confidence(sample_decision)

        assert result["status"] == "pending_approval"
        assert len(controller.pending_approvals) == 1

    @pytest.mark.asyncio
    async def test_execute_blocked_by_guardrails(self, controller, sample_decision):
        """Test execution blocked by guardrails."""
        controller.activate_kill_switch("Test")

        result = await controller.execute_with_confidence(sample_decision)

        assert result["status"] == "blocked"
        assert "Kill switch" in result["reason"]

    @pytest.mark.asyncio
    async def test_action_recording(self, controller, high_confidence_decision):
        """Test action is recorded after execution."""
        await controller.execute_with_confidence(high_confidence_decision)

        assert len(controller.action_history) == 1
        record = controller.action_history[0]
        assert record.action_type == ActionType.ALERT
        assert record.autonomous is True


# ============================================================================
# SELF-HEALING TESTS
# ============================================================================
class TestSelfHealing:
    """Tests for self-healing capabilities."""

    @pytest.mark.asyncio
    async def test_restart_service_healing(self, controller):
        """Test service restart healing action."""
        result = await controller._execute_self_healing(
            action=SelfHealingAction.RESTART_SERVICE,
            target="test-service",
        )

        assert result["status"] == "restarted"
        assert "deployment_id" in result

    @pytest.mark.asyncio
    async def test_scale_up_healing(self, controller):
        """Test scale up healing action."""
        result = await controller._execute_self_healing(
            action=SelfHealingAction.SCALE_UP,
            target="test-service",
            params={"scale_factor": 2.0},
        )

        assert result["status"] == "scaled_up"

    @pytest.mark.asyncio
    async def test_duplicate_healing_prevention(self, controller):
        """Test duplicate healing is prevented."""
        controller.healing_in_progress.add("restart_service:test-service")

        result = await controller._execute_self_healing(
            action=SelfHealingAction.RESTART_SERVICE,
            target="test-service",
        )

        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_healing_recorded(self, controller):
        """Test healing action is recorded."""
        await controller._execute_self_healing(
            action=SelfHealingAction.RESTART_SERVICE,
            target="test-service",
        )

        assert len(controller.recent_healings) == 1
        action = controller.recent_healings[0][1]
        assert action == SelfHealingAction.RESTART_SERVICE


# ============================================================================
# PREDICTIVE ANALYSIS TESTS
# ============================================================================
class TestPredictiveAnalysis:
    """Tests for predictive analysis."""

    @pytest.mark.asyncio
    async def test_no_insights_healthy_system(self, controller):
        """Test no insights for healthy system."""
        insights = await controller._analyze_predictive_insights()

        assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_memory_pressure_insight(self, controller, mock_orchestrator):
        """Test memory pressure generates insight."""
        mock_orchestrator.world_model.railway_state["services"] = [
            {"name": "web", "memoryUsage": 0.90}
        ]

        insights = await controller._analyze_predictive_insights()

        memory_insights = [i for i in insights if i.issue_type == "memory_pressure"]
        assert len(memory_insights) == 1
        assert memory_insights[0].recommended_action == SelfHealingAction.SCALE_UP

    @pytest.mark.asyncio
    async def test_ci_instability_insight(self, controller, mock_orchestrator):
        """Test CI instability generates insight."""
        mock_orchestrator.world_model.github_state["workflow_runs"] = {
            "data": [
                {"conclusion": "failure"},
                {"conclusion": "failure"},
                {"conclusion": "success"},
            ]
        }

        insights = await controller._analyze_predictive_insights()

        ci_insights = [i for i in insights if i.issue_type == "ci_instability"]
        assert len(ci_insights) == 1
        assert ci_insights[0].recommended_action == ActionType.CREATE_ISSUE


# ============================================================================
# APPROVAL MANAGEMENT TESTS
# ============================================================================
class TestApprovalManagement:
    """Tests for approval queue management."""

    def test_get_pending_approvals_empty(self, controller):
        """Test empty approvals list."""
        approvals = controller.get_pending_approvals()

        assert len(approvals) == 0

    def test_get_pending_approvals_with_items(self, controller, sample_decision):
        """Test approvals list with items."""
        confidence = ConfidenceScore(score=0.6, reasoning="Test")
        controller.pending_approvals.append((sample_decision, confidence))

        approvals = controller.get_pending_approvals()

        assert len(approvals) == 1
        assert approvals[0]["decision"]["action"] == "deploy"
        assert approvals[0]["confidence"]["score"] == 0.6

    @pytest.mark.asyncio
    async def test_approve_decision(self, controller, sample_decision):
        """Test approving a pending decision."""
        confidence = ConfidenceScore(score=0.6)
        controller.pending_approvals.append((sample_decision, confidence))

        result = await controller.approve_decision(0)

        assert result["status"] == "executed"
        assert result["autonomous"] is False
        assert len(controller.pending_approvals) == 0

    def test_reject_decision(self, controller, sample_decision):
        """Test rejecting a pending decision."""
        confidence = ConfidenceScore(score=0.6)
        controller.pending_approvals.append((sample_decision, confidence))

        result = controller.reject_decision(0, "Not needed")

        assert result["status"] == "rejected"
        assert len(controller.pending_approvals) == 0

    @pytest.mark.asyncio
    async def test_approve_invalid_index(self, controller):
        """Test approving invalid index returns error."""
        result = await controller.approve_decision(999)

        assert result["status"] == "error"


# ============================================================================
# AUTONOMOUS CYCLE TESTS
# ============================================================================
class TestAutonomousCycle:
    """Tests for autonomous operation cycle."""

    @pytest.mark.asyncio
    async def test_cycle_with_kill_switch(self, controller):
        """Test cycle is halted with kill switch."""
        controller.activate_kill_switch("Test")

        result = await controller.run_autonomous_cycle()

        assert result["status"] == "halted"

    @pytest.mark.asyncio
    async def test_cycle_with_no_decision(self, controller, mock_orchestrator):
        """Test cycle with no decision needed."""
        mock_orchestrator.run_cycle = AsyncMock(return_value=None)

        result = await controller.run_autonomous_cycle()

        assert result["status"] == "completed"
        assert result["decisions_made"] == 0

    @pytest.mark.asyncio
    async def test_cycle_with_decision(
        self, controller, mock_orchestrator, high_confidence_decision
    ):
        """Test cycle with decision to execute."""
        mock_orchestrator.run_cycle = AsyncMock(return_value=high_confidence_decision)

        result = await controller.run_autonomous_cycle()

        assert result["status"] == "completed"
        assert result["decisions_made"] == 1
        assert result["decisions_auto_executed"] == 1


# ============================================================================
# STATUS AND METRICS TESTS
# ============================================================================
class TestStatusAndMetrics:
    """Tests for status and metrics reporting."""

    def test_get_status(self, controller):
        """Test status retrieval."""
        status = controller.get_status()

        assert status["autonomy_level"] == "supervised"
        assert status["kill_switch_enabled"] is False
        assert status["confidence_threshold"] == 0.8
        assert "safety_metrics" in status

    def test_get_learning_summary_empty(self, controller):
        """Test learning summary when empty."""
        summary = controller.get_learning_summary()

        assert len(summary) == 0

    def test_get_learning_summary_with_data(self, controller, sample_decision):
        """Test learning summary with recorded actions."""
        # Add some action records
        for success in [True, True, False, True]:
            record = ActionRecord(
                timestamp=datetime.now(UTC),
                action_type=ActionType.DEPLOY,
                decision=sample_decision,
                result={"status": "success" if success else "failed"},
                success=success,
                confidence=ConfidenceScore(score=0.8),
                autonomous=True,
            )
            controller.action_history.append(record)
            controller.decision_patterns["deploy"].append(record)

        summary = controller.get_learning_summary()

        assert "deploy" in summary
        assert summary["deploy"]["total_executions"] == 4
        assert summary["deploy"]["success_rate"] == 0.75
        assert summary["deploy"]["autonomous_rate"] == 1.0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================
class TestIntegration:
    """Integration tests for autonomous controller."""

    @pytest.mark.asyncio
    async def test_full_autonomous_cycle_with_healing(self, controller, mock_orchestrator):
        """Test full cycle including self-healing."""
        # Set up memory pressure condition
        mock_orchestrator.world_model.railway_state["services"] = [
            {"name": "web", "memoryUsage": 0.90}
        ]

        controller.autonomy_level = AutonomyLevel.AUTONOMOUS

        result = await controller.run_autonomous_cycle()

        assert result["status"] == "completed"
        # Should have detected memory pressure and attempted healing
        assert result["predictive_insights"] >= 1

    @pytest.mark.asyncio
    async def test_confidence_learning_over_time(self, controller, sample_decision):
        """Test confidence improves with successful history."""
        controller.autonomy_level = AutonomyLevel.SUPERVISED
        controller.confidence_threshold = 0.7

        # Initial confidence
        initial_conf = controller._calculate_confidence(sample_decision)

        # Add successful history
        for _ in range(10):
            record = ActionRecord(
                timestamp=datetime.now(UTC),
                action_type=ActionType.DEPLOY,
                decision=sample_decision,
                result={"status": "success"},
                success=True,
                confidence=ConfidenceScore(score=0.8),
                autonomous=True,
            )
            controller.decision_patterns["deploy"].append(record)

        # Confidence should improve
        improved_conf = controller._calculate_confidence(sample_decision)

        assert improved_conf.score >= initial_conf.score

    @pytest.mark.asyncio
    async def test_safety_prevents_dangerous_autonomous_actions(
        self, controller, mock_orchestrator
    ):
        """Test safety guardrails prevent dangerous autonomous actions."""
        # Simulate cascading failures
        for _ in range(3):
            record = ActionRecord(
                timestamp=datetime.now(UTC),
                action_type=ActionType.ROLLBACK,
                decision=Decision(
                    action=ActionType.ROLLBACK,
                    reasoning="Failed deployment",
                    parameters={},
                ),
                result={"status": "rolled_back"},
                success=True,
                confidence=ConfidenceScore(score=0.9),
                autonomous=True,
            )
            controller.action_history.append(record)

        # Create new decision
        decision = Decision(
            action=ActionType.DEPLOY,
            reasoning="New deployment",
            parameters={"commit": "def456"},
        )

        # Should be blocked by cascading failure protection
        result = await controller.execute_with_confidence(decision)

        assert result["status"] == "blocked"
        assert controller.kill_switch_enabled is True
