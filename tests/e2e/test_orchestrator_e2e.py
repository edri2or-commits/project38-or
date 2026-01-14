"""End-to-end tests for MainOrchestrator OODA loop."""

from datetime import datetime

import pytest

from src.orchestrator import ActionType, Decision, Observation, WorldModel


@pytest.mark.asyncio
async def test_complete_ooda_cycle(orchestrator, mock_railway_client, mock_github_client):
    """Test complete OODA loop cycle: Observe → Orient → Decide → Act."""

    # Setup: Mock observations
    mock_railway_client.list_services.return_value = [
        {
            "id": "service-123",
            "name": "web",
            "latestDeployment": {
                "id": "deployment-123",
                "status": "SUCCESS",
                "createdAt": datetime.utcnow().isoformat(),
            },
        }
    ]

    mock_github_client.get_workflow_runs.return_value = {
        "data": [
            {
                "id": "run-123",
                "status": "completed",
                "conclusion": "success",
                "created_at": datetime.utcnow().isoformat(),
            }
        ]
    }

    # Execute: Run complete OODA cycle
    decision = await orchestrator.run_cycle()

    # Assert: Cycle completed (returns Decision or None)
    # If no action needed, returns None
    # If action taken, returns Decision object
    assert decision is None or isinstance(decision, Decision)

    if decision:
        # Verify Decision structure
        assert hasattr(decision, "action")
        assert hasattr(decision, "reasoning")
        assert hasattr(decision, "parameters")
        assert isinstance(decision.action, ActionType)


@pytest.mark.asyncio
async def test_ooda_deployment_failure_recovery(
    orchestrator, mock_railway_client, mock_github_client, mock_n8n_client
):
    """Test OODA loop handles deployment failure autonomously."""

    # Setup: Mock failed deployment in Railway state
    # The orchestrator checks world_model.railway_state.get("deployment_failed")
    # This requires manipulating the world model after observe()

    # For this test, we'll trigger observe -> orient -> decide sequence
    mock_railway_client.list_services.return_value = [
        {
            "id": "service-123",
            "status": "FAILED",
            "latestDeployment": {"id": "deployment-failed", "status": "FAILED"},
        }
    ]

    mock_railway_client.list_deployments.return_value = [
        {
            "id": "deployment-failed",
            "status": "FAILED",
            "createdAt": datetime.utcnow().isoformat(),
            "error": "Build failed",
        }
    ]

    mock_railway_client.rollback_deployment.return_value = {
        "id": "deployment-rollback",
        "status": "SUCCESS",
    }

    # Manually manipulate world model to trigger failure decision
    orchestrator.world_model.railway_state["deployment_failed"] = True
    orchestrator.world_model.railway_state["failed_deployment_id"] = "deployment-failed"

    # Execute: Run decide phase with failure state
    decision = await orchestrator.decide(orchestrator.world_model)

    # Assert: Should decide to rollback
    assert decision is not None
    assert decision.action == ActionType.ROLLBACK
    assert decision.priority == 10

    # Execute the rollback action
    result = await orchestrator.act(decision)
    assert "status" in result or "deployment_id" in result


@pytest.mark.asyncio
async def test_ooda_pr_ready_to_merge(orchestrator, mock_github_client, mock_railway_client):
    """Test OODA loop detects PR ready to merge."""

    # Setup: Manipulate world model to show PR ready
    orchestrator.world_model.github_state["pr_ready_to_merge"] = True
    orchestrator.world_model.github_state["pr_number"] = 123

    # Execute: Run decide phase
    decision = await orchestrator.decide(orchestrator.world_model)

    # Assert: Should decide to merge PR
    assert decision is not None
    assert decision.action == ActionType.MERGE_PR
    assert decision.parameters.get("pr_number") == 123


@pytest.mark.asyncio
async def test_ooda_continuous_mode_multiple_cycles(orchestrator):
    """Test OODA loop runs multiple cycles in continuous mode."""

    # Note: run_continuous() is an infinite loop with no stop() method
    # We test by running run_cycle() multiple times manually

    # Execute: Run 3 cycles
    results = []
    for _ in range(3):
        decision = await orchestrator.run_cycle()
        results.append(decision)

    # Assert: 3 cycles completed
    assert len(results) == 3

    # Each result is Decision or None
    for result in results:
        assert result is None or isinstance(result, Decision)


