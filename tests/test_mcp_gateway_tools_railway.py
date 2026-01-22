"""Tests for MCP Gateway Railway tools.

Tests the railway module in src/mcp_gateway/tools/railway.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _has_tenacity() -> bool:
    """Check if tenacity module is available."""
    try:
        import tenacity
        return True
    except ImportError:
        return False


def _can_import_railway() -> bool:
    """Check if railway module can be imported."""
    try:
        from src.mcp_gateway.tools.railway import (
            trigger_deployment,
            get_deployment_status,
            get_recent_deployments,
            execute_rollback,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _has_tenacity(),
        reason="tenacity module not available"
    ),
    pytest.mark.skipif(
        not _can_import_railway(),
        reason="mcp_gateway.tools.railway module not importable"
    ),
]


class TestTriggerDeployment:
    """Tests for trigger_deployment function."""

    @pytest.mark.asyncio
    async def test_trigger_deployment_no_service_id_returns_error(self):
        """Test that missing service_id returns error."""
        from src.mcp_gateway.tools.railway import trigger_deployment

        mock_config = MagicMock()
        mock_config.railway_service_id = ""
        mock_config.railway_environment_id = "env-123"

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            result = await trigger_deployment()

        assert result["status"] == "error"
        assert "No service_id configured" in result["message"]

    @pytest.mark.asyncio
    async def test_trigger_deployment_success(self):
        """Test successful deployment trigger."""
        from src.mcp_gateway.tools.railway import trigger_deployment

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {"data": {"serviceInstanceRedeploy": True}}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await trigger_deployment()

        assert result["status"] == "triggered"
        assert result["service_id"] == "svc-123"
        assert result["environment_id"] == "env-456"

    @pytest.mark.asyncio
    async def test_trigger_deployment_with_custom_service_id(self):
        """Test deployment with custom service_id parameter."""
        from src.mcp_gateway.tools.railway import trigger_deployment

        mock_config = MagicMock()
        mock_config.railway_service_id = "default-svc"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {"data": {"serviceInstanceRedeploy": True}}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await trigger_deployment(service_id="custom-svc")

        assert result["service_id"] == "custom-svc"

    @pytest.mark.asyncio
    async def test_trigger_deployment_graphql_error(self):
        """Test handling of GraphQL errors."""
        from src.mcp_gateway.tools.railway import trigger_deployment

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {"errors": [{"message": "Service not found"}]}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await trigger_deployment()

        assert result["status"] == "error"
        assert "Service not found" in result["message"]


class TestGetDeploymentStatus:
    """Tests for get_deployment_status function."""

    @pytest.mark.asyncio
    async def test_get_status_no_service_id_returns_error(self):
        """Test that missing service_id returns error."""
        from src.mcp_gateway.tools.railway import get_deployment_status

        mock_config = MagicMock()
        mock_config.railway_service_id = ""
        mock_config.railway_environment_id = "env-123"

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            result = await get_deployment_status()

        assert result["status"] == "error"
        assert "No service_id configured" in result["message"]

    @pytest.mark.asyncio
    async def test_get_status_success_with_deployment(self):
        """Test successful status retrieval."""
        from src.mcp_gateway.tools.railway import get_deployment_status

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {
            "data": {
                "deployments": {
                    "edges": [
                        {"node": {"id": "dep-1", "status": "SUCCESS", "createdAt": "2026-01-22T10:00:00Z"}}
                    ]
                }
            }
        }

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await get_deployment_status()

        assert result["status"] == "success"
        assert result["current"]["id"] == "dep-1"
        assert result["current"]["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_get_status_no_deployments(self):
        """Test status when no deployments exist."""
        from src.mcp_gateway.tools.railway import get_deployment_status

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {"data": {"deployments": {"edges": []}}}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await get_deployment_status()

        assert result["status"] == "success"
        assert result["current"] is None
        assert "No deployments found" in result["message"]


class TestGetRecentDeployments:
    """Tests for get_recent_deployments function."""

    @pytest.mark.asyncio
    async def test_get_recent_deployments_success(self):
        """Test successful retrieval of recent deployments."""
        from src.mcp_gateway.tools.railway import get_recent_deployments

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {
            "data": {
                "deployments": {
                    "edges": [
                        {"node": {"id": "dep-1", "status": "SUCCESS", "createdAt": "2026-01-22T10:00:00Z"}},
                        {"node": {"id": "dep-2", "status": "FAILED", "createdAt": "2026-01-22T09:00:00Z"}},
                    ]
                }
            }
        }

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await get_recent_deployments(count=5)

        assert result["status"] == "success"
        assert result["count"] == 2
        assert len(result["deployments"]) == 2
        assert result["deployments"][0]["id"] == "dep-1"

    @pytest.mark.asyncio
    async def test_get_recent_deployments_custom_count(self):
        """Test that count parameter is passed to query."""
        from src.mcp_gateway.tools.railway import get_recent_deployments

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        mock_response = {"data": {"deployments": {"edges": []}}}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                await get_recent_deployments(count=10)

        # Verify count was passed in variables
        call_args = mock_req.call_args
        assert call_args[0][1]["first"] == 10


class TestExecuteRollback:
    """Tests for execute_rollback function."""

    @pytest.mark.asyncio
    async def test_rollback_with_deployment_id(self):
        """Test rollback with specific deployment ID."""
        from src.mcp_gateway.tools.railway import execute_rollback

        mock_config = MagicMock()
        mock_config.railway_token = "token"

        mock_response = {"data": {"deploymentRollback": {"id": "new-dep", "status": "DEPLOYING"}}}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await execute_rollback(deployment_id="old-dep-id")

        assert result["status"] == "rollback_initiated"
        assert result["deployment_id"] == "new-dep"
        assert result["target_deployment"] == "old-dep-id"

    @pytest.mark.asyncio
    async def test_rollback_auto_find_last_success(self):
        """Test rollback auto-finds last successful deployment."""
        from src.mcp_gateway.tools.railway import execute_rollback

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        # First call returns recent deployments
        recent_response = {
            "data": {
                "deployments": {
                    "edges": [
                        {"node": {"id": "dep-1", "status": "FAILED", "createdAt": "2026-01-22T10:00:00Z"}},
                        {"node": {"id": "dep-2", "status": "SUCCESS", "createdAt": "2026-01-22T09:00:00Z"}},
                    ]
                }
            }
        }
        # Second call does the rollback
        rollback_response = {"data": {"deploymentRollback": {"id": "new-dep", "status": "DEPLOYING"}}}

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.side_effect = [recent_response, rollback_response]
                result = await execute_rollback()

        assert result["status"] == "rollback_initiated"
        assert result["target_deployment"] == "dep-2"  # Found the SUCCESS one

    @pytest.mark.asyncio
    async def test_rollback_no_successful_deployment_found(self):
        """Test rollback error when no successful deployment exists."""
        from src.mcp_gateway.tools.railway import execute_rollback

        mock_config = MagicMock()
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_token = "token"

        recent_response = {
            "data": {
                "deployments": {
                    "edges": [
                        {"node": {"id": "dep-1", "status": "FAILED", "createdAt": "2026-01-22T10:00:00Z"}},
                        {"node": {"id": "dep-2", "status": "FAILED", "createdAt": "2026-01-22T09:00:00Z"}},
                    ]
                }
            }
        }

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("src.mcp_gateway.tools.railway._graphql_request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = recent_response
                result = await execute_rollback()

        assert result["status"] == "error"
        assert "No successful deployment found" in result["message"]


class TestGraphQLRequest:
    """Tests for _graphql_request internal function."""

    @pytest.mark.asyncio
    async def test_graphql_request_uses_config_token(self):
        """Test that GraphQL request uses token from config."""
        from src.mcp_gateway.tools.railway import _graphql_request
        import httpx

        mock_config = MagicMock()
        mock_config.railway_token = "test-bearer-token"

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"test": True}}
        mock_response.raise_for_status = MagicMock()

        with patch("src.mcp_gateway.tools.railway.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await _graphql_request("query { test }")

        # Verify token was used in header
        call_args = mock_instance.post.call_args
        assert "Bearer test-bearer-token" in call_args.kwargs["headers"]["Authorization"]
