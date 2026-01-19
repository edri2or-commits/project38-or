"""
Tests for the Automation Orchestrator.

Tests the multi-path execution strategy from ADR-008.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.automation.orchestrator import (
    AutomationOrchestrator,
    AutomationResult,
    ExecutionPath,
)


class TestAutomationResult:
    """Tests for AutomationResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = AutomationResult(
            success=True,
            path=ExecutionPath.DIRECT_PYTHON,
            data={"key": "value"},
        )
        assert result.success is True
        assert result.path == ExecutionPath.DIRECT_PYTHON
        assert result.data == {"key": "value"}
        assert result.errors == []

    def test_failed_result(self):
        """Test creating a failed result."""
        result = AutomationResult(
            success=False,
            errors=["Error 1", "Error 2"],
        )
        assert result.success is False
        assert result.path is None
        assert len(result.errors) == 2

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = AutomationResult(
            success=True,
            path=ExecutionPath.CLOUD_RUN,
            data={"test": "data"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["path"] == "cloud_run"
        assert d["data"] == {"test": "data"}


class TestAutomationOrchestrator:
    """Tests for AutomationOrchestrator class."""

    def test_initialization_defaults(self):
        """Test orchestrator initializes with defaults."""
        orchestrator = AutomationOrchestrator()
        assert orchestrator.github_repo == "edri2or-commits/project38-or"
        assert orchestrator.cloud_run_url is not None

    def test_initialization_custom(self):
        """Test orchestrator initializes with custom values."""
        orchestrator = AutomationOrchestrator(
            cloud_run_url="https://custom.run.app",
            github_repo="owner/repo",
        )
        assert orchestrator.cloud_run_url == "https://custom.run.app"
        assert orchestrator.github_repo == "owner/repo"

    def test_register_handler(self):
        """Test registering a direct Python handler."""
        orchestrator = AutomationOrchestrator()

        async def my_handler(param1: str) -> dict:
            return {"result": param1}

        orchestrator.register_handler("my-action", my_handler)
        assert "my-action" in orchestrator._direct_handlers

    @pytest.mark.asyncio
    async def test_direct_python_handler_success(self):
        """Test direct Python path succeeds with registered handler."""
        orchestrator = AutomationOrchestrator()

        async def test_handler(**kwargs) -> dict:
            return {"status": "ok", "received": kwargs}

        orchestrator.register_handler("test-action", test_handler)

        result = await orchestrator.execute(
            "test-action",
            {"param": "value"},
            paths=[ExecutionPath.DIRECT_PYTHON],
        )

        assert result.success is True
        assert result.path == ExecutionPath.DIRECT_PYTHON
        assert result.data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_direct_python_no_handler(self):
        """Test direct Python path fails without handler."""
        orchestrator = AutomationOrchestrator()

        result = await orchestrator.execute(
            "unknown-action",
            {},
            paths=[ExecutionPath.DIRECT_PYTHON],
        )

        assert result.success is False
        assert "No direct handler" in result.errors[0]

    @pytest.mark.asyncio
    async def test_cloud_run_success(self):
        """Test Cloud Run path succeeds with mock response."""
        orchestrator = AutomationOrchestrator(
            cloud_run_url="https://test.run.app",
            cloud_run_token="test-token",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tools": ["tool1", "tool2"]}

        with patch("requests.post", return_value=mock_response):
            result = await orchestrator.execute(
                "test-gcp-tools",
                {},
                paths=[ExecutionPath.CLOUD_RUN],
            )

        assert result.success is True
        assert result.path == ExecutionPath.CLOUD_RUN

    @pytest.mark.asyncio
    async def test_cloud_run_timeout(self):
        """Test Cloud Run path handles timeout."""
        orchestrator = AutomationOrchestrator(
            cloud_run_url="https://test.run.app",
        )
        orchestrator.path_configs[ExecutionPath.CLOUD_RUN].timeout_seconds = 0.1

        import requests

        with patch("requests.post", side_effect=requests.Timeout):
            result = await orchestrator.execute(
                "test-gcp-tools",
                {},
                paths=[ExecutionPath.CLOUD_RUN],
            )

        assert result.success is False
        assert "timed out" in str(result.errors).lower() or "timeout" in str(result.errors).lower()

    @pytest.mark.asyncio
    async def test_fallback_order(self):
        """Test that paths are tried in order and fallback works."""
        orchestrator = AutomationOrchestrator(
            cloud_run_url="https://test.run.app",
            n8n_url="https://n8n.test.app/webhook",
        )

        call_order = []

        # Mock all paths to fail except n8n
        async def mock_direct(action, params):
            call_order.append("direct")
            return AutomationResult(success=False, errors=["No handler"])

        async def mock_cloud_run(action, params):
            call_order.append("cloud_run")
            return AutomationResult(success=False, errors=["Connection failed"])

        async def mock_n8n(action, params):
            call_order.append("n8n")
            return AutomationResult(
                success=True,
                path=ExecutionPath.N8N_WEBHOOK,
                data={"triggered": True},
            )

        orchestrator._try_direct_python = mock_direct
        orchestrator._try_cloud_run = mock_cloud_run
        orchestrator._try_n8n_webhook = mock_n8n

        result = await orchestrator.execute(
            "test-action",
            {},
            paths=[
                ExecutionPath.DIRECT_PYTHON,
                ExecutionPath.CLOUD_RUN,
                ExecutionPath.N8N_WEBHOOK,
            ],
        )

        assert result.success is True
        assert result.path == ExecutionPath.N8N_WEBHOOK
        assert call_order == ["direct", "cloud_run", "n8n"]

    @pytest.mark.asyncio
    async def test_all_paths_fail(self):
        """Test that all errors are collected when all paths fail."""
        orchestrator = AutomationOrchestrator()

        async def mock_fail(action, params):
            return AutomationResult(success=False, errors=["Failed"])

        orchestrator._try_direct_python = mock_fail
        orchestrator._try_cloud_run = mock_fail
        orchestrator._try_n8n_webhook = mock_fail
        orchestrator._try_github_api = mock_fail
        orchestrator._try_manual = mock_fail

        result = await orchestrator.execute("test-action", {})

        assert result.success is False
        assert len(result.errors) >= 4  # At least 4 paths tried

    @pytest.mark.asyncio
    async def test_github_api_known_unreliable(self):
        """Test that GitHub API returns note about known limitations."""
        orchestrator = AutomationOrchestrator(
            github_token="test-token",
        )

        mock_response = MagicMock()
        mock_response.status_code = 204  # Success but no content

        with patch("requests.post", return_value=mock_response):
            result = await orchestrator.execute(
                "test-gcp-tools",
                {},
                paths=[ExecutionPath.GITHUB_API],
            )

        assert result.success is True
        assert result.path == ExecutionPath.GITHUB_API
        assert "No run ID" in str(result.data)  # Documents known limitation

    @pytest.mark.asyncio
    async def test_manual_creates_issue(self):
        """Test manual path creates GitHub issue."""
        orchestrator = AutomationOrchestrator(
            github_token="test-token",
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 999,
            "html_url": "https://github.com/test/repo/issues/999",
        }

        with patch("requests.post", return_value=mock_response):
            result = await orchestrator.execute(
                "test-action",
                {},
                paths=[ExecutionPath.MANUAL],
            )

        assert result.success is True
        assert result.path == ExecutionPath.MANUAL
        assert result.data["issue_number"] == 999

    @pytest.mark.asyncio
    async def test_duration_tracking(self):
        """Test that duration is tracked correctly."""
        orchestrator = AutomationOrchestrator()

        async def slow_handler(**kwargs):
            import asyncio

            await asyncio.sleep(0.1)
            return {"done": True}

        orchestrator.register_handler("slow-action", slow_handler)

        result = await orchestrator.execute(
            "slow-action",
            {},
            paths=[ExecutionPath.DIRECT_PYTHON],
        )

        assert result.success is True
        assert result.duration_ms >= 100  # At least 100ms


class TestExecutionPath:
    """Tests for ExecutionPath enum."""

    def test_all_paths_defined(self):
        """Test all expected paths are defined."""
        expected = {"direct_python", "cloud_run", "n8n_webhook", "github_api", "manual"}
        actual = {p.value for p in ExecutionPath}
        assert actual == expected
