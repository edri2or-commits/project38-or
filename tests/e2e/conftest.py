"""Pytest configuration for E2E tests."""

from unittest.mock import AsyncMock

import pytest

from src.github_app_client import GitHubAppClient
from src.n8n_client import N8nClient
from src.orchestrator import MainOrchestrator
from src.railway_client import RailwayClient


@pytest.fixture
def mock_railway_client():
    """Mock Railway client for E2E tests."""
    client = AsyncMock()

    # Mock deployment trigger (returns dict with deployment details)
    client.trigger_deployment.return_value = {
        "id": "deployment-123",
        "status": "BUILDING",
        "createdAt": "2026-01-13T12:00:00Z",
    }

    # Mock deployment monitoring
    client.get_deployment_status.return_value = "SUCCESS"
    client.get_deployment_details.return_value = {
        "id": "deployment-123",
        "status": "SUCCESS",
        "staticUrl": "https://test.railway.app",
    }

    # Mock service info (list_services is the actual method name)
    client.get_services.return_value = [
        {
            "id": "service-123",
            "name": "web",
            "latestDeployment": {"id": "deployment-123", "status": "SUCCESS"},
        }
    ]
    client.list_services.return_value = [
        {
            "id": "service-123",
            "name": "web",
            "latestDeployment": {"id": "deployment-123", "status": "SUCCESS"},
        }
    ]

    # Mock deployments list
    client.get_deployments.return_value = [
        {"id": "deployment-123", "status": "SUCCESS", "createdAt": "2026-01-13T12:00:00Z"}
    ]
    client.get_last_active_deployment.return_value = {
        "id": "deployment-123",
        "status": "SUCCESS",
        "createdAt": "2026-01-13T12:00:00Z",
    }

    # Mock rollback
    client.rollback_deployment.return_value = {"id": "deployment-rollback", "status": "SUCCESS"}

    return client


@pytest.fixture
def mock_github_client():
    """Mock GitHub App client for E2E tests."""
    client = AsyncMock()

    # Mock PR operations
    client.get_pull_request.return_value = {
        "number": 123,
        "state": "open",
        "mergeable": True,
        "head": {"sha": "abc123"},
    }

    client.create_issue.return_value = {
        "number": 456,
        "html_url": "https://github.com/test/repo/issues/456",
    }

    # Mock workflow operations
    client.trigger_workflow.return_value = {"id": "run-123"}
    client.get_workflow_runs.return_value = {
        "data": [
            {
                "id": "run-123",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-01-13T12:00:00Z",
            }
        ]
    }

    return client


@pytest.fixture
def mock_n8n_client():
    """Mock n8n client for E2E tests."""
    client = AsyncMock()

    # Mock workflow execution
    client.execute_workflow.return_value = {"executionId": "exec-123", "status": "success"}

    return client


@pytest.fixture
def orchestrator(mock_railway_client, mock_github_client, mock_n8n_client):
    """Create orchestrator with mocked clients."""
    return MainOrchestrator(
        railway=mock_railway_client,
        github=mock_github_client,
        n8n=mock_n8n_client,
        project_id="test-project",
        environment_id="test-environment",
    )
