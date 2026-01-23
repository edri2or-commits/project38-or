"""Tests for Main Orchestrator module.

Tests the OODA Loop orchestrator in src/orchestrator.py.
Covers:
- DeploymentState, ActionType enums
- Observation, WorldModel, Decision classes
- MainOrchestrator class
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="module", autouse=True)
def mock_orchestrator_dependencies():
    """Mock the problematic imports before loading orchestrator.

    Uses module scope with autouse to apply to all tests in this module.
    Properly cleans up sys.modules after all tests complete.
    """
    # Store originals
    originals = {
        "src.github_app_client": sys.modules.get("src.github_app_client"),
        "src.n8n_client": sys.modules.get("src.n8n_client"),
        "src.railway_client": sys.modules.get("src.railway_client"),
    }

    # Create and inject mocks
    _mock_github_app_client = MagicMock()
    _mock_github_app_client.GitHubAppClient = MagicMock
    sys.modules["src.github_app_client"] = _mock_github_app_client

    _mock_n8n_client = MagicMock()
    _mock_n8n_client.N8nClient = MagicMock
    sys.modules["src.n8n_client"] = _mock_n8n_client

    _mock_railway_client = MagicMock()
    _mock_railway_client.RailwayClient = MagicMock
    sys.modules["src.railway_client"] = _mock_railway_client

    yield

    # Restore originals
    for key, original in originals.items():
        if original is not None:
            sys.modules[key] = original
        else:
            sys.modules.pop(key, None)


class TestDeploymentState:
    """Tests for DeploymentState enum."""

    def test_deployment_state_values(self):
        """Test that DeploymentState has expected values."""
        from src.orchestrator import DeploymentState

        assert DeploymentState.IDLE.value == "idle"
        assert DeploymentState.OBSERVING.value == "observing"
        assert DeploymentState.ORIENTING.value == "orienting"
        assert DeploymentState.DECIDING.value == "deciding"
        assert DeploymentState.ACTING.value == "acting"
        assert DeploymentState.SUCCESS.value == "success"
        assert DeploymentState.FAILED.value == "failed"
        assert DeploymentState.ROLLED_BACK.value == "rolled_back"


class TestActionType:
    """Tests for ActionType enum."""

    def test_action_type_values(self):
        """Test that ActionType has expected values."""
        from src.orchestrator import ActionType

        assert ActionType.DEPLOY.value == "deploy"
        assert ActionType.ROLLBACK.value == "rollback"
        assert ActionType.SCALE.value == "scale"
        assert ActionType.ALERT.value == "alert"
        assert ActionType.CREATE_ISSUE.value == "create_issue"
        assert ActionType.MERGE_PR.value == "merge_pr"
        assert ActionType.EXECUTE_WORKFLOW.value == "execute_workflow"


class TestObservation:
    """Tests for Observation class."""

    def test_observation_creation(self):
        """Test Observation creation."""
        from src.orchestrator import Observation

        now = datetime.now(UTC)
        obs = Observation(
            source="railway",
            timestamp=now,
            data={"services": ["web", "api"]},
        )

        assert obs.source == "railway"
        assert obs.timestamp == now
        assert obs.data == {"services": ["web", "api"]}
        assert obs.metadata == {}

    def test_observation_with_metadata(self):
        """Test Observation with metadata."""
        from src.orchestrator import Observation

        obs = Observation(
            source="github",
            timestamp=datetime.now(UTC),
            data={"commits": 5},
            metadata={"branch": "main"},
        )

        assert obs.metadata == {"branch": "main"}

    def test_observation_repr(self):
        """Test Observation string representation."""
        from src.orchestrator import Observation

        now = datetime.now(UTC)
        obs = Observation(
            source="railway",
            timestamp=now,
            data={"status": "healthy"},
        )

        repr_str = repr(obs)
        assert "railway" in repr_str
        assert "status" in repr_str


class TestWorldModel:
    """Tests for WorldModel class."""

    def test_world_model_init(self):
        """Test WorldModel initialization."""
        from src.orchestrator import WorldModel

        model = WorldModel()

        assert model.railway_state == {}
        assert model.github_state == {}
        assert model.n8n_state == {}
        assert model.observations == []
        assert model.last_update is not None

    def test_world_model_update_railway(self):
        """Test WorldModel update with railway observation."""
        from src.orchestrator import Observation, WorldModel

        model = WorldModel()
        obs = Observation(
            source="railway",
            timestamp=datetime.now(UTC),
            data={"services": ["web"]},
        )

        model.update(obs)

        assert model.railway_state == {"services": ["web"]}
        assert len(model.observations) == 1

    def test_world_model_update_github(self):
        """Test WorldModel update with github observation."""
        from src.orchestrator import Observation, WorldModel

        model = WorldModel()
        obs = Observation(
            source="github",
            timestamp=datetime.now(UTC),
            data={"prs": 3},
        )

        model.update(obs)

        assert model.github_state == {"prs": 3}

    def test_world_model_update_n8n(self):
        """Test WorldModel update with n8n observation."""
        from src.orchestrator import Observation, WorldModel

        model = WorldModel()
        obs = Observation(
            source="n8n",
            timestamp=datetime.now(UTC),
            data={"workflows": 5},
        )

        model.update(obs)

        assert model.n8n_state == {"workflows": 5}

    def test_get_recent_observations(self):
        """Test getting recent observations."""
        from src.orchestrator import Observation, WorldModel

        model = WorldModel()

        # Add 15 observations
        for i in range(15):
            obs = Observation(
                source="railway",
                timestamp=datetime.now(UTC),
                data={"index": i},
            )
            model.update(obs)

        # Get last 10
        recent = model.get_recent_observations(limit=10)

        assert len(recent) == 10
        assert recent[-1].data["index"] == 14


class TestDecision:
    """Tests for Decision class."""

    def test_decision_creation(self):
        """Test Decision creation."""
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action=ActionType.DEPLOY,
            reasoning="New commit detected",
            parameters={"commit": "abc123"},
        )

        assert decision.action == ActionType.DEPLOY
        assert decision.reasoning == "New commit detected"
        assert decision.parameters == {"commit": "abc123"}
        assert decision.priority == 5  # default
        assert decision.timestamp is not None

    def test_decision_with_priority(self):
        """Test Decision with custom priority."""
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action=ActionType.ROLLBACK,
            reasoning="Health check failed",
            parameters={},
            priority=10,
        )

        assert decision.priority == 10

    def test_decision_repr(self):
        """Test Decision string representation."""
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action=ActionType.ALERT,
            reasoning="High memory usage",
            parameters={},
            priority=7,
        )

        repr_str = repr(decision)
        assert "ALERT" in repr_str
        assert "7" in repr_str


class TestMainOrchestrator:
    """Tests for MainOrchestrator class."""

    @pytest.fixture
    def mock_clients(self):
        """Create mock clients for orchestrator."""
        railway = MagicMock()
        github = MagicMock()
        n8n = MagicMock()
        return railway, github, n8n

    @pytest.fixture
    def orchestrator(self, mock_clients):
        """Create orchestrator with mock clients."""
        from src.orchestrator import MainOrchestrator

        railway, github, n8n = mock_clients
        return MainOrchestrator(
            railway=railway,
            github=github,
            n8n=n8n,
            project_id="test-project",
            environment_id="test-env",
        )

    def test_init(self, orchestrator):
        """Test orchestrator initialization."""
        from src.orchestrator import DeploymentState

        assert orchestrator.project_id == "test-project"
        assert orchestrator.environment_id == "test-env"
        assert orchestrator.state == DeploymentState.IDLE
        assert orchestrator.world_model is not None

    def test_default_repo_values(self, mock_clients):
        """Test default owner/repo values."""
        from src.orchestrator import MainOrchestrator

        railway, github, n8n = mock_clients
        orch = MainOrchestrator(
            railway=railway,
            github=github,
            n8n=n8n,
            project_id="p",
            environment_id="e",
        )

        assert orch.owner == "edri2or-commits"
        assert orch.repo == "project38-or"

    @pytest.mark.asyncio
    async def test_observe_railway_success(self, orchestrator):
        """Test observe phase with railway success."""
        from src.orchestrator import DeploymentState

        orchestrator.railway.list_services = AsyncMock(
            return_value=[{"id": "svc1", "name": "web"}]
        )
        orchestrator.github.get_workflow_runs = AsyncMock(
            side_effect=Exception("GitHub error")
        )
        orchestrator.n8n.get_recent_executions = AsyncMock(
            side_effect=Exception("n8n error")
        )

        observations = await orchestrator.observe()

        assert orchestrator.state == DeploymentState.OBSERVING
        assert len(observations) >= 1
        assert observations[0].source == "railway"

    @pytest.mark.asyncio
    async def test_observe_all_fail(self, orchestrator):
        """Test observe phase when all sources fail."""
        orchestrator.railway.list_services = AsyncMock(
            side_effect=Exception("Railway error")
        )
        orchestrator.github.get_workflow_runs = AsyncMock(
            side_effect=Exception("GitHub error")
        )
        orchestrator.n8n.get_recent_executions = AsyncMock(
            side_effect=Exception("n8n error")
        )

        observations = await orchestrator.observe()

        assert observations == []

    @pytest.mark.asyncio
    async def test_observe_github_success(self, orchestrator):
        """Test observe phase with github success."""
        orchestrator.railway.list_services = AsyncMock(
            side_effect=Exception("Railway error")
        )
        orchestrator.github.get_workflow_runs = AsyncMock(
            return_value=[{"id": 1, "status": "completed"}]
        )
        orchestrator.n8n.get_recent_executions = AsyncMock(
            side_effect=Exception("n8n error")
        )

        observations = await orchestrator.observe()

        github_obs = [o for o in observations if o.source == "github"]
        assert len(github_obs) == 1

    @pytest.mark.asyncio
    async def test_observe_n8n_success(self, orchestrator):
        """Test observe phase with n8n success."""
        orchestrator.railway.list_services = AsyncMock(
            side_effect=Exception("Railway error")
        )
        orchestrator.github.get_workflow_runs = AsyncMock(
            side_effect=Exception("GitHub error")
        )
        orchestrator.n8n.get_recent_executions = AsyncMock(
            return_value=[{"id": 1, "status": "success"}]
        )

        observations = await orchestrator.observe()

        n8n_obs = [o for o in observations if o.source == "n8n"]
        assert len(n8n_obs) == 1

    @pytest.mark.asyncio
    async def test_orient(self, orchestrator):
        """Test orient phase updates world model."""
        from src.orchestrator import DeploymentState, Observation

        # Provide properly structured service data
        observations = [
            Observation(
                source="railway",
                timestamp=datetime.now(UTC),
                data={
                    "services": [
                        {"id": "svc1", "name": "web", "latestDeployment": {"status": "SUCCESS"}}
                    ]
                },
            ),
            Observation(
                source="github",
                timestamp=datetime.now(UTC),
                data={"prs": 2},
            ),
        ]

        world_model = await orchestrator.orient(observations)

        assert orchestrator.state == DeploymentState.ORIENTING
        assert "services" in world_model.railway_state
        assert world_model.github_state == {"prs": 2}


class TestOrchestratorIntegration:
    """Integration tests for orchestrator."""

    @pytest.fixture
    def full_orchestrator(self):
        """Create orchestrator with all mock clients."""
        from src.orchestrator import MainOrchestrator

        railway = MagicMock()
        railway.list_services = AsyncMock(return_value=[])
        railway.trigger_deployment = AsyncMock(return_value={"id": "deploy-1"})

        github = MagicMock()
        github.get_workflow_runs = AsyncMock(return_value=[])
        github.create_issue = AsyncMock(return_value={"number": 1})

        n8n = MagicMock()
        n8n.get_recent_executions = AsyncMock(return_value=[])

        return MainOrchestrator(
            railway=railway,
            github=github,
            n8n=n8n,
            project_id="test-project",
            environment_id="test-env",
        )

    @pytest.mark.asyncio
    async def test_full_ooda_cycle(self, full_orchestrator):
        """Test complete OODA cycle."""
        # Observe
        observations = await full_orchestrator.observe()

        # Orient
        world_model = await full_orchestrator.orient(observations)

        # World model should be updated
        assert world_model is not None
        assert len(world_model.observations) == len(observations)