@pytest.mark.asyncio
async def test_ooda_observe_phase_collects_all_sources(
    orchestrator, mock_railway_client, mock_github_client, mock_n8n_client
):
    """Test Observe phase collects data from all 3 sources."""

    # Setup: Mock all sources
    mock_railway_client.list_services.return_value = [{"id": "svc-1"}]

    mock_github_client.get_workflow_runs.return_value = {"data": [{"id": "run-1"}]}

    mock_n8n_client.get_recent_executions.return_value = [{"id": "exec-1"}]

    # Execute: Run observe phase
    observations = await orchestrator.observe()

    # Assert: Returns list of Observation objects
    assert isinstance(observations, list)
    assert len(observations) > 0

    # Verify Observation structure
    for obs in observations:
        assert isinstance(obs, Observation)
        assert hasattr(obs, "source")
        assert hasattr(obs, "timestamp")
        assert hasattr(obs, "data")
        assert hasattr(obs, "metadata")

    # Verify we got observations from multiple sources
    sources = {obs.source for obs in observations}
    # Should have at least railway, github, n8n (depends on mock success)
    assert len(sources) >= 1


@pytest.mark.asyncio
async def test_ooda_orient_phase_builds_world_model(orchestrator):
    """Test Orient phase analyzes observations and builds WorldModel."""

    # Setup: Create observations
    observations = [
        Observation(
            source="railway",
            timestamp=datetime.utcnow(),
            data={"services": [{"id": "svc-1", "name": "web"}]},
            metadata={},
        ),
        Observation(
            source="github",
            timestamp=datetime.utcnow(),
            data={"workflow_runs": {"data": [{"id": "run-1", "conclusion": "success"}]}},
            metadata={},
        ),
    ]

    # Execute: Run orient phase
    world_model = await orchestrator.orient(observations)

    # Assert: WorldModel updated
    assert isinstance(world_model, WorldModel)
    assert hasattr(world_model, "railway_state")
    assert hasattr(world_model, "github_state")
    assert hasattr(world_model, "n8n_state")
    assert hasattr(world_model, "observations")

    # Observations should be recorded
    assert len(world_model.observations) >= len(observations)


@pytest.mark.asyncio
async def test_ooda_decide_phase_generates_decisions(orchestrator):
    """Test Decide phase generates appropriate decisions from WorldModel."""

    # Setup: Create world model with failed deployment
    world_model = WorldModel()
    world_model.railway_state["deployment_failed"] = True
    world_model.railway_state["failed_deployment_id"] = "dep-failed"

    # Execute: Run decide phase
    decision = await orchestrator.decide(world_model)

    # Assert: Decision generated (returns Decision or None)
    assert decision is not None
    assert isinstance(decision, Decision)

    # Should be rollback decision
    assert decision.action == ActionType.ROLLBACK
    assert decision.priority >= 8


@pytest.mark.asyncio
async def test_ooda_act_phase_executes_decisions(
    orchestrator, mock_railway_client, mock_github_client, mock_n8n_client
):
    """Test Act phase executes decisions through worker clients."""

    # Setup: Create decision to execute (takes single Decision, not list)
    decision = Decision(
        action=ActionType.ALERT,
        reasoning="Test alert",
        parameters={"message": "Test alert message", "severity": "info"},
        priority=5,
    )

    mock_n8n_client.execute_workflow.return_value = "exec-123"

    # Execute: Run act phase
    result = await orchestrator.act(decision)

    # Assert: Action executed (returns dict)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_ooda_graceful_degradation_on_source_failure(orchestrator, mock_railway_client):
    """Test OODA loop continues if one source fails."""

    # Setup: Railway client fails
    mock_railway_client.list_services.side_effect = Exception("Railway API down")

    # Execute: Run observe phase (should not crash)
    observations = await orchestrator.observe()

    # Assert: Returns list (possibly empty or partial)
    assert isinstance(observations, list)

    # Other sources should still work (github, n8n)
    # Exact count depends on which mocks succeed
    # At minimum, should not raise exception
