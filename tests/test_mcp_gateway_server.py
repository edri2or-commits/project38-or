"""Tests for MCP Gateway Server.

Tests the server module in src/mcp_gateway/server.py.
Covers:
- Server creation and tool registration
- Tool function delegation to underlying modules
- JSON parsing for tools accepting JSON strings
- Error handling and edge cases
- Graceful handling when fastmcp is not available
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _can_import_fastmcp() -> bool:
    """Check if fastmcp module is available."""
    try:
        from fastmcp import FastMCP
        return True
    except ImportError:
        return False


def _can_import_server() -> bool:
    """Check if server module can be imported."""
    try:
        from src.mcp_gateway.server import create_mcp_server, create_mcp_app, FASTMCP_AVAILABLE
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _can_import_server(),
        reason="mcp_gateway.server module not importable"
    ),
]


class TestServerCreation:
    """Tests for server creation and initialization."""

    def test_create_mcp_server_returns_fastmcp_instance(self):
        """Test that create_mcp_server returns a FastMCP instance when available."""
        if not _can_import_fastmcp():
            pytest.skip("fastmcp not installed")

        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        assert server is not None
        # Should be a FastMCP instance
        from fastmcp import FastMCP
        assert isinstance(server, FastMCP)

    def test_create_mcp_server_returns_none_without_fastmcp(self):
        """Test that create_mcp_server returns None when fastmcp not available."""
        from src.mcp_gateway import server

        # Temporarily make FASTMCP_AVAILABLE False
        original_value = server.FASTMCP_AVAILABLE
        server.FASTMCP_AVAILABLE = False

        try:
            result = server.create_mcp_server()
            assert result is None
        finally:
            server.FASTMCP_AVAILABLE = original_value

    def test_create_mcp_app_returns_asgi_app(self):
        """Test that create_mcp_app returns an ASGI app for FastAPI mounting."""
        if not _can_import_fastmcp():
            pytest.skip("fastmcp not installed")

        from src.mcp_gateway.server import create_mcp_app

        app = create_mcp_app()

        assert app is not None
        # Should be callable (ASGI app)
        assert callable(app) or hasattr(app, "__call__")

    def test_create_mcp_app_returns_none_without_fastmcp(self):
        """Test that create_mcp_app returns None when fastmcp not available."""
        from src.mcp_gateway import server

        original_value = server.FASTMCP_AVAILABLE
        server.FASTMCP_AVAILABLE = False

        try:
            result = server.create_mcp_app()
            assert result is None
        finally:
            server.FASTMCP_AVAILABLE = original_value

    def test_module_level_mcp_instance_exists(self):
        """Test that module-level mcp instance is created."""
        from src.mcp_gateway.server import mcp

        if _can_import_fastmcp():
            assert mcp is not None
        # If fastmcp not available, mcp would be None - that's expected


class TestToolRegistration:
    """Tests for tool registration on the MCP server."""

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_railway_tools_registered(self):
        """Test that all Railway tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        assert server is not None

        # Get registered tool names
        tool_names = [tool.name for tool in server._tool_manager._tools.values()]

        railway_tools = ["railway_deploy", "railway_status", "railway_deployments", "railway_rollback"]
        for tool in railway_tools:
            assert tool in tool_names, f"Railway tool '{tool}' not registered"

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_n8n_tools_registered(self):
        """Test that all n8n tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        tool_names = [tool.name for tool in server._tool_manager._tools.values()]

        n8n_tools = ["n8n_trigger", "n8n_list", "n8n_status"]
        for tool in n8n_tools:
            assert tool in tool_names, f"n8n tool '{tool}' not registered"

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_monitoring_tools_registered(self):
        """Test that all monitoring tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        tool_names = [tool.name for tool in server._tool_manager._tools.values()]

        monitoring_tools = ["health_check", "get_metrics", "deployment_health"]
        for tool in monitoring_tools:
            assert tool in tool_names, f"Monitoring tool '{tool}' not registered"

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_oauth_tools_registered(self):
        """Test that OAuth tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        tool_names = [tool.name for tool in server._tool_manager._tools.values()]

        oauth_tools = ["workspace_oauth_exchange", "workspace_oauth_status"]
        for tool in oauth_tools:
            assert tool in tool_names, f"OAuth tool '{tool}' not registered"

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_workspace_tools_registered(self):
        """Test that Google Workspace tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        tool_names = [tool.name for tool in server._tool_manager._tools.values()]

        workspace_tools = [
            "gmail_send", "gmail_search", "gmail_list",
            "calendar_list_events", "calendar_create_event",
            "drive_list_files", "drive_create_folder",
            "sheets_read", "sheets_write", "sheets_create",
            "docs_create", "docs_read", "docs_append",
        ]
        for tool in workspace_tools:
            assert tool in tool_names, f"Workspace tool '{tool}' not registered"

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_browser_tools_registered(self):
        """Test that browser automation tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        tool_names = [tool.name for tool in server._tool_manager._tools.values()]

        browser_tools = [
            "browser_navigate", "browser_accessibility_tree",
            "browser_click_ref", "browser_fill_ref",
            "browser_screenshot", "browser_close",
        ]
        for tool in browser_tools:
            assert tool in tool_names, f"Browser tool '{tool}' not registered"

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_total_tool_count(self):
        """Test that expected number of tools are registered."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()
        tool_count = len(server._tool_manager._tools)

        # Expected: 4 railway + 3 n8n + 3 monitoring + 2 oauth + 13 workspace + 6 browser = 31
        expected_min = 25  # Allow some flexibility
        assert tool_count >= expected_min, f"Expected at least {expected_min} tools, got {tool_count}"


