"""Tests for Railway GraphQL API client."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.railway_client import (
    DeploymentStatus,
    RailwayAPIError,
    RailwayAuthenticationError,
    RailwayClient,
    RailwayRateLimitError,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def railway_client():
    """Create Railway client with test token."""
    return RailwayClient(api_token="test-token-123")


@pytest.fixture
def mock_httpx_response():
    """Create mock httpx response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"data": {}}
    return response


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


def test_railway_client_initialization(railway_client):
    """Test RailwayClient initialization."""
    assert railway_client.api_token == "test-token-123"
    assert railway_client.base_url == "https://backboard.railway.com/graphql/v2"


def test_build_url_cloudflare_workaround(railway_client):
    """Test URL building with Cloudflare workaround (timestamp)."""
    url = railway_client._build_url()
    assert url.startswith("https://backboard.railway.com/graphql/v2?t=")
    # Verify timestamp is recent (within last 5 seconds)
    timestamp = int(url.split("?t=")[1])
    assert abs(time.time() - timestamp) < 5


# =============================================================================
# GRAPHQL EXECUTION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_execute_graphql_success(railway_client, mock_httpx_response):
    """Test successful GraphQL execution."""
    mock_httpx_response.json.return_value = {
        "data": {"deployment": {"id": "deploy-123", "status": "ACTIVE"}}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        result = await railway_client._execute_graphql(
            "query { deployment(id: $id) { id status } }",
            {"id": "deploy-123"},
        )

        assert result == {"deployment": {"id": "deploy-123", "status": "ACTIVE"}}
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_execute_graphql_authentication_error(railway_client):
    """Test GraphQL execution with 401 Unauthorized."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(RailwayAuthenticationError, match="Invalid or expired"):
            await railway_client._execute_graphql("query { test }")


@pytest.mark.asyncio
async def test_execute_graphql_rate_limit_error(railway_client):
    """Test GraphQL execution with 429 Rate Limit."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(RailwayRateLimitError, match="Rate limit exceeded"):
            await railway_client._execute_graphql("query { test }")


@pytest.mark.asyncio
async def test_execute_graphql_errors_in_response(railway_client):
    """Test GraphQL execution with GraphQL-level errors."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "errors": [
            {"message": "Deployment not found"},
            {"message": "Invalid service ID"},
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(RailwayAPIError, match="Deployment not found.*Invalid service ID"):
            await railway_client._execute_graphql("query { test }")


@pytest.mark.asyncio
async def test_execute_graphql_timeout(railway_client):
    """Test GraphQL execution with timeout."""
    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("Request timed out"),
    ):
        with pytest.raises(RailwayAPIError, match="Request timed out after 30s"):
            await railway_client._execute_graphql("query { test }")


# =============================================================================
# DEPLOYMENT OPERATIONS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_trigger_deployment(railway_client, mock_httpx_response):
    """Test triggering a new deployment."""
    mock_httpx_response.json.return_value = {"data": {"serviceInstanceDeploy": "deploy-new-123"}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        deployment_id = await railway_client.trigger_deployment(
            environment_id="env-456", service_id="svc-789"
        )

        assert deployment_id == "deploy-new-123"
        # Verify mutation was called with correct variables
        call_args = mock_post.call_args
        assert call_args[1]["json"]["variables"]["environmentId"] == "env-456"
        assert call_args[1]["json"]["variables"]["serviceId"] == "svc-789"


@pytest.mark.asyncio
async def test_get_deployment_status(railway_client, mock_httpx_response):
    """Test getting deployment status."""
    mock_httpx_response.json.return_value = {
        "data": {"deployment": {"id": "deploy-123", "status": "BUILDING"}}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        status = await railway_client.get_deployment_status("deploy-123")

        assert status == "BUILDING"


@pytest.mark.asyncio
async def test_get_deployment_details(railway_client, mock_httpx_response):
    """Test getting full deployment details."""
    mock_httpx_response.json.return_value = {
        "data": {
            "deployment": {
                "id": "deploy-123",
                "status": "ACTIVE",
                "staticUrl": "https://my-app.railway.app",
                "createdAt": "2026-01-13T10:00:00Z",
                "updatedAt": "2026-01-13T10:05:00Z",
                "meta": {"branch": "main"},
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        details = await railway_client.get_deployment_details("deploy-123")

        assert isinstance(details, DeploymentStatus)
        assert details.id == "deploy-123"
        assert details.status == "ACTIVE"
        assert details.static_url == "https://my-app.railway.app"
        assert details.meta == {"branch": "main"}


@pytest.mark.asyncio
async def test_rollback_deployment(railway_client, mock_httpx_response):
    """Test rolling back to previous deployment."""
    mock_httpx_response.json.return_value = {
        "data": {"serviceInstanceRedeploy": "deploy-rollback-456"}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        new_deployment_id = await railway_client.rollback_deployment("deploy-old-123")

        assert new_deployment_id == "deploy-rollback-456"


@pytest.mark.asyncio
async def test_get_last_active_deployment(railway_client, mock_httpx_response):
    """Test getting last active deployment."""
    mock_httpx_response.json.return_value = {
        "data": {
            "deployments": {
                "edges": [
                    {
                        "node": {
                            "id": "deploy-failed-123",
                            "status": "FAILED",
                            "createdAt": "2026-01-13T12:00:00Z",
                        }
                    },
                    {
                        "node": {
                            "id": "deploy-active-456",
                            "status": "ACTIVE",
                            "createdAt": "2026-01-13T11:00:00Z",
                        }
                    },
                    {
                        "node": {
                            "id": "deploy-old-789",
                            "status": "ACTIVE",
                            "createdAt": "2026-01-13T10:00:00Z",
                        }
                    },
                ]
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        last_active = await railway_client.get_last_active_deployment(
            project_id="proj-123", environment_id="env-456"
        )

        # Should return first ACTIVE deployment (most recent)
        assert last_active["id"] == "deploy-active-456"
        assert last_active["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_get_last_active_deployment_none(railway_client, mock_httpx_response):
    """Test get_last_active_deployment when no ACTIVE deployment exists."""
    mock_httpx_response.json.return_value = {
        "data": {
            "deployments": {
                "edges": [
                    {
                        "node": {
                            "id": "deploy-1",
                            "status": "FAILED",
                            "createdAt": "2026-01-13T12:00:00Z",
                        }
                    },
                    {
                        "node": {
                            "id": "deploy-2",
                            "status": "CRASHED",
                            "createdAt": "2026-01-13T11:00:00Z",
                        }
                    },
                ]
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        last_active = await railway_client.get_last_active_deployment(
            project_id="proj-123", environment_id="env-456"
        )

        assert last_active is None


# =============================================================================
# MONITORING & LOGS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_build_logs(railway_client, mock_httpx_response):
    """Test getting build logs."""
    mock_httpx_response.json.return_value = {
        "data": {
            "buildLogs": {
                "lines": [
                    {
                        "message": "Installing dependencies...",
                        "timestamp": "2026-01-13T10:00:00Z",
                        "severity": "INFO",
                    },
                    {
                        "message": "Build failed: syntax error",
                        "timestamp": "2026-01-13T10:01:00Z",
                        "severity": "ERROR",
                    },
                ]
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        logs = await railway_client.get_build_logs("deploy-123", limit=50)

        assert len(logs) == 2
        assert logs[0]["message"] == "Installing dependencies..."
        assert logs[1]["severity"] == "ERROR"


@pytest.mark.asyncio
async def test_get_runtime_logs(railway_client, mock_httpx_response):
    """Test getting runtime logs."""
    mock_httpx_response.json.return_value = {
        "data": {
            "runtimeLogs": {
                "lines": [
                    {
                        "message": "Server started on port 8000",
                        "timestamp": "2026-01-13T10:05:00Z",
                        "severity": "INFO",
                    },
                    {
                        "message": "Uncaught exception: ConnectionError",
                        "timestamp": "2026-01-13T10:06:00Z",
                        "severity": "ERROR",
                    },
                ]
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        logs = await railway_client.get_runtime_logs("deploy-123")

        assert len(logs) == 2
        assert logs[1]["message"] == "Uncaught exception: ConnectionError"


@pytest.mark.asyncio
async def test_get_deployment_metrics(railway_client, mock_httpx_response):
    """Test getting deployment metrics."""
    mock_httpx_response.json.return_value = {
        "data": {
            "deploymentMetrics": {
                "cpuUsage": 45.2,
                "memoryUsage": 512.8,
                "requestCount": 1234,
                "responseTime": 125.5,
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        metrics = await railway_client.get_deployment_metrics("deploy-123")

        assert metrics["cpuUsage"] == 45.2
        assert metrics["memoryUsage"] == 512.8
        assert metrics["requestCount"] == 1234


# =============================================================================
# AUTONOMOUS MONITORING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_monitor_deployment_until_stable_success(railway_client):
    """Test monitoring deployment until ACTIVE."""
    # Mock responses: INITIALIZING → BUILDING → DEPLOYING → ACTIVE
    mock_responses = [
        {"data": {"deployment": {"id": "deploy-123", "status": "INITIALIZING"}}},
        {"data": {"deployment": {"id": "deploy-123", "status": "BUILDING"}}},
        {"data": {"deployment": {"id": "deploy-123", "status": "DEPLOYING"}}},
        {"data": {"deployment": {"id": "deploy-123", "status": "ACTIVE"}}},
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda r=resp: r) for resp in mock_responses
        ]

        final_status = await railway_client.monitor_deployment_until_stable(
            "deploy-123", timeout_seconds=60, poll_interval=0.1
        )

        assert final_status == "ACTIVE"
        assert mock_post.call_count == 4


@pytest.mark.asyncio
async def test_monitor_deployment_until_stable_failed(railway_client):
    """Test monitoring deployment that fails during build."""
    mock_responses = [
        {"data": {"deployment": {"id": "deploy-123", "status": "INITIALIZING"}}},
        {"data": {"deployment": {"id": "deploy-123", "status": "BUILDING"}}},
        {"data": {"deployment": {"id": "deploy-123", "status": "FAILED"}}},
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda r=resp: r) for resp in mock_responses
        ]

        final_status = await railway_client.monitor_deployment_until_stable(
            "deploy-123", timeout_seconds=60, poll_interval=0.1
        )

        assert final_status == "FAILED"


@pytest.mark.asyncio
async def test_monitor_deployment_timeout(railway_client):
    """Test monitoring deployment that times out."""
    # Always return BUILDING (transient state)
    mock_response = {"data": {"deployment": {"id": "deploy-123", "status": "BUILDING"}}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response)

        with pytest.raises(TimeoutError, match="did not stabilize within"):
            await railway_client.monitor_deployment_until_stable(
                "deploy-123", timeout_seconds=1, poll_interval=0.1
            )


@pytest.mark.asyncio
async def test_monitor_deployment_unknown_status(railway_client):
    """Test monitoring deployment with unknown status."""
    mock_response = {"data": {"deployment": {"id": "deploy-123", "status": "UNKNOWN_STATE"}}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response)

        with pytest.raises(ValueError, match="Unknown deployment status"):
            await railway_client.monitor_deployment_until_stable(
                "deploy-123", timeout_seconds=10, poll_interval=0.1
            )


# =============================================================================
# SERVICE MANAGEMENT TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_list_services(railway_client, mock_httpx_response):
    """Test listing services."""
    mock_httpx_response.json.return_value = {
        "data": {
            "project": {
                "services": {
                    "edges": [
                        {
                            "node": {
                                "id": "svc-1",
                                "name": "web",
                                "icon": "🌐",
                                "createdAt": "2026-01-01T00:00:00Z",
                            }
                        },
                        {
                            "node": {
                                "id": "svc-2",
                                "name": "postgres",
                                "icon": "🐘",
                                "createdAt": "2026-01-02T00:00:00Z",
                            }
                        },
                    ]
                }
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        services = await railway_client.list_services(
            project_id="proj-123", environment_id="env-456"
        )

        assert len(services) == 2
        assert services[0]["name"] == "web"
        assert services[1]["name"] == "postgres"


@pytest.mark.asyncio
async def test_get_service_details(railway_client, mock_httpx_response):
    """Test getting service details."""
    mock_httpx_response.json.return_value = {
        "data": {
            "service": {
                "id": "svc-123",
                "name": "web",
                "icon": "🌐",
                "createdAt": "2026-01-01T00:00:00Z",
                "deployments": {
                    "edges": [
                        {
                            "node": {
                                "id": "deploy-1",
                                "status": "ACTIVE",
                                "createdAt": "2026-01-13T10:00:00Z",
                            }
                        },
                        {
                            "node": {
                                "id": "deploy-2",
                                "status": "FAILED",
                                "createdAt": "2026-01-13T09:00:00Z",
                            }
                        },
                    ]
                },
            }
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        details = await railway_client.get_service_details("svc-123")

        assert details["name"] == "web"
        assert len(details["deployments"]) == 2
        assert details["deployments"][0]["status"] == "ACTIVE"


# =============================================================================
# ENVIRONMENT VARIABLES TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_set_environment_variable(railway_client, mock_httpx_response):
    """Test setting environment variable."""
    mock_httpx_response.json.return_value = {"data": {"variableUpsert": {"id": "var-123"}}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        await railway_client.set_environment_variable(
            service_id="svc-123",
            environment_id="env-456",
            key="MAX_WORKERS",
            value="4",
        )

        # Verify mutation was called with correct variables
        call_args = mock_post.call_args
        variables = call_args[1]["json"]["variables"]
        assert variables["key"] == "MAX_WORKERS"
        assert variables["value"] == "4"
