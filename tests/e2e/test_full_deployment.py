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
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Verify initialization
        assert orchestrator.railway_client is railway_client
        assert orchestrator.github_client is github_client
        assert orchestrator.n8n_client is n8n_client
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
            "workflow_runs": [
                {"id": 123, "status": "completed", "conclusion": "success"}
            ]
        }
        n8n_client.get_recent_executions.return_value = [
            {"id": "exec-1", "status": "success"}
        ]

        # Initialize orchestrator
        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Run observe phase
        observations = await orchestrator.observe()

        # Verify observations collected from all sources
        assert "railway" in observations
        assert "github" in observations
        assert "n8n" in observations
        assert len(observations["railway"]["services"]) == 1
        assert len(observations["github"]["workflow_runs"]) == 1
        assert len(observations["n8n"]["recent_executions"]) == 1

    @pytest.mark.asyncio
    async def test_deployment_decision_making(self):
        """Test orchestrator makes correct deployment decisions."""
        from src.orchestrator import ActionType, MainOrchestrator

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Mock observations showing PR ready to merge
        observations = {
            "github": {
                "pull_requests": [
                    {
                        "number": 100,
                        "state": "open",
                        "mergeable": True,
                        "status_checks": {"state": "success"},
                    }
                ]
            }
        }

        # Update world model
        orchestrator.world_model.update(observations)

        # Run decide phase
        decisions = await orchestrator.decide()

        # Should create MERGE_PR decision
        merge_decisions = [
            d for d in decisions if d.action_type == ActionType.MERGE_PR
        ]
        assert len(merge_decisions) > 0
        assert merge_decisions[0].data["pr_number"] == 100

    @pytest.mark.asyncio
    async def test_deployment_failure_recovery(self):
        """Test orchestrator handles deployment failures with rollback."""
        from src.orchestrator import MainOrchestrator

        # Create mock clients
        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock deployment failure
        railway_client.get_deployment_status.return_value = {
            "status": "FAILED",
            "error": "Build failed",
        }
        railway_client.get_previous_successful_deployment.return_value = (
            "prev-deploy-123"
        )
        railway_client.rollback_deployment.return_value = "rollback-deploy-456"

        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Trigger failure handler
        await orchestrator.handle_deployment_failure(
            deployment_id="failed-deploy-789",
            service_id="service-1",
            environment_id="env-prod",
            error="Build failed",
        )

        # Verify rollback was triggered
        railway_client.rollback_deployment.assert_called_once_with("prev-deploy-123")

        # Verify issue was created
        github_client.create_issue.assert_called_once()
        issue_call = github_client.create_issue.call_args
        assert "Deployment Failed" in issue_call[1]["title"]

        # Verify alert was sent
        n8n_client.execute_workflow.assert_called()

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
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Run complete cycle
        cycle_result = await orchestrator.run_cycle()

        # Verify cycle completed all phases
        assert "observations" in cycle_result
        assert "decisions" in cycle_result
        assert "actions" in cycle_result
        assert cycle_result["cycle_id"] is not None

        # Verify OODA phases were executed
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

        state_machine.transition_to(DeploymentStatus.BUILDING, reason="Build started")
        assert state_machine.current_state == DeploymentStatus.BUILDING

        state_machine.transition_to(
            DeploymentStatus.DEPLOYING, reason="Deploy started"
        )
        assert state_machine.current_state == DeploymentStatus.DEPLOYING

        state_machine.transition_to(
            DeploymentStatus.ACTIVE, reason="Deploy succeeded"
        )
        assert state_machine.current_state == DeploymentStatus.ACTIVE

        # Verify history tracking
        assert len(state_machine.get_history()) == 4  # PENDING + 3 transitions

    @pytest.mark.asyncio
    async def test_deployment_rollback_flow(self):
        """Test deployment rollback triggers correct state transitions."""
        from src.state_machine import (
            DeploymentStateMachine,
            DeploymentStatus,
            InvalidTransitionError,
        )

        state_machine = DeploymentStateMachine(deployment_id="failed-deploy-456")

        # Simulate deployment failure
        state_machine.transition_to(DeploymentStatus.BUILDING)
        state_machine.transition_to(DeploymentStatus.DEPLOYING)
        state_machine.transition_to(DeploymentStatus.FAILED, reason="Health check failed")

        # Transition to rollback
        state_machine.transition_to(
            DeploymentStatus.ROLLING_BACK, reason="Initiating rollback"
        )
        assert state_machine.current_state == DeploymentStatus.ROLLING_BACK

        state_machine.transition_to(
            DeploymentStatus.ROLLED_BACK, reason="Rollback complete"
        )
        assert state_machine.current_state == DeploymentStatus.ROLLED_BACK

        # Verify terminal state
        with pytest.raises(InvalidTransitionError):
            state_machine.transition_to(
                DeploymentStatus.ACTIVE, reason="Should not be allowed"
            )

    @pytest.mark.asyncio
    async def test_client_integration_railway(self):
        """Test Railway client integration with orchestrator."""
        from src.orchestrator import MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        # Mock Railway deployment trigger
        railway_client.trigger_deployment.return_value = "new-deploy-789"
        railway_client.get_deployment_status.return_value = {
            "status": "SUCCESS",
            "url": "https://or-infra.com",
        }

        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Trigger deployment action
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action_type=ActionType.DEPLOY,
            data={"service_id": "service-1", "environment_id": "env-prod"},
            priority=10,
            reason="Test deployment",
        )

        await orchestrator._act_deploy(decision)

        # Verify Railway client was called
        railway_client.trigger_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_workflow(self):
        """Test notification workflow via n8n integration."""
        from src.orchestrator import MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Trigger success notification
        from src.orchestrator import ActionType, Decision

        decision = Decision(
            action_type=ActionType.ALERT,
            data={
                "workflow_id": "deployment-success-alert",
                "payload": {
                    "deployment_id": "deploy-123",
                    "status": "SUCCESS",
                    "url": "https://or-infra.com",
                },
            },
            priority=5,
            reason="Notify deployment success",
        )

        await orchestrator._act_alert(decision)

        # Verify n8n workflow was executed
        n8n_client.execute_workflow.assert_called_once_with(
            workflow_id="deployment-success-alert",
            payload={
                "deployment_id": "deploy-123",
                "status": "SUCCESS",
                "url": "https://or-infra.com",
            },
        )


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
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        observations = await orchestrator.observe()

        # Verify all services observed
        assert len(observations["railway"]["services"]) == 3

    @pytest.mark.asyncio
    async def test_concurrent_deployments(self):
        """Test orchestrator handles concurrent deployment decisions."""
        from src.orchestrator import ActionType, Decision, MainOrchestrator

        railway_client = AsyncMock()
        github_client = AsyncMock()
        n8n_client = AsyncMock()

        orchestrator = MainOrchestrator(
            railway_client=railway_client,
            github_client=github_client,
            n8n_client=n8n_client,
        )

        # Create multiple deployment decisions
        decisions = [
            Decision(
                action_type=ActionType.DEPLOY,
                data={"service_id": f"service-{i}", "environment_id": "env-prod"},
                priority=10 - i,
                reason=f"Deploy service {i}",
            )
            for i in range(3)
        ]

        # Execute actions (should be prioritized)
        actions = await orchestrator.act(decisions)

        # Verify actions executed in priority order
        assert len(actions) == 3
        assert actions[0].priority >= actions[1].priority
        assert actions[1].priority >= actions[2].priority


# Pytest markers for selective test execution
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
]
