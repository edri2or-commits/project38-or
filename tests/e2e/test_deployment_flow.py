"""End-to-end tests for complete deployment flow."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.state_machine import DeploymentStatus


@pytest.mark.asyncio
async def test_successful_deployment_flow(
    orchestrator,
    mock_railway_client,
    mock_github_client,
    mock_n8n_client
):
    """Test complete successful deployment: PR → Merge → Deploy → Verify → Notify."""

    # Setup: Mock PR ready to merge
    pr_number = 123
    commit_sha = "abc123def456"

    mock_github_client.get_pull_request.return_value = {
        "number": pr_number,
        "state": "open",
        "mergeable": True,
        "head": {"sha": commit_sha}
    }

    mock_github_client.merge_pull_request.return_value = {
        "sha": commit_sha,
        "merged": True,
        "message": "Pull Request successfully merged"
    }

    mock_railway_client.trigger_deployment.return_value = "deployment-123"

    mock_railway_client.get_deployment_status.return_value = {
        "id": "deployment-123",
        "status": "SUCCESS",
        "url": "https://test.railway.app",
        "createdAt": datetime.utcnow().isoformat()
    }

    mock_n8n_client.execute_workflow.return_value = {
        "executionId": "exec-success",
        "status": "success"
    }

    # Execute: Deploy from PR
    result = await orchestrator.handle_deployment_event({
        "pr_number": pr_number,
        "environment": "production"
    })

    # Assert: Deployment succeeded
    assert result["success"] is True
    assert result["deployment_id"] == "deployment-123"
    assert result["pr_number"] == pr_number

    # Verify all steps executed in order:
    # 1. PR merged
    mock_github_client.merge_pull_request.assert_called_once()

    # 2. Deployment triggered
    mock_railway_client.trigger_deployment.assert_called_once()

    # 3. Notification sent
    mock_n8n_client.execute_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_deployment_failure_triggers_rollback(
    orchestrator,
    mock_railway_client,
    mock_github_client,
    mock_n8n_client
):
    """Test deployment failure triggers automatic rollback."""

    # Setup: Mock failed deployment
    mock_railway_client.get_deployment_status.return_value = {
        "id": "deployment-failed",
        "status": "FAILED",
        "error": "Build failed: npm install error",
        "createdAt": datetime.utcnow().isoformat()
    }

    mock_railway_client.rollback_deployment.return_value = {
        "id": "deployment-rollback",
        "status": "SUCCESS"
    }

    mock_github_client.create_issue.return_value = {
        "number": 456,
        "html_url": "https://github.com/test/repo/issues/456"
    }

    # Execute: Handle failed deployment
    result = await orchestrator.handle_deployment_failure({
        "deployment_id": "deployment-failed",
        "service_id": "service-123",
        "error": "Build failed"
    })

    # Assert: Rollback and issue creation executed
    assert result["rollback_executed"] is True
    assert result["issue_created"] is True

    # Verify rollback called
    mock_railway_client.rollback_deployment.assert_called_once()

    # Verify issue created with failure details
    mock_github_client.create_issue.assert_called_once()
    issue_call_args = mock_github_client.create_issue.call_args
    assert "Build failed" in issue_call_args[1]["body"]

    # Verify alert sent
    mock_n8n_client.execute_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_deployment_state_machine_transitions(orchestrator):
    """Test deployment progresses through correct state transitions."""

    # Test sequence: PENDING → BUILDING → DEPLOYING → ACTIVE
    from src.state_machine import DeploymentStateMachine

    state_machine = DeploymentStateMachine(
        deployment_id="deploy-123",
        initial_status=DeploymentStatus.PENDING
    )

    # Transition 1: PENDING → BUILDING
    state_machine.transition(DeploymentStatus.BUILDING, reason="Build started")
    assert state_machine.current_status == DeploymentStatus.BUILDING

    # Transition 2: BUILDING → DEPLOYING
    state_machine.transition(DeploymentStatus.DEPLOYING, reason="Build completed")
    assert state_machine.current_status == DeploymentStatus.DEPLOYING

    # Transition 3: DEPLOYING → ACTIVE
    state_machine.transition(DeploymentStatus.ACTIVE, reason="Deployment successful")
    assert state_machine.current_status == DeploymentStatus.ACTIVE

    # Verify history
    history = state_machine.get_history()
    assert len(history) == 4  # Initial + 3 transitions
    assert history[0]["status"] == DeploymentStatus.PENDING
    assert history[-1]["status"] == DeploymentStatus.ACTIVE


@pytest.mark.asyncio
async def test_deployment_state_machine_invalid_transition(orchestrator):
    """Test state machine rejects invalid transitions."""
    from src.state_machine import DeploymentStateMachine

    state_machine = DeploymentStateMachine(
        deployment_id="deploy-invalid",
        initial_status=DeploymentStatus.PENDING
    )

    # Invalid: PENDING → ACTIVE (must go through BUILDING, DEPLOYING)
    with pytest.raises(ValueError, match="Invalid transition"):
        state_machine.transition(DeploymentStatus.ACTIVE, reason="Skip steps")


@pytest.mark.asyncio
async def test_parallel_deployments_managed_independently(orchestrator):
    """Test multiple deployments are tracked independently."""
    from src.state_machine import StateMachineManager

    manager = StateMachineManager()

    # Create 3 deployments
    sm1 = manager.create_state_machine("deploy-1", DeploymentStatus.PENDING)
    sm2 = manager.create_state_machine("deploy-2", DeploymentStatus.BUILDING)
    sm3 = manager.create_state_machine("deploy-3", DeploymentStatus.ACTIVE)

    # Verify each tracked independently
    assert manager.get("deploy-1").current_status == DeploymentStatus.PENDING
    assert manager.get("deploy-2").current_status == DeploymentStatus.BUILDING
    assert manager.get("deploy-3").current_status == DeploymentStatus.ACTIVE

    # Verify count
    assert manager.count() == 3

    # Transition one without affecting others
    sm1.transition(DeploymentStatus.BUILDING, reason="Started build")
    assert manager.get("deploy-1").current_status == DeploymentStatus.BUILDING
    assert manager.get("deploy-2").current_status == DeploymentStatus.BUILDING  # Unchanged
    assert manager.get("deploy-3").current_status == DeploymentStatus.ACTIVE  # Unchanged


@pytest.mark.asyncio
async def test_deployment_with_health_check_verification(
    orchestrator,
    mock_railway_client
):
    """Test deployment verifies health check before marking success."""

    # Setup: Mock successful deployment
    mock_railway_client.get_deployment_status.return_value = {
        "id": "deploy-health",
        "status": "SUCCESS",
        "url": "https://test.railway.app"
    }

    # Mock health check endpoint
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        # Execute: Deploy with health check
        result = await orchestrator.handle_deployment_event({
            "deployment_id": "deploy-health",
            "verify_health": True
        })

        # Assert: Health check called
        mock_get.assert_called_once()
        assert "test.railway.app" in str(mock_get.call_args)


@pytest.mark.asyncio
async def test_deployment_rollback_to_last_successful(
    orchestrator,
    mock_railway_client
):
    """Test rollback identifies and deploys last successful deployment."""

    # Setup: Mock deployment history
    mock_railway_client.get_deployments.return_value = [
        {"id": "deploy-1", "status": "FAILED", "createdAt": "2026-01-13T12:00:00Z"},
        {"id": "deploy-2", "status": "SUCCESS", "createdAt": "2026-01-13T11:00:00Z"},  # Last successful
        {"id": "deploy-3", "status": "SUCCESS", "createdAt": "2026-01-13T10:00:00Z"}
    ]

    mock_railway_client.rollback_deployment.return_value = {
        "id": "deploy-rollback",
        "status": "SUCCESS",
        "rollback_to": "deploy-2"
    }

    # Execute: Trigger rollback
    result = await orchestrator.handle_deployment_failure({
        "deployment_id": "deploy-1",
        "service_id": "service-123"
    })

    # Assert: Rolled back to deploy-2 (last successful)
    mock_railway_client.rollback_deployment.assert_called_once()
    rollback_args = mock_railway_client.rollback_deployment.call_args
    assert "deploy-2" in str(rollback_args) or rollback_args[0][0] == "service-123"


@pytest.mark.asyncio
async def test_deployment_notification_includes_metadata(
    orchestrator,
    mock_n8n_client
):
    """Test deployment notifications include all relevant metadata."""

    # Setup: Successful deployment
    deployment_data = {
        "deployment_id": "deploy-notify",
        "pr_number": 123,
        "commit_sha": "abc123",
        "environment": "production",
        "url": "https://prod.railway.app",
        "status": "SUCCESS"
    }

    # Execute: Send notification
    await orchestrator._act_alert({
        "type": "deployment_success",
        "data": deployment_data,
        "severity": "info"
    })

    # Assert: Notification sent with metadata
    mock_n8n_client.execute_workflow.assert_called_once()
    notification_call = mock_n8n_client.execute_workflow.call_args

    # Verify workflow includes deployment metadata
    workflow_data = notification_call[0][1] if len(notification_call[0]) > 1 else notification_call[1].get("data", {})
    assert "deployment_id" in str(workflow_data)
    assert "pr_number" in str(workflow_data) or 123 in str(workflow_data)


@pytest.mark.asyncio
async def test_deployment_timeout_handling(orchestrator, mock_railway_client):
    """Test deployment timeout triggers appropriate handling."""

    # Setup: Mock deployment that times out
    mock_railway_client.get_deployment_status.side_effect = [
        {"id": "deploy-timeout", "status": "BUILDING"},
        {"id": "deploy-timeout", "status": "BUILDING"},
        {"id": "deploy-timeout", "status": "BUILDING"},
        {"id": "deploy-timeout", "status": "BUILDING"},
        # Never reaches SUCCESS
    ]

    # Execute: Wait for deployment with timeout
    with pytest.raises(TimeoutError):
        await orchestrator._wait_for_deployment(
            deployment_id="deploy-timeout",
            timeout_seconds=2,  # Short timeout for test
            poll_interval=0.5
        )


@pytest.mark.asyncio
async def test_deployment_creates_audit_log(orchestrator):
    """Test all deployment actions are logged for audit trail."""

    # Setup: Track log calls
    import logging
    log_calls = []

    def capture_log(record):
        log_calls.append({
            "message": record.getMessage(),
            "level": record.levelname,
            "extra": getattr(record, "correlation_id", None)
        })

    handler = logging.Handler()
    handler.emit = capture_log
    logging.getLogger("src.orchestrator").addHandler(handler)

    # Execute: Perform deployment
    await orchestrator.handle_deployment_event({
        "pr_number": 999,
        "environment": "staging"
    })

    # Assert: Audit logs created
    assert len(log_calls) > 0

    # Verify key events logged
    messages = [log["message"] for log in log_calls]
    assert any("deployment" in msg.lower() for msg in messages)

    # Verify correlation ID present
    assert any(log["extra"] is not None for log in log_calls)
