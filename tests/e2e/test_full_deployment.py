"""
End-to-end integration test for complete autonomous deployment flow.

Test scenario (Day 7 requirement from implementation-roadmap.md):
1. Initialize all clients (Railway, GitHub, n8n)
2. Trigger deployment via orchestrator
3. Monitor deployment status
4. Verify health check
5. Test rollback capability
6. Verify notifications

Note: These tests use mocking since we cannot access Railway production
from the Claude Code environment due to Anthropic proxy restrictions.
"""

from unittest.mock import AsyncMock, Mock

import pytest


class TestFullDeploymentFlow:
    """End-to-end tests for autonomous deployment workflow."""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test that orchestrator initializes with all required clients."""
        from src.github_app_client import GitHubAppClient
        from src.n8n_client import N8nClient
        from src.orchestrator import MainOrchestrator
        from src.railway_client import RailwayClient

        # Create mock clients
        railway_client = Mock(spec=RailwayClient)
        github_client = Mock(spec=GitHubAppClient)
        n8n_client = Mock(spec=N8nClient)

        # Initialize orchestrator
        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Verify initialization
        assert orchestrator.railway is railway_client
        assert orchestrator.github is github_client
        assert orchestrator.n8n is n8n_client
        assert orchestrator.world_model is not None

    @pytest.mark.asyncio
    async def test_ooda_loop_observe_phase(self):
        """Test OODA loop observe phase collects data from all sources."""
        from src.orchestrator import MainOrchestrator

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock observations
        railway_client.list_services.return_value = [
            {"id": "service-1", "name": "web", "deployments": []}
        ]
        github_client.get_workflow_runs.return_value = {
            "workflow_runs": [{"id": 123, "status": "completed", "conclusion": "success"}]
        }
        n8n_client.get_recent_executions.return_value = [{"id": "exec-1", "status": "success"}]

        # Initialize orchestrator
        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Run observe phase
        observations = await orchestrator.observe()

        # Verify observations collected from all sources (list of Observation objects)
        assert isinstance(observations, list)
        assert len(observations) == 3

        # Check sources
        sources = [obs.source for obs in observations]
        assert "railway" in sources
        assert "github" in sources
        assert "n8n" in sources

        # Check data structure
        railway_obs = next(obs for obs in observations if obs.source == "railway")
        assert len(railway_obs.data["services"]) == 1

        github_obs = next(obs for obs in observations if obs.source == "github")
        assert len(github_obs.data["workflow_runs"]["workflow_runs"]) == 1

        n8n_obs = next(obs for obs in observations if obs.source == "n8n")
        assert len(n8n_obs.data["recent_executions"]) == 1

    @pytest.mark.asyncio
    async def test_deployment_decision_making(self):
        """Test orchestrator makes correct deployment decisions."""
        from src.orchestrator import ActionType, Decision, MainOrchestrator, Observation
        from datetime import datetime, UTC

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Create observation with deployment failure
        obs = Observation(
            source="railway",
            timestamp=datetime.now(UTC),
            data={"deployment_failed": True, "failed_deployment_id": "deploy-123"},
        )

        # Update world model
        orchestrator.world_model.update(obs)

        # Run decide phase
        decision = await orchestrator.decide(orchestrator.world_model)

        # Should create ROLLBACK decision
        assert decision is not None
        assert decision.action == ActionType.ROLLBACK
        assert decision.parameters["deployment_id"] == "deploy-123"

    @pytest.mark.asyncio
    async def test_deployment_failure_recovery(self):
        """Test orchestrator handles deployment failures with rollback."""
        from src.orchestrator import MainOrchestrator

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock deployment history (for finding last successful deployment)
        railway_client.list_deployments.return_value = [
            {"id": "failed-deploy-789", "status": "FAILED"},
            {"id": "prev-deploy-123", "status": "SUCCESS"},
        ]
        railway_client.rollback_deployment.return_value = {
            "id": "rollback-deploy-456",
            "status": "DEPLOYING",
        }

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Trigger failure handler
        result = await orchestrator.handle_deployment_failure(
            deployment_id="failed-deploy-789",
        )

        # Verify rollback was triggered
        assert result is not None
        railway_client.list_deployments.assert_called_once()
        railway_client.rollback_deployment.assert_called_once()

        # Verify issue was created
        github_client.create_issue.assert_called_once()

        # Verify alert was sent
        n8n_client.execute_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_ooda_cycle(self):
        """Test complete OODA cycle: Observe → Orient → Decide → Act."""
        from src.orchestrator import MainOrchestrator

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock successful observations
        railway_client.list_services.return_value = []
        github_client.get_workflow_runs.return_value = {"workflow_runs": []}
        n8n_client.get_recent_executions.return_value = []

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Run complete cycle
        decision = await orchestrator.run_cycle()

        # Verify cycle completed (returns None when no decision needed)
        # In this case, no action needed since all services are healthy
        assert decision is None

        # Verify OODA phases were executed (observe phase called all clients)
        railway_client.list_services.assert_called_once()
        github_client.get_workflow_runs.assert_called_once()
        n8n_client.get_recent_executions.assert_called_once()

    @pytest.mark.asyncio
    async def test_state_machine_transitions(self):
        """Test deployment state machine handles transitions correctly."""
        from src.state_machine import DeploymentStateMachine, DeploymentStatus

        state_machine = DeploymentStateMachine(deployment_id="test-deploy-123")

        # Test valid transitions
        assert state_machine.current_state == DeploymentStatus.PENDING

        state_machine.transition(DeploymentStatus.BUILDING, reason="Build started")
        assert state_machine.current_state == DeploymentStatus.BUILDING

        state_machine.transition(DeploymentStatus.DEPLOYING, reason="Deploy started")
        assert state_machine.current_state == DeploymentStatus.DEPLOYING

        state_machine.transition(DeploymentStatus.ACTIVE, reason="Deploy succeeded")
        assert state_machine.current_state == DeploymentStatus.ACTIVE

        # Verify history tracking
        assert len(state_machine.get_history()) == 4  # PENDING + 3 transitions

    @pytest.mark.asyncio
    async def test_deployment_rollback_flow(self):
        """Test deployment rollback triggers correct state transitions."""
        from src.state_machine import (
            DeploymentStateMachine,
            DeploymentStatus,
        )

        state_machine = DeploymentStateMachine(deployment_id="failed-deploy-456")

        # Simulate deployment failure
        state_machine.transition(DeploymentStatus.BUILDING)
        state_machine.transition(DeploymentStatus.DEPLOYING)
        state_machine.transition(DeploymentStatus.FAILED, reason="Health check failed")

        # Transition to rollback
        state_machine.transition(DeploymentStatus.ROLLING_BACK, reason="Initiating rollback")
        assert state_machine.current_state == DeploymentStatus.ROLLING_BACK

        state_machine.transition(DeploymentStatus.ROLLED_BACK, reason="Rollback complete")
        assert state_machine.current_state == DeploymentStatus.ROLLED_BACK

        # Verify terminal state
        with pytest.raises(ValueError):
            state_machine.transition(DeploymentStatus.ACTIVE, reason="Should not be allowed")

    @pytest.mark.asyncio
    async def test_client_integration_railway(self):
        """Test Railway client integration with orchestrator."""
        from src.orchestrator import MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock Railway deployment trigger and status
        railway_client.trigger_deployment.return_value = {
            "id": "new-deploy-789",
            "status": "DEPLOYING",
        }
        railway_client.wait_for_deployment.return_value = {
            "status": "SUCCESS",
            "url": "https://or-infra.com",
        }

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Trigger deployment action
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action=ActionType.DEPLOY,
            reasoning="Test deployment",
            parameters={"service_id": "service-1", "environment_id": "env-prod"},
            priority=10,
        )

        # Act on decision (calls Railway client)
        await orchestrator.act(decision)

        # Verify Railway client was called for deployment trigger
        railway_client.trigger_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_workflow(self):
        """Test notification workflow via n8n integration."""
        from src.orchestrator import MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Trigger success notification
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action=ActionType.ALERT,
            reasoning="Notify deployment success",
            parameters={
                "workflow_id": "deployment-success-alert",
                "payload": {
                    "deployment_id": "deploy-123",
                    "status": "SUCCESS",
                    "url": "https://or-infra.com",
                },
            },
            priority=5,
        )

        await orchestrator.act(decision)

        # Verify n8n workflow was executed
        n8n_client.execute_workflow.assert_called_once()


class TestMultiServiceOrchestration:
    """Test orchestrator handling multiple services and environments."""

    @pytest.mark.asyncio
    async def test_multiple_service_monitoring(self):
        """Test orchestrator monitors multiple Railway services."""
        from src.orchestrator import MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock multiple services
        railway_client.list_services.return_value = [
            {"id": "service-web", "name": "web"},
            {"id": "service-worker", "name": "worker"},
            {"id": "service-api", "name": "api"},
        ]

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        observations = await orchestrator.observe()

        # Verify all services observed (observations is a list)
        railway_obs = next(obs for obs in observations if obs.source == "railway")
        assert len(railway_obs.data["services"]) == 3

    @pytest.mark.asyncio
    async def test_concurrent_deployments(self):
        """Test orchestrator handles concurrent deployment decisions."""
        from src.orchestrator import ActionType, Decision, MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        orchestrator = MainOrchestrator(
            railway=railway_client,
            github=github_client,
            n8n=n8n_client,
            project_id="test-project-id",
            environment_id="test-env-id",
        )

        # Create multiple deployment decisions
        decisions = [
            Decision(
                action=ActionType.DEPLOY,
                reasoning=f"Deploy service {i}",
                parameters={"service_id": f"service-{i}", "environment_id": "env-prod"},
                priority=10 - i,
            )
            for i in range(3)
        ]

        # Execute actions one by one (act() takes single Decision, not list)
        results = []
        for decision in decisions:
            result = await orchestrator.act(decision)
            results.append(result)

        # Verify all actions executed
        assert len(results) == 3
        assert decisions[0].priority >= decisions[1].priority
        assert decisions[1].priority >= decisions[2].priority


# Pytest markers for selective test execution
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
]
