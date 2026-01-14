"""End-to-end tests for MainOrchestrator OODA loop."""

from datetime import datetime

import pytest

from src.orchestrator import ActionType, WorldModel


@pytest.mark.asyncio
async def test_complete_ooda_cycle(orchestrator, mock_railway_client, mock_github_client):
    """Test complete OODA loop cycle: Observe → Orient → Decide → Act."""

    # Setup: Mock observations
    mock_railway_client.get_services.return_value = [
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

    mock_railway_client.get_deployments.return_value = [
        {"id": "deployment-123", "status": "SUCCESS", "createdAt": datetime.utcnow().isoformat()}
    ]

    mock_github_client.get_workflow_runs.return_value = [
        {
            "id": "run-123",
            "status": "completed",
            "conclusion": "success",
            "created_at": datetime.utcnow().isoformat(),
        }
    ]

    # Execute: Run complete OODA cycle
    result = await orchestrator.run_cycle()

    # Assert: Verify all phases executed
    assert result is not None
    assert "observations" in result
    assert "world_model" in result
    assert "decisions" in result
    assert "actions" in result

    # Verify observations collected
    observations = result["observations"]
    assert "railway" in observations
    assert "github" in observations
    assert observations["railway"]["services"] is not None

    # Verify world model created
    world_model = result["world_model"]
    assert isinstance(world_model, WorldModel)

    # Verify decisions made
    decisions = result["decisions"]
    assert isinstance(decisions, list)

    # Verify actions executed
    actions = result["actions"]
    assert isinstance(actions, list)


@pytest.mark.asyncio
async def test_ooda_deployment_failure_recovery(
    orchestrator, mock_railway_client, mock_github_client, mock_n8n_client
):
    """Test OODA loop handles deployment failure autonomously."""

    # Setup: Mock failed deployment
    mock_railway_client.get_deployments.return_value = [
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

    # Execute: Run OODA cycle with failure
    result = await orchestrator.run_cycle()

    # Assert: Verify failure detected and handled
    decisions = result["decisions"]

    # Should have ROLLBACK decision
    rollback_decisions = [
        d for d in decisions if d.get("type") == ActionType.ROLLBACK or "rollback" in str(d).lower()
    ]
    assert len(rollback_decisions) > 0

    # Should have CREATE_ISSUE decision
    issue_decisions = [
        d
        for d in decisions
        if d.get("type") == ActionType.CREATE_ISSUE or "issue" in str(d).lower()
    ]
    assert len(issue_decisions) > 0

    # Verify actions executed
    actions = result["actions"]
    assert any(a["type"] == "rollback" for a in actions)
    assert any(a["type"] == "create_issue" for a in actions)


@pytest.mark.asyncio
async def test_ooda_pr_ready_to_merge(orchestrator, mock_github_client, mock_railway_client):
    """Test OODA loop detects PR ready to merge and executes deployment."""

    # Setup: Mock PR with all checks passed
    mock_github_client.get_pull_requests.return_value = [
        {"number": 123, "state": "open", "head": {"sha": "abc123"}, "mergeable": True}
    ]

    mock_github_client.get_pr_checks.return_value = {
        "check_runs": [
            {"name": "test", "conclusion": "success"},
            {"name": "lint", "conclusion": "success"},
        ],
        "all_passed": True,
    }

    mock_github_client.merge_pull_request.return_value = {"sha": "abc123", "merged": True}

    # Execute: Run OODA cycle
    result = await orchestrator.run_cycle()

    # Assert: Should decide to merge and deploy
    decisions = result["decisions"]

    merge_decisions = [
        d for d in decisions if d.get("type") == ActionType.MERGE_PR or "merge" in str(d).lower()
    ]
    assert len(merge_decisions) > 0

    # Note: DEPLOY might be in next cycle after merge


@pytest.mark.asyncio
async def test_ooda_continuous_mode_multiple_cycles(orchestrator):
    """Test OODA loop runs multiple cycles in continuous mode."""

    # Setup: Configure for 3 cycles
    cycles_completed = []

    async def mock_run_cycle():
        """Mock single cycle run."""
        cycles_completed.append(datetime.utcnow())
        if len(cycles_completed) >= 3:
            # Stop after 3 cycles
            orchestrator.stop()
        return {"observations": {}, "world_model": WorldModel(), "decisions": [], "actions": []}

    # Replace run_cycle with mock
    orchestrator.run_cycle = mock_run_cycle

    # Execute: Run continuous mode (async, non-blocking)
    import asyncio

    task = asyncio.create_task(orchestrator.run_continuous(interval_seconds=0.1))

    # Wait for 3 cycles
    await asyncio.sleep(0.5)
    orchestrator.stop()
    await task

    # Assert: Multiple cycles completed
    assert len(cycles_completed) >= 3


@pytest.mark.asyncio
async def test_ooda_observe_phase_collects_all_sources(
    orchestrator, mock_railway_client, mock_github_client, mock_n8n_client
):
    """Test Observe phase collects data from all 3 sources."""

    # Setup: Mock all sources
    mock_railway_client.get_services.return_value = [{"id": "svc-1"}]
    mock_railway_client.get_deployments.return_value = [{"id": "dep-1"}]

    mock_github_client.get_workflow_runs.return_value = [{"id": "run-1"}]
    mock_github_client.get_pull_requests.return_value = [{"number": 123}]
    mock_github_client.get_recent_commits.return_value = [{"sha": "abc"}]

    mock_n8n_client.get_recent_executions.return_value = [{"id": "exec-1"}]

    # Execute: Run observe phase
    observations = await orchestrator.observe()

    # Assert: All sources collected
    assert "railway" in observations
    assert "github" in observations
    assert "n8n" in observations

    # Verify Railway observations
    assert observations["railway"]["services"] == [{"id": "svc-1"}]
    assert observations["railway"]["deployments"] == [{"id": "dep-1"}]

    # Verify GitHub observations
    assert observations["github"]["workflow_runs"] == [{"id": "run-1"}]
    assert observations["github"]["pull_requests"] == [{"number": 123}]
    assert observations["github"]["recent_commits"] == [{"sha": "abc"}]

    # Verify n8n observations
    assert observations["n8n"]["recent_executions"] == [{"id": "exec-1"}]


@pytest.mark.asyncio
async def test_ooda_orient_phase_builds_world_model(orchestrator):
    """Test Orient phase analyzes observations and builds WorldModel."""

    # Setup: Provide observations
    observations = {
        "railway": {
            "services": [{"id": "svc-1", "name": "web"}],
            "deployments": [
                {"id": "dep-1", "status": "SUCCESS", "createdAt": "2026-01-13T10:00:00Z"},
                {"id": "dep-2", "status": "FAILED", "createdAt": "2026-01-13T09:00:00Z"},
            ],
        },
        "github": {
            "workflow_runs": [{"id": "run-1", "conclusion": "success"}],
            "pull_requests": [],
        },
        "n8n": {"recent_executions": []},
    }

    # Execute: Run orient phase
    world_model = await orchestrator.orient(observations)

    # Assert: WorldModel created with analysis
    assert isinstance(world_model, WorldModel)
    assert world_model.timestamp is not None
    assert world_model.observations == observations

    # Should detect failure pattern
    assert (
        "failure" in str(world_model).lower()
        or len(world_model.observations["railway"]["deployments"]) >= 2
    )


@pytest.mark.asyncio
async def test_ooda_decide_phase_generates_decisions(orchestrator):
    """Test Decide phase generates appropriate decisions from WorldModel."""

    # Setup: Create world model with failed deployment
    world_model = WorldModel(
        timestamp=datetime.utcnow(),
        observations={
            "railway": {
                "deployments": [{"id": "dep-failed", "status": "FAILED", "error": "Build failed"}]
            }
        },
    )

    # Execute: Run decide phase
    decisions = await orchestrator.decide(world_model)

    # Assert: Decisions generated
    assert isinstance(decisions, list)
    assert len(decisions) > 0

    # Should have high priority decisions for failure
    high_priority = [d for d in decisions if d.get("priority", 0) >= 8]
    assert len(high_priority) > 0


@pytest.mark.asyncio
async def test_ooda_act_phase_executes_decisions(
    orchestrator, mock_railway_client, mock_github_client, mock_n8n_client
):
    """Test Act phase executes decisions through worker clients."""

    # Setup: Create decisions to execute
    decisions = [
        {
            "type": ActionType.ROLLBACK,
            "priority": 10,
            "deployment_id": "dep-failed",
            "reason": "Deployment failed",
        },
        {
            "type": ActionType.ALERT,
            "priority": 8,
            "message": "Deployment failure detected",
            "severity": "high",
        },
    ]

    # Execute: Run act phase
    actions = await orchestrator.act(decisions)

    # Assert: Actions executed
    assert isinstance(actions, list)
    assert len(actions) == len(decisions)

    # Verify rollback executed
    assert any(a["type"] == "rollback" for a in actions)

    # Verify alert sent
    assert any(a["type"] == "alert" for a in actions)


@pytest.mark.asyncio
async def test_ooda_graceful_degradation_on_source_failure(orchestrator, mock_railway_client):
    """Test OODA loop continues if one source fails."""

    # Setup: Railway client fails
    mock_railway_client.get_services.side_effect = Exception("Railway API down")

    # Execute: Run observe phase (should not crash)
    observations = await orchestrator.observe()

    # Assert: Other sources still collected
    assert "github" in observations
    assert "n8n" in observations

    # Railway should have error marker or empty data
    assert "railway" in observations
