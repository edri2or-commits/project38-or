"""Tests for n8n Client."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.n8n_client import (
    N8nAuthenticationError,
    N8nClient,
    N8nNotFoundError,
    N8nValidationError,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def n8n_client():
    """Create an n8n client instance for testing."""
    return N8nClient(base_url="https://n8n.railway.app", api_key="test_api_key_123")


@pytest.fixture
def sample_workflow():
    """Sample workflow data for testing."""
    return {
        "name": "Test Workflow",
        "nodes": [
            {"name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300]},
            {
                "name": "Telegram",
                "type": "n8n-nodes-base.telegram",
                "position": [450, 300],
            },
        ],
        "connections": {"Webhook": {"main": [[{"node": "Telegram"}]]}},
        "active": True,
        "settings": {},
    }


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestN8nClientInit:
    """Tests for N8nClient initialization."""

    def test_init_with_required_params(self):
        """Test initialization with required parameters."""
        client = N8nClient(base_url="https://n8n.railway.app", api_key="test_key")

        assert client.base_url == "https://n8n.railway.app"
        assert client.api_key == "test_key"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base URL."""
        client = N8nClient(base_url="https://n8n.railway.app/", api_key="test_key")

        assert client.base_url == "https://n8n.railway.app"


# ============================================================================
# API REQUEST TESTS
# ============================================================================


class TestApiRequest:
    """Tests for _api_request method."""

    @pytest.mark.asyncio
    async def test_api_request_success(self, n8n_client):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await n8n_client._api_request("GET", "/workflows")

            assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_api_request_with_json_data(self, n8n_client):
        """Test API request with JSON data."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "wf-123"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.request = mock_request

            result = await n8n_client._api_request("POST", "/workflows", json_data={"name": "Test"})

            assert result == {"id": "wf-123"}
            call_args = mock_request.call_args
            assert call_args[1]["json"] == {"name": "Test"}

    @pytest.mark.asyncio
    async def test_api_request_204_no_content(self, n8n_client):
        """Test API request with 204 No Content response."""
        mock_response = AsyncMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await n8n_client._api_request("DELETE", "/workflows/123")

            assert result == {}

    @pytest.mark.asyncio
    async def test_api_request_authentication_error(self, n8n_client):
        """Test that 401 raises N8nAuthenticationError."""
        mock_response = AsyncMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(N8nAuthenticationError):
                await n8n_client._api_request("GET", "/workflows")

    @pytest.mark.asyncio
    async def test_api_request_not_found_error(self, n8n_client):
        """Test that 404 raises N8nNotFoundError."""
        mock_response = AsyncMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(N8nNotFoundError):
                await n8n_client._api_request("GET", "/workflows/invalid")

    @pytest.mark.asyncio
    async def test_api_request_validation_error(self, n8n_client):
        """Test that 400 raises N8nValidationError."""
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid workflow structure"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(N8nValidationError):
                await n8n_client._api_request("POST", "/workflows", json_data={})


# ============================================================================
# WORKFLOW MANAGEMENT TESTS
# ============================================================================


class TestWorkflowManagement:
    """Tests for workflow management operations."""

    @pytest.mark.asyncio
    async def test_create_workflow(self, n8n_client, sample_workflow):
        """Test creating a workflow."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {"id": "wf-123", **sample_workflow}

            result = await n8n_client.create_workflow(
                name=sample_workflow["name"],
                nodes=sample_workflow["nodes"],
                connections=sample_workflow["connections"],
                active=True,
            )

            assert result["id"] == "wf-123"
            assert result["name"] == "Test Workflow"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_workflow(self, n8n_client):
        """Test getting a workflow."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {"id": "wf-123", "name": "Test Workflow"}

            result = await n8n_client.get_workflow("wf-123")

            assert result["id"] == "wf-123"
            mock_request.assert_called_once_with(method="GET", endpoint="/workflows/wf-123")

    @pytest.mark.asyncio
    async def test_list_workflows(self, n8n_client):
        """Test listing workflows."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "data": [
                    {"id": "wf-1", "name": "Workflow 1", "active": True},
                    {"id": "wf-2", "name": "Workflow 2", "active": False},
                ]
            }

            result = await n8n_client.list_workflows()

            assert len(result) == 2
            assert result[0]["id"] == "wf-1"

    @pytest.mark.asyncio
    async def test_list_workflows_active_only(self, n8n_client):
        """Test listing only active workflows."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "data": [
                    {"id": "wf-1", "name": "Workflow 1", "active": True},
                    {"id": "wf-2", "name": "Workflow 2", "active": False},
                ]
            }

            result = await n8n_client.list_workflows(active_only=True)

            assert len(result) == 1
            assert result[0]["id"] == "wf-1"
            assert result[0]["active"] is True

    @pytest.mark.asyncio
    async def test_update_workflow(self, n8n_client):
        """Test updating a workflow."""
        with patch.object(n8n_client, "get_workflow") as mock_get:
            with patch.object(n8n_client, "_api_request") as mock_request:
                mock_get.return_value = {
                    "id": "wf-123",
                    "name": "Old Name",
                    "nodes": [],
                    "connections": {},
                    "active": True,
                }
                mock_request.return_value = {
                    "id": "wf-123",
                    "name": "New Name",
                    "active": False,
                }

                result = await n8n_client.update_workflow(
                    workflow_id="wf-123", name="New Name", active=False
                )

                assert result["name"] == "New Name"
                assert result["active"] is False

    @pytest.mark.asyncio
    async def test_delete_workflow(self, n8n_client):
        """Test deleting a workflow."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {}

            await n8n_client.delete_workflow("wf-123")

            mock_request.assert_called_once_with(method="DELETE", endpoint="/workflows/wf-123")

    @pytest.mark.asyncio
    async def test_activate_workflow(self, n8n_client):
        """Test activating a workflow."""
        with patch.object(n8n_client, "update_workflow") as mock_update:
            mock_update.return_value = {"id": "wf-123", "active": True}

            result = await n8n_client.activate_workflow("wf-123")

            assert result["active"] is True
            mock_update.assert_called_once_with("wf-123", active=True)

    @pytest.mark.asyncio
    async def test_deactivate_workflow(self, n8n_client):
        """Test deactivating a workflow."""
        with patch.object(n8n_client, "update_workflow") as mock_update:
            mock_update.return_value = {"id": "wf-123", "active": False}

            result = await n8n_client.deactivate_workflow("wf-123")

            assert result["active"] is False
            mock_update.assert_called_once_with("wf-123", active=False)


