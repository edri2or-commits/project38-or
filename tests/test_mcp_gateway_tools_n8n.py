"""Tests for MCP Gateway n8n tools.

Tests the n8n module in src/mcp_gateway/tools/n8n.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _can_import_n8n() -> bool:
    """Check if n8n module can be imported."""
    try:
        # Check tenacity first (required by railway which is imported by tools/__init__)
        import tenacity  # noqa
        from src.mcp_gateway.tools.n8n import (
            trigger_workflow,
            list_workflows,
            get_workflow_status,
            register_workflow,
            WORKFLOW_REGISTRY,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_import_n8n(),
    reason="mcp_gateway.tools.n8n module not importable"
)


class TestTriggerWorkflow:
    """Tests for trigger_workflow function."""

    @pytest.mark.asyncio
    async def test_trigger_workflow_no_base_url_returns_error(self):
        """Test that missing n8n_base_url returns error."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import trigger_workflow

        mock_config = MagicMock()
        mock_config.n8n_base_url = ""

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            result = await trigger_workflow("health-monitor")

        assert result["status"] == "error"
        assert "N8N_BASE_URL not configured" in result["message"]

    @pytest.mark.asyncio
    async def test_trigger_workflow_unknown_workflow_returns_error(self):
        """Test that unknown workflow name returns error."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import trigger_workflow

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            result = await trigger_workflow("nonexistent-workflow")

        assert result["status"] == "error"
        assert "Unknown workflow" in result["message"]
        assert "available_workflows" in result

    @pytest.mark.asyncio
    async def test_trigger_workflow_success_post(self):
        """Test successful POST workflow trigger."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import trigger_workflow

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await trigger_workflow("deploy-railway", data={"ref": "main"})

        assert result["status"] == "triggered"
        assert result["workflow"] == "deploy-railway"
        assert result["http_status"] == 200

    @pytest.mark.asyncio
    async def test_trigger_workflow_success_get(self):
        """Test successful GET workflow trigger."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import trigger_workflow

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"healthy": True}

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await trigger_workflow("health-monitor")

        assert result["status"] == "triggered"
        assert result["workflow"] == "health-monitor"

    @pytest.mark.asyncio
    async def test_trigger_workflow_timeout(self):
        """Test workflow timeout handling."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import trigger_workflow
        import httpx

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = httpx.TimeoutException("Timed out")
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await trigger_workflow("health-monitor")

        assert result["status"] == "error"
        assert "timed out" in result["message"]


class TestListWorkflows:
    """Tests for list_workflows function."""

    @pytest.mark.asyncio
    async def test_list_workflows_returns_all_registered(self):
        """Test that list_workflows returns all registered workflows."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import list_workflows, WORKFLOW_REGISTRY

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            result = await list_workflows()

        assert result["status"] == "success"
        assert result["count"] == len(WORKFLOW_REGISTRY)
        assert len(result["workflows"]) == len(WORKFLOW_REGISTRY)

    @pytest.mark.asyncio
    async def test_list_workflows_includes_workflow_details(self):
        """Test that each workflow has required details."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import list_workflows

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            result = await list_workflows()

        for workflow in result["workflows"]:
            assert "name" in workflow
            assert "webhook_url" in workflow
            assert "method" in workflow
            assert "description" in workflow


class TestGetWorkflowStatus:
    """Tests for get_workflow_status function."""

    @pytest.mark.asyncio
    async def test_get_status_no_base_url_returns_error(self):
        """Test that missing n8n_base_url returns error."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import get_workflow_status

        mock_config = MagicMock()
        mock_config.n8n_base_url = ""

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            result = await get_workflow_status("health-monitor")

        assert result["status"] == "error"
        assert "N8N_BASE_URL not configured" in result["message"]

    @pytest.mark.asyncio
    async def test_get_status_unknown_workflow_returns_error(self):
        """Test that unknown workflow returns error."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import get_workflow_status

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            result = await get_workflow_status("unknown-workflow")

        assert result["status"] == "error"
        assert "Unknown workflow" in result["message"]

    @pytest.mark.asyncio
    async def test_get_status_available(self):
        """Test status check for available workflow."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import get_workflow_status

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.options.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await get_workflow_status("health-monitor")

        assert result["status"] == "available"
        assert result["workflow"] == "health-monitor"
        assert "url" in result

    @pytest.mark.asyncio
    async def test_get_status_server_error(self):
        """Test status check for workflow with server error."""
        from src.mcp_gateway.tools import n8n as n8n_module
        from src.mcp_gateway.tools.n8n import get_workflow_status

        mock_config = MagicMock()
        mock_config.n8n_base_url = "http://n8n.local"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(n8n_module, "get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.options.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await get_workflow_status("health-monitor")

        assert result["status"] == "unavailable"
        assert "Server error" in result["message"]


class TestRegisterWorkflow:
    """Tests for register_workflow function."""

    def test_register_workflow_adds_to_registry(self):
        """Test that register_workflow adds a new workflow."""
        from src.mcp_gateway.tools.n8n import register_workflow, WORKFLOW_REGISTRY

        # Clean up test workflow if it exists from previous runs
        test_name = "test-workflow-xyz"
        if test_name in WORKFLOW_REGISTRY:
            del WORKFLOW_REGISTRY[test_name]

        register_workflow(
            name=test_name,
            path="/webhook/test-xyz",
            method="POST",
            description="Test workflow"
        )

        assert test_name in WORKFLOW_REGISTRY
        assert WORKFLOW_REGISTRY[test_name]["path"] == "/webhook/test-xyz"
        assert WORKFLOW_REGISTRY[test_name]["method"] == "POST"
        assert WORKFLOW_REGISTRY[test_name]["description"] == "Test workflow"

        # Clean up
        del WORKFLOW_REGISTRY[test_name]

    def test_register_workflow_default_method(self):
        """Test that register_workflow defaults to POST method."""
        from src.mcp_gateway.tools.n8n import register_workflow, WORKFLOW_REGISTRY

        test_name = "test-default-method"
        if test_name in WORKFLOW_REGISTRY:
            del WORKFLOW_REGISTRY[test_name]

        register_workflow(name=test_name, path="/webhook/test")

        assert WORKFLOW_REGISTRY[test_name]["method"] == "POST"

        # Clean up
        del WORKFLOW_REGISTRY[test_name]


class TestWorkflowRegistry:
    """Tests for WORKFLOW_REGISTRY constant."""

    def test_registry_has_required_workflows(self):
        """Test that registry contains expected workflows."""
        from src.mcp_gateway.tools.n8n import WORKFLOW_REGISTRY

        expected_workflows = ["health-monitor", "deploy-railway", "rollback-railway"]

        for workflow in expected_workflows:
            assert workflow in WORKFLOW_REGISTRY

    def test_registry_workflows_have_required_fields(self):
        """Test that each workflow has required fields."""
        from src.mcp_gateway.tools.n8n import WORKFLOW_REGISTRY

        for name, info in WORKFLOW_REGISTRY.items():
            assert "path" in info, f"{name} missing 'path'"
            assert "method" in info, f"{name} missing 'method'"
            assert info["method"] in ["GET", "POST"], f"{name} has invalid method"