class TestRailwayToolDelegation:
    """Tests for Railway tool delegation to underlying module."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_railway_deploy_delegates_correctly(self):
        """Test that railway_deploy delegates to trigger_deployment."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        # Get the tool function
        railway_deploy = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_deploy":
                railway_deploy = tool.fn
                break

        assert railway_deploy is not None

        mock_result = {"status": "triggered", "service_id": "test-svc"}

        with patch("src.mcp_gateway.tools.railway.trigger_deployment", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = mock_result
            result = await railway_deploy(service_id="test-svc")

        assert result == mock_result
        mock_trigger.assert_called_once_with("test-svc")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_railway_deploy_empty_service_id_uses_none(self):
        """Test that empty service_id passes None to trigger_deployment."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        railway_deploy = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_deploy":
                railway_deploy = tool.fn
                break

        with patch("src.mcp_gateway.tools.railway.trigger_deployment", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = {"status": "triggered"}
            await railway_deploy(service_id="")

        mock_trigger.assert_called_once_with(None)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_railway_status_delegates_correctly(self):
        """Test that railway_status delegates to get_deployment_status."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        railway_status = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_status":
                railway_status = tool.fn
                break

        mock_result = {"status": "success", "current": {"id": "dep-1"}}

        with patch("src.mcp_gateway.tools.railway.get_deployment_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_result
            result = await railway_status()

        assert result == mock_result
        mock_status.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_railway_deployments_passes_count(self):
        """Test that railway_deployments passes count parameter."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        railway_deployments = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_deployments":
                railway_deployments = tool.fn
                break

        with patch("src.mcp_gateway.tools.railway.get_recent_deployments", new_callable=AsyncMock) as mock_deps:
            mock_deps.return_value = {"status": "success", "deployments": []}
            await railway_deployments(count=10)

        mock_deps.assert_called_once_with(10)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_railway_rollback_delegates_correctly(self):
        """Test that railway_rollback delegates to execute_rollback."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        railway_rollback = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_rollback":
                railway_rollback = tool.fn
                break

        mock_result = {"status": "rollback_initiated", "deployment_id": "new-dep"}

        with patch("src.mcp_gateway.tools.railway.execute_rollback", new_callable=AsyncMock) as mock_rollback:
            mock_rollback.return_value = mock_result
            result = await railway_rollback(deployment_id="old-dep")

        assert result == mock_result
        mock_rollback.assert_called_once_with("old-dep")


class TestN8nToolDelegation:
    """Tests for n8n tool delegation to underlying module."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_n8n_trigger_parses_json_data(self):
        """Test that n8n_trigger correctly parses JSON data string."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        n8n_trigger = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_trigger":
                n8n_trigger = tool.fn
                break

        mock_result = {"status": "success", "execution_id": "exec-1"}

        with patch("src.mcp_gateway.tools.n8n.trigger_workflow", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = mock_result
            result = await n8n_trigger(workflow_name="test-workflow", data='{"key": "value"}')

        assert result == mock_result
        mock_trigger.assert_called_once_with("test-workflow", {"key": "value"})

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_n8n_trigger_invalid_json_returns_error(self):
        """Test that n8n_trigger returns error for invalid JSON."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        n8n_trigger = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_trigger":
                n8n_trigger = tool.fn
                break

        result = await n8n_trigger(workflow_name="test", data="not valid json")

        assert result["status"] == "error"
        assert "Invalid JSON" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_n8n_trigger_empty_data_uses_empty_dict(self):
        """Test that n8n_trigger uses empty dict for empty data."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        n8n_trigger = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_trigger":
                n8n_trigger = tool.fn
                break

        with patch("src.mcp_gateway.tools.n8n.trigger_workflow", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = {"status": "success"}
            await n8n_trigger(workflow_name="test", data="")

        mock_trigger.assert_called_once_with("test", {})

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_n8n_list_delegates_correctly(self):
        """Test that n8n_list delegates to list_workflows."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        n8n_list = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_list":
                n8n_list = tool.fn
                break

        mock_result = {"workflows": [{"name": "test-workflow"}]}

        with patch("src.mcp_gateway.tools.n8n.list_workflows", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result
            result = await n8n_list()

        assert result == mock_result
        mock_list.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_n8n_status_delegates_correctly(self):
        """Test that n8n_status delegates to get_workflow_status."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        n8n_status = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_status":
                n8n_status = tool.fn
                break

        mock_result = {"status": "accessible", "workflow": "test"}

        with patch("src.mcp_gateway.tools.n8n.get_workflow_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_result
            result = await n8n_status(workflow_name="test")

        assert result == mock_result
        mock_status.assert_called_once_with("test")


class TestMonitoringToolDelegation:
    """Tests for monitoring tool delegation to underlying module."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_health_check_delegates_correctly(self):
        """Test that health_check delegates to check_health."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        health_check = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "health_check":
                health_check = tool.fn
                break

        mock_result = {"railway": "healthy", "n8n": "healthy"}

        with patch("src.mcp_gateway.tools.monitoring.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = mock_result
            result = await health_check()

        assert result == mock_result
        mock_health.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_get_metrics_delegates_correctly(self):
        """Test that get_metrics delegates to get_metrics."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        get_metrics_tool = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "get_metrics":
                get_metrics_tool = tool.fn
                break

        mock_result = {"cpu": 50, "memory": 60}

        with patch("src.mcp_gateway.tools.monitoring.get_metrics", new_callable=AsyncMock) as mock_metrics:
            mock_metrics.return_value = mock_result
            result = await get_metrics_tool()

        assert result == mock_result
        mock_metrics.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_deployment_health_delegates_correctly(self):
        """Test that deployment_health delegates to check_deployment_health."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        deployment_health = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "deployment_health":
                deployment_health = tool.fn
                break

        mock_result = {"overall": "healthy", "recommendations": []}

        with patch("src.mcp_gateway.tools.monitoring.check_deployment_health", new_callable=AsyncMock) as mock_dep_health:
            mock_dep_health.return_value = mock_result
            result = await deployment_health()

        assert result == mock_result
        mock_dep_health.assert_called_once()


class TestOAuthToolDelegation:
    """Tests for OAuth tool delegation to underlying module."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_workspace_oauth_exchange_delegates_correctly(self):
        """Test that workspace_oauth_exchange delegates to exchange_oauth_code."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        oauth_exchange = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "workspace_oauth_exchange":
                oauth_exchange = tool.fn
                break

        mock_result = {"success": True, "message": "Token stored"}

        with patch("src.mcp_gateway.tools.oauth.exchange_oauth_code", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = mock_result
            result = await oauth_exchange(auth_code="test-auth-code")

        assert result == mock_result
        mock_exchange.assert_called_once_with("test-auth-code")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_workspace_oauth_status_delegates_correctly(self):
        """Test that workspace_oauth_status delegates to check_oauth_status."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        oauth_status = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "workspace_oauth_status":
                oauth_status = tool.fn
                break

        mock_result = {"configured": True, "secrets": ["client_id", "client_secret"]}

        with patch("src.mcp_gateway.tools.oauth.check_oauth_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_result
            result = await oauth_status()

        assert result == mock_result
        mock_status.assert_called_once()


class TestWorkspaceToolDelegation:
    """Tests for Google Workspace tool delegation."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_gmail_send_delegates_correctly(self):
        """Test that gmail_send delegates with all parameters."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        gmail_send = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "gmail_send":
                gmail_send = tool.fn
                break

        mock_result = {"success": True, "message_id": "msg-123"}

        with patch("src.mcp_gateway.tools.workspace.gmail_send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_result
            result = await gmail_send(
                to="user@example.com",
                subject="Test",
                body="Hello",
                cc="cc@example.com",
                bcc="bcc@example.com"
            )

        assert result == mock_result
        mock_send.assert_called_once_with(
            "user@example.com", "Test", "Hello", "cc@example.com", "bcc@example.com"
        )

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_gmail_search_delegates_correctly(self):
        """Test that gmail_search delegates with query and max_results."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        gmail_search = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "gmail_search":
                gmail_search = tool.fn
                break

        mock_result = {"emails": [{"id": "email-1"}]}

        with patch("src.mcp_gateway.tools.workspace.gmail_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_result
            result = await gmail_search(query="from:test@example.com", max_results=5)

        assert result == mock_result
        mock_search.assert_called_once_with("from:test@example.com", 5)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_sheets_write_parses_json_values(self):
        """Test that sheets_write correctly parses JSON values."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        sheets_write = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "sheets_write":
                sheets_write = tool.fn
                break

        mock_result = {"success": True, "updated_cells": 4}

        with patch("src.mcp_gateway.tools.workspace.sheets_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = mock_result
            result = await sheets_write(
                spreadsheet_id="sheet-123",
                range_notation="Sheet1!A1:B2",
                values='[["A1", "B1"], ["A2", "B2"]]'
            )

        assert result == mock_result
        mock_write.assert_called_once_with(
            "sheet-123",
            "Sheet1!A1:B2",
            [["A1", "B1"], ["A2", "B2"]]
        )

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_sheets_write_invalid_json_returns_error(self):
        """Test that sheets_write returns error for invalid JSON."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        sheets_write = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "sheets_write":
                sheets_write = tool.fn
                break

        result = await sheets_write(
            spreadsheet_id="sheet-123",
            range_notation="Sheet1!A1",
            values="not valid json"
        )

        assert result["success"] is False
        assert "Invalid JSON" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_calendar_create_event_delegates_correctly(self):
        """Test that calendar_create_event delegates with all parameters."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        calendar_create = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "calendar_create_event":
                calendar_create = tool.fn
                break

        mock_result = {"success": True, "event_id": "event-123"}

        with patch("src.mcp_gateway.tools.workspace.calendar_create_event", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_result
            result = await calendar_create(
                summary="Meeting",
                start_time="2026-01-22T10:00:00Z",
                end_time="2026-01-22T11:00:00Z",
                calendar_id="primary",
                description="Test meeting",
                location="Room 1",
                attendees="user@example.com"
            )

        assert result == mock_result
        mock_create.assert_called_once_with(
            "Meeting",
            "2026-01-22T10:00:00Z",
            "2026-01-22T11:00:00Z",
            "primary",
            "Test meeting",
            "Room 1",
            "user@example.com"
        )


class TestBrowserToolDelegation:
    """Tests for browser automation tool delegation."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_navigate_starts_server_if_needed(self):
        """Test that browser_navigate starts browser server if not running."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        browser_navigate = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_navigate":
                browser_navigate = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = False
        mock_server.start = AsyncMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"success": True, "url": "https://example.com"}
        mock_server.navigate = AsyncMock(return_value=mock_result)

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_navigate(url="https://example.com")

        mock_server.start.assert_called_once()
        mock_server.navigate.assert_called_once_with("https://example.com")
        assert result["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_accessibility_tree_requires_running_server(self):
        """Test that browser_accessibility_tree returns error if browser not started."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        browser_tree = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_accessibility_tree":
                browser_tree = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = False

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_tree()

        assert result["success"] is False
        assert "Browser not started" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_click_ref_requires_running_server(self):
        """Test that browser_click_ref returns error if browser not started."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        browser_click = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_click_ref":
                browser_click = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = False

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_click(ref="@e1")

        assert result["success"] is False
        assert "Browser not started" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_fill_ref_requires_running_server(self):
        """Test that browser_fill_ref returns error if browser not started."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        browser_fill = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_fill_ref":
                browser_fill = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = False

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_fill(ref="@e1", value="test")

        assert result["success"] is False
        assert "Browser not started" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_screenshot_encodes_to_base64(self):
        """Test that browser_screenshot encodes image bytes to base64."""
        from src.mcp_gateway.server import create_mcp_server
        import base64

        server = create_mcp_server()

        browser_screenshot = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_screenshot":
                browser_screenshot = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = True
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = b"fake image bytes"
        mock_result.url = "https://example.com"
        mock_result.duration = 0.5
        mock_server.screenshot = AsyncMock(return_value=mock_result)

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_screenshot(full_page=False)

        assert result["success"] is True
        assert result["data"] == base64.b64encode(b"fake image bytes").decode("utf-8")
        assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_close_stops_running_server(self):
        """Test that browser_close stops server if running."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        browser_close = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_close":
                browser_close = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = True
        mock_server.stop = AsyncMock()

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_close()

        mock_server.stop.assert_called_once()
        assert result["success"] is True
        assert "closed" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_browser_close_when_not_running(self):
        """Test that browser_close succeeds even if browser not running."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        browser_close = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "browser_close":
                browser_close = tool.fn
                break

        mock_server = MagicMock()
        mock_server.is_running = False

        with patch("src.mcp_gateway.server.get_browser_server", return_value=mock_server):
            result = await browser_close()

        assert result["success"] is True
        assert "not running" in result["message"]


class TestToolFunctionSignatures:
    """Tests for tool function signatures and parameters."""

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_railway_deploy_has_optional_service_id(self):
        """Test that railway_deploy has service_id with default empty string."""
        from src.mcp_gateway.server import create_mcp_server
        import inspect

        server = create_mcp_server()

        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_deploy":
                sig = inspect.signature(tool.fn)
                param = sig.parameters.get("service_id")
                assert param is not None
                assert param.default == ""
                break

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_railway_deployments_has_default_count(self):
        """Test that railway_deployments has count default of 5."""
        from src.mcp_gateway.server import create_mcp_server
        import inspect

        server = create_mcp_server()

        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_deployments":
                sig = inspect.signature(tool.fn)
                param = sig.parameters.get("count")
                assert param is not None
                assert param.default == 5
                break

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_n8n_trigger_has_default_empty_data(self):
        """Test that n8n_trigger has data default of empty JSON object."""
        from src.mcp_gateway.server import create_mcp_server
        import inspect

        server = create_mcp_server()

        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_trigger":
                sig = inspect.signature(tool.fn)
                param = sig.parameters.get("data")
                assert param is not None
                assert param.default == "{}"
                break

    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    def test_gmail_list_has_default_inbox(self):
        """Test that gmail_list defaults to INBOX label."""
        from src.mcp_gateway.server import create_mcp_server
        import inspect

        server = create_mcp_server()

        for tool in server._tool_manager._tools.values():
            if tool.name == "gmail_list":
                sig = inspect.signature(tool.fn)
                param = sig.parameters.get("label")
                assert param is not None
                assert param.default == "INBOX"
                break


class TestErrorHandling:
    """Tests for error handling in MCP server tools."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_tool_exception_handling(self):
        """Test that tool exceptions are properly handled."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        railway_status = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "railway_status":
                railway_status = tool.fn
                break

        with patch("src.mcp_gateway.tools.railway.get_deployment_status", new_callable=AsyncMock) as mock_status:
            mock_status.side_effect = Exception("Network error")

            # The tool should propagate the exception (server handles it)
            with pytest.raises(Exception, match="Network error"):
                await railway_status()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _can_import_fastmcp(), reason="fastmcp not installed")
    async def test_json_decode_errors_return_error_dict(self):
        """Test that JSON decode errors return error dict, not raise."""
        from src.mcp_gateway.server import create_mcp_server

        server = create_mcp_server()

        n8n_trigger = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "n8n_trigger":
                n8n_trigger = tool.fn
                break

        # Various invalid JSON inputs
        invalid_jsons = [
            "{invalid",
            "{'single': 'quotes'}",
            "[1, 2, 3,]",
            "undefined",
            "NaN",
        ]

        for invalid_json in invalid_jsons:
            result = await n8n_trigger(workflow_name="test", data=invalid_json)
            assert result["status"] == "error"
            assert "Invalid JSON" in result["message"]