# ============================================================================
# WORKFLOW EXECUTION TESTS
# ============================================================================


class TestWorkflowExecution:
    """Tests for workflow execution operations."""

    @pytest.mark.asyncio
    async def test_execute_workflow(self, n8n_client):
        """Test executing a workflow."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {"data": {"executionId": "exec-123"}}

            execution_id = await n8n_client.execute_workflow(
                workflow_id="wf-123", data={"alert": {"severity": "critical"}}
            )

            assert execution_id == "exec-123"
            mock_request.assert_called_once_with(
                method="POST",
                endpoint="/workflows/wf-123/execute",
                json_data={"data": {"alert": {"severity": "critical"}}},
            )

    @pytest.mark.asyncio
    async def test_execute_workflow_no_data(self, n8n_client):
        """Test executing a workflow without input data."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {"data": {"executionId": "exec-456"}}

            execution_id = await n8n_client.execute_workflow(workflow_id="wf-123")

            assert execution_id == "exec-456"
            call_args = mock_request.call_args
            assert call_args[1]["json_data"] == {"data": {}}

    @pytest.mark.asyncio
    async def test_get_execution_status(self, n8n_client):
        """Test getting execution status."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "finished": True,
                "status": "success",
                "data": {"result": "OK"},
                "startedAt": "2026-01-13T10:00:00Z",
                "stoppedAt": "2026-01-13T10:00:05Z",
            }

            result = await n8n_client.get_execution_status("exec-123")

            assert result["finished"] is True
            assert result["status"] == "success"
            mock_request.assert_called_once_with(method="GET", endpoint="/executions/exec-123")

    @pytest.mark.asyncio
    async def test_get_recent_executions(self, n8n_client):
        """Test getting recent executions."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "data": [
                    {"id": "exec-1", "workflowName": "Workflow 1", "status": "success"},
                    {"id": "exec-2", "workflowName": "Workflow 2", "status": "error"},
                ]
            }

            result = await n8n_client.get_recent_executions(limit=10)

            assert len(result) == 2
            assert result[0]["id"] == "exec-1"
            mock_request.assert_called_once_with(
                method="GET", endpoint="/executions", params={"limit": 10}
            )

    @pytest.mark.asyncio
    async def test_get_recent_executions_limit_cap(self, n8n_client):
        """Test that execution limit is capped at 100."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {"data": []}

            await n8n_client.get_recent_executions(limit=200)

            call_args = mock_request.call_args
            assert call_args[1]["params"]["limit"] == 100


# ============================================================================
# WORKFLOW IMPORT/EXPORT TESTS
# ============================================================================


class TestWorkflowImportExport:
    """Tests for workflow import/export operations."""

    @pytest.mark.asyncio
    async def test_export_workflow(self, n8n_client):
        """Test exporting a workflow."""
        with patch.object(n8n_client, "get_workflow") as mock_get:
            mock_get.return_value = {
                "id": "wf-123",
                "name": "Test Workflow",
                "nodes": [],
                "connections": {},
            }

            result = await n8n_client.export_workflow("wf-123")

            assert result["id"] == "wf-123"
            assert result["name"] == "Test Workflow"
            mock_get.assert_called_once_with("wf-123")

    @pytest.mark.asyncio
    async def test_import_workflow(self, n8n_client, sample_workflow):
        """Test importing a workflow."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            workflow_with_id = {
                "id": "old-123",
                "createdAt": "2026-01-01T00:00:00Z",
                **sample_workflow,
            }
            mock_request.return_value = {"id": "new-456", **sample_workflow}

            result = await n8n_client.import_workflow(workflow_with_id, activate=True)

            assert result["id"] == "new-456"
            # Verify that ID and timestamps were removed
            call_args = mock_request.call_args
            workflow_data = call_args[1]["json_data"]
            assert "id" not in workflow_data
            assert "createdAt" not in workflow_data
            assert workflow_data["active"] is True

    @pytest.mark.asyncio
    async def test_import_workflow_inactive(self, n8n_client, sample_workflow):
        """Test importing a workflow without activation."""
        with patch.object(n8n_client, "_api_request") as mock_request:
            mock_request.return_value = {"id": "new-789", **sample_workflow}

            result = await n8n_client.import_workflow(sample_workflow, activate=False)

            assert result["id"] == "new-789"
            call_args = mock_request.call_args
            workflow_data = call_args[1]["json_data"]
            assert workflow_data["active"] is False
