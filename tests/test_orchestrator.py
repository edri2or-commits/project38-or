"""Tests for Main Orchestrator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.orchestrator import (
    ActionType,
    Decision,
    DeploymentState,
    MainOrchestrator,
    Observation,
    WorldModel,
)


# ============================================================================
# FIXTURES
# ============================================================================
@pytest.fixture
def mock_railway_client():
    """Create mock Railway client."""
    client = AsyncMock()
    client.list_services = AsyncMock(return_value=[])
    client.trigger_deployment = AsyncMock(return_value={"id": "deploy-123", "status": "BUILDING"})
    client.wait_for_deployment = AsyncMock(
        return_value={"id": "deploy-123", "status": "SUCCESS", "url": "https://or-infra.com"}
    )
    client.rollback_deployment = AsyncMock(
        return_value={"id": "deploy-456", "status": "ROLLING_BACK"}
    )
    client.list_deployments = AsyncMock(
        return_value=[
            {"id": "deploy-456", "status": "SUCCESS"},
            {"id": "deploy-123", "status": "FAILED"},
        ]
    )
    return client


@pytest.fixture
def mock_github_client():
    """Create mock GitHub client."""
    client = AsyncMock()
    client.get_workflow_runs = AsyncMock(return_value={"data": []})
    client.create_issue = AsyncMock(
        return_value={"number": 123, "html_url": "https://github.com/repo/issues/123"}
    )
    client.merge_pull_request = AsyncMock(return_value={"merged": True, "sha": "abc123"})
    return client


@pytest.fixture
def mock_n8n_client():
    """Create mock n8n client."""
    client = AsyncMock()
    client.get_recent_executions = AsyncMock(return_value=[])
    client.execute_workflow = AsyncMock(return_value="exec-123")
    return client


@pytest.fixture
def orchestrator(mock_railway_client, mock_github_client, mock_n8n_client):
    """Create orchestrator instance with mocked clients."""
    return MainOrchestrator(
        railway=mock_railway_client,
        github=mock_github_client,
        n8n=mock_n8n_client,
        project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
        environment_id="99c99a18-aea2-4d01-9360-6a93705102a0",
    )


# ============================================================================
# OBSERVATION TESTS
# ============================================================================
class TestObservation:
    """Tests for Observation class."""

    def test_observation_creation(self):
        """Test creating an observation."""
        obs = Observation(
            source="railway",
            timestamp=datetime.now(UTC),
            data={"status": "ACTIVE"},
            metadata={"project_id": "123"},
        )

        assert obs.source == "railway"
        assert obs.data == {"status": "ACTIVE"}
        assert obs.metadata == {"project_id": "123"}

    def test_observation_repr(self):
        """Test observation string representation."""
        obs = Observation(source="github", timestamp=datetime.now(UTC), data={"test": "value"})

        assert "github" in repr(obs)
        assert "test" in repr(obs)


# ============================================================================
# WORLD MODEL TESTS
# ============================================================================
class TestWorldModel:
    """Tests for WorldModel class."""

    def test_world_model_initialization(self):
        """Test world model initialization."""
        wm = WorldModel()

        assert wm.railway_state == {}
        assert wm.github_state == {}
        assert wm.n8n_state == {}
        assert len(wm.observations) == 0

    def test_world_model_update(self):
        """Test updating world model with observation."""
        wm = WorldModel()
        obs = Observation(source="railway", timestamp=datetime.now(UTC), data={"status": "ACTIVE"})

        wm.update(obs)

        assert len(wm.observations) == 1
        assert wm.railway_state == {"status": "ACTIVE"}

    def test_world_model_multiple_updates(self):
        """Test multiple updates from different sources."""
        wm = WorldModel()

        railway_obs = Observation(
            source="railway", timestamp=datetime.now(UTC), data={"deployment": "active"}
        )
        github_obs = Observation(
            source="github", timestamp=datetime.now(UTC), data={"pr": "merged"}
        )

        wm.update(railway_obs)
        wm.update(github_obs)

        assert len(wm.observations) == 2
        assert wm.railway_state == {"deployment": "active"}
        assert wm.github_state == {"pr": "merged"}

    def test_get_recent_observations(self):
        """Test getting recent observations."""
        wm = WorldModel()

        for i in range(15):
            obs = Observation(source="railway", timestamp=datetime.now(UTC), data={"count": i})
            wm.update(obs)

        recent = wm.get_recent_observations(limit=5)
        assert len(recent) == 5
        assert recent[-1].data["count"] == 14


# ============================================================================
# DECISION TESTS
# ============================================================================
class TestDecision:
    """Tests for Decision class."""

    def test_decision_creation(self):
        """Test creating a decision."""
        decision = Decision(
            action=ActionType.DEPLOY,
            reasoning="New commit to main",
            parameters={"commit": "abc123"},
            priority=8,
        )

        assert decision.action == ActionType.DEPLOY
        assert decision.reasoning == "New commit to main"
        assert decision.parameters == {"commit": "abc123"}
        assert decision.priority == 8

    def test_decision_repr(self):
        """Test decision string representation."""
        decision = Decision(
            action=ActionType.ROLLBACK, reasoning="Deployment failed", parameters={}, priority=10
        )

        assert "ROLLBACK" in repr(decision)
        assert "10" in repr(decision)


# ============================================================================
# ORCHESTRATOR INITIALIZATION TESTS
# ============================================================================
class TestOrchestratorInit:
    """Tests for MainOrchestrator initialization."""

    def test_orchestrator_initialization(
        self, mock_railway_client, mock_github_client, mock_n8n_client
    ):
        """Test orchestrator initialization."""
        orchestrator = MainOrchestrator(
            railway=mock_railway_client,
            github=mock_github_client,
            n8n=mock_n8n_client,
            project_id="test-project",
            environment_id="test-env",
        )

        assert orchestrator.project_id == "test-project"
        assert orchestrator.environment_id == "test-env"
        assert orchestrator.state == DeploymentState.IDLE
        assert isinstance(orchestrator.world_model, WorldModel)


# ============================================================================
# OODA LOOP TESTS
# ============================================================================
class TestOODALoop:
    """Tests for OODA loop implementation."""

    @pytest.mark.asyncio
    async def test_observe(self, orchestrator):
        """Test OBSERVE phase."""
        observations = await orchestrator.observe()

        assert len(observations) == 3
        sources = [obs.source for obs in observations]
        assert "railway" in sources
        assert "github" in sources
        assert "n8n" in sources
        assert orchestrator.state == DeploymentState.OBSERVING

    @pytest.mark.asyncio
    async def test_observe_handles_failures(self, orchestrator):
        """Test OBSERVE handles client failures gracefully."""
        orchestrator.railway.list_services.side_effect = Exception("Railway API error")

        observations = await orchestrator.observe()

        # Should still have GitHub and n8n observations
        assert len(observations) == 2

    @pytest.mark.asyncio
    async def test_orient(self, orchestrator):
        """Test ORIENT phase."""
        observations = [
            Observation(
                source="railway",
                timestamp=datetime.now(UTC),
                data={"services": [{"name": "web", "status": "ACTIVE"}]},
            ),
            Observation(
                source="github", timestamp=datetime.now(UTC), data={"workflow_runs": {"data": []}}
            ),
        ]

        world_model = await orchestrator.orient(observations)

        assert len(world_model.observations) == 2
        assert world_model.railway_state.get("services") is not None
        assert orchestrator.state == DeploymentState.ORIENTING

    @pytest.mark.asyncio
    async def test_decide_no_action(self, orchestrator):
        """Test DECIDE phase when no action is needed."""
        world_model = WorldModel()

        decision = await orchestrator.decide(world_model)

        assert decision is None
        assert orchestrator.state == DeploymentState.DECIDING

    @pytest.mark.asyncio
    async def test_decide_rollback(self, orchestrator):
        """Test DECIDE phase initiates rollback on failure."""
        world_model = WorldModel()
        world_model.railway_state = {
            "deployment_failed": True,
            "failed_deployment_id": "deploy-123",
        }

        decision = await orchestrator.decide(world_model)

        assert decision is not None
        assert decision.action == ActionType.ROLLBACK
        assert decision.priority == 10

    @pytest.mark.asyncio
    async def test_decide_create_issue(self, orchestrator):
        """Test DECIDE phase creates issue on CI failure."""
        world_model = WorldModel()
        world_model.github_state = {
            "workflow_runs": {
                "data": [
                    {
                        "name": "test.yml",
                        "conclusion": "failure",
                        "html_url": "https://github.com/repo/actions/runs/123",
                    }
                ]
            }
        }

        decision = await orchestrator.decide(world_model)

        assert decision is not None
        assert decision.action == ActionType.CREATE_ISSUE
        assert decision.priority == 7

    @pytest.mark.asyncio
    async def test_decide_merge_pr(self, orchestrator):
        """Test DECIDE phase merges PR when ready."""
        world_model = WorldModel()
        world_model.github_state = {"pr_ready_to_merge": True, "pr_number": 42}

        decision = await orchestrator.decide(world_model)

        assert decision is not None
        assert decision.action == ActionType.MERGE_PR
        assert decision.parameters["pr_number"] == 42

    @pytest.mark.asyncio
    async def test_act_deploy(self, orchestrator):
        """Test ACT phase executes deployment."""
        decision = Decision(
            action=ActionType.DEPLOY, reasoning="New commit", parameters={"commit": "abc123"}
        )

        result = await orchestrator.act(decision)

        assert result["deployment_id"] == "deploy-123"
        assert result["status"] == "SUCCESS"
        orchestrator.railway.trigger_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_act_rollback(self, orchestrator):
        """Test ACT phase executes rollback."""
        decision = Decision(
            action=ActionType.ROLLBACK,
            reasoning="Deployment failed",
            parameters={"deployment_id": "deploy-456"},
        )

        result = await orchestrator.act(decision)

        assert result["rollback_deployment_id"] == "deploy-456"
        orchestrator.railway.rollback_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_act_create_issue(self, orchestrator):
        """Test ACT phase creates GitHub issue."""
        decision = Decision(
            action=ActionType.CREATE_ISSUE,
            reasoning="CI failure",
            parameters={"title": "Test failure", "body": "Details here"},
        )

        result = await orchestrator.act(decision)

        assert result["issue_number"] == 123
        orchestrator.github.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_act_merge_pr(self, orchestrator):
        """Test ACT phase merges PR."""
        decision = Decision(
            action=ActionType.MERGE_PR, reasoning="Checks passed", parameters={"pr_number": 42}
        )

        result = await orchestrator.act(decision)

        assert result["merged"] is True
        orchestrator.github.merge_pull_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_act_alert(self, orchestrator):
        """Test ACT phase sends alert via n8n."""
        decision = Decision(
            action=ActionType.ALERT,
            reasoning="Critical failure",
            parameters={"workflow_id": "alert-workflow", "data": {"severity": "critical"}},
        )

        result = await orchestrator.act(decision)

        assert result["execution_id"] == "exec-123"
        orchestrator.n8n.execute_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_act_invalid_action(self, orchestrator):
        """Test ACT phase raises error for invalid action."""
        decision = Decision(
            action="INVALID_ACTION",
            reasoning="Test",
            parameters={},  # type: ignore
        )

        with pytest.raises(ValueError, match="Unsupported action type"):
            await orchestrator.act(decision)


# ============================================================================
# COMPLETE CYCLE TESTS
# ============================================================================
class TestCompleteCycle:
    """Tests for complete OODA cycle."""

    @pytest.mark.asyncio
    async def test_run_cycle_no_action(self, orchestrator):
        """Test running cycle with no action needed."""
        decision = await orchestrator.run_cycle()

        assert decision is None
        assert orchestrator.state == DeploymentState.IDLE

    @pytest.mark.asyncio
    async def test_run_cycle_with_action(self, orchestrator):
        """Test running cycle with action execution."""
        # Set up world state to trigger rollback
        orchestrator.railway.list_services.return_value = [
            {
                "name": "web",
                "latestDeployment": {"id": "deploy-123", "status": "FAILED"},
            }
        ]

        decision = await orchestrator.run_cycle()

        assert decision is not None
        assert decision.action == ActionType.ROLLBACK
        assert orchestrator.state == DeploymentState.SUCCESS


# ============================================================================
# EVENT HANDLER TESTS
# ============================================================================
class TestEventHandlers:
    """Tests for event handlers."""

    @pytest.mark.asyncio
    async def test_handle_deployment_event_main_branch(self, orchestrator):
        """Test handling deployment event for main branch."""
        event = {"commit": "abc123", "ref": "refs/heads/main"}

        result = await orchestrator.handle_deployment_event(event)

        assert result["deployment_id"] == "deploy-123"
        orchestrator.railway.trigger_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_deployment_event_feature_branch(self, orchestrator):
        """Test handling deployment event for feature branch (skipped)."""
        event = {"commit": "abc123", "ref": "refs/heads/feature/xyz"}

        result = await orchestrator.handle_deployment_event(event)

        assert result["status"] == "skipped"
        assert result["reason"] == "Not main branch"
        orchestrator.railway.trigger_deployment.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_deployment_failure(self, orchestrator):
        """Test handling deployment failure with rollback."""
        result = await orchestrator.handle_deployment_failure("deploy-123")

        assert result is not None
        assert result["rollback_deployment_id"] == "deploy-456"

        # Verify both rollback and issue creation were called
        orchestrator.railway.rollback_deployment.assert_called_once()
        orchestrator.github.create_issue.assert_called_once()
