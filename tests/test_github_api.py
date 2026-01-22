"""Tests for src/github_api.py - GitHub API Client."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import os


class TestGitHubAPIInit:
    """Tests for GitHubAPI initialization."""

    def test_github_api_import(self):
        """GitHubAPI should be importable."""
        from src.github_api import GitHubAPI

        assert GitHubAPI is not None

    def test_github_api_init_with_token(self):
        """GitHubAPI should initialize with provided token."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test_token_123")
        assert api.token == "test_token_123"

    def test_github_api_init_with_env_gh_token(self):
        """GitHubAPI should use GH_TOKEN env var."""
        from src.github_api import GitHubAPI

        with patch.dict(os.environ, {"GH_TOKEN": "env_token_456"}, clear=True):
            api = GitHubAPI(token=None)
            assert api.token == "env_token_456"

    def test_github_api_init_with_env_github_token(self):
        """GitHubAPI should use GITHUB_TOKEN env var as fallback."""
        from src.github_api import GitHubAPI

        with patch.dict(os.environ, {"GITHUB_TOKEN": "github_token_789"}, clear=True):
            api = GitHubAPI(token=None)
            assert api.token == "github_token_789"

    def test_github_api_init_no_token_raises(self):
        """GitHubAPI should raise ValueError without token."""
        from src.github_api import GitHubAPI

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="No GitHub token found"):
                GitHubAPI(token=None)

    def test_github_api_default_repo(self):
        """GitHubAPI should have default repo."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")
        assert api.repo == "edri2or-commits/project38-or"

    def test_github_api_custom_repo(self):
        """GitHubAPI should accept custom repo."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test", repo="owner/custom-repo")
        assert api.repo == "owner/custom-repo"
        assert "owner/custom-repo" in api.base_url

    def test_github_api_headers(self):
        """GitHubAPI should set correct headers."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test_token")
        assert api.headers["Authorization"] == "Bearer test_token"
        assert "application/vnd.github+json" in api.headers["Accept"]


class TestGitHubAPIRequest:
    """Tests for GitHubAPI._request method."""

    def test_request_builds_url(self):
        """_request should build correct URL."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        with patch("requests.request") as mock_request:
            mock_response = MagicMock()
            mock_request.return_value = mock_response

            api._request("GET", "actions/runs")

            call_args = mock_request.call_args
            assert "https://api.github.com/repos/" in call_args.kwargs["url"]
            assert "actions/runs" in call_args.kwargs["url"]

    def test_request_passes_params(self):
        """_request should pass query parameters."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        with patch("requests.request") as mock_request:
            mock_response = MagicMock()
            mock_request.return_value = mock_response

            api._request("GET", "endpoint", params={"per_page": 10})

            call_args = mock_request.call_args
            assert call_args.kwargs["params"] == {"per_page": 10}

    def test_request_passes_json_data(self):
        """_request should pass JSON data."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        with patch("requests.request") as mock_request:
            mock_response = MagicMock()
            mock_request.return_value = mock_response

            api._request("POST", "endpoint", json_data={"key": "value"})

            call_args = mock_request.call_args
            assert call_args.kwargs["json"] == {"key": "value"}


class TestGetWorkflowRuns:
    """Tests for GitHubAPI.get_workflow_runs method."""

    def test_get_workflow_runs_basic(self):
        """get_workflow_runs should return list of runs."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workflow_runs": [
                {"id": 1, "name": "Test", "status": "completed"},
                {"id": 2, "name": "Build", "status": "in_progress"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response):
            runs = api.get_workflow_runs(limit=10)

        assert len(runs) == 2
        assert runs[0]["id"] == 1

    def test_get_workflow_runs_with_workflow_filter(self):
        """get_workflow_runs should filter by workflow file."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {"workflow_runs": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response) as mock_req:
            api.get_workflow_runs(workflow_file="test.yml")

            call_args = mock_req.call_args
            assert "test.yml" in call_args.args[1]

    def test_get_workflow_runs_with_status_filter(self):
        """get_workflow_runs should filter by status."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {"workflow_runs": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response) as mock_req:
            api.get_workflow_runs(status="completed")

            call_args = mock_req.call_args
            assert call_args.kwargs.get("params", {}).get("status") == "completed"


class TestGetRunStatus:
    """Tests for GitHubAPI.get_run_status method."""

    def test_get_run_status_returns_dict(self):
        """get_run_status should return status dict."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 12345,
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/...",
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-01-15T10:05:00Z",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response):
            status = api.get_run_status(12345)

        assert status["id"] == 12345
        assert status["status"] == "completed"
        assert status["conclusion"] == "success"

    def test_get_run_status_handles_running(self):
        """get_run_status should handle running workflows."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 12345,
            "name": "Test Workflow",
            "status": "in_progress",
            "conclusion": None,
            "html_url": "https://github.com/...",
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-01-15T10:02:00Z",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response):
            status = api.get_run_status(12345)

        assert status["conclusion"] is None


class TestGetRunJobs:
    """Tests for GitHubAPI.get_run_jobs method."""

    def test_get_run_jobs_returns_jobs(self):
        """get_run_jobs should return list of jobs with steps."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {
                    "id": 1,
                    "name": "build",
                    "status": "completed",
                    "conclusion": "success",
                    "steps": [
                        {"name": "Checkout", "status": "completed", "conclusion": "success"},
                        {"name": "Build", "status": "completed", "conclusion": "success"},
                    ],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response):
            jobs = api.get_run_jobs(12345)

        assert len(jobs) == 1
        assert jobs[0]["name"] == "build"
        assert len(jobs[0]["steps"]) == 2

    def test_get_run_jobs_empty(self):
        """get_run_jobs should handle no jobs."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {"jobs": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response):
            jobs = api.get_run_jobs(12345)

        assert jobs == []


class TestTriggerWorkflow:
    """Tests for GitHubAPI.trigger_workflow method."""

    def test_trigger_workflow_success(self):
        """trigger_workflow should return True on 204 response."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(api, "_request", return_value=mock_response):
            result = api.trigger_workflow("test.yml")

        assert result is True

    def test_trigger_workflow_with_inputs(self):
        """trigger_workflow should pass inputs."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(api, "_request", return_value=mock_response) as mock_req:
            api.trigger_workflow("test.yml", inputs={"key": "value"})

            call_args = mock_req.call_args
            assert call_args.kwargs["json_data"]["inputs"] == {"key": "value"}

    def test_trigger_workflow_failure(self):
        """trigger_workflow should return False on non-204."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(api, "_request", return_value=mock_response):
            result = api.trigger_workflow("nonexistent.yml")

        assert result is False


class TestWaitForWorkflow:
    """Tests for GitHubAPI.wait_for_workflow method."""

    def test_wait_for_workflow_completes(self):
        """wait_for_workflow should return when workflow completes."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        # Mock get_workflow_runs to return completed workflow
        runs = [{"id": 123, "status": "completed"}]

        with patch.object(api, "get_workflow_runs", return_value=runs):
            with patch.object(api, "get_run_status", return_value={"id": 123, "status": "completed"}):
                with patch("time.sleep"):  # Skip actual sleeping
                    result = api.wait_for_workflow("test.yml", timeout=10, poll_interval=1)

        assert result is not None
        assert result["id"] == 123

    def test_wait_for_workflow_timeout(self):
        """wait_for_workflow should return None on timeout."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        # Mock get_workflow_runs to return running workflow
        runs = [{"id": 123, "status": "in_progress"}]

        call_count = [0]

        def mock_sleep(seconds):
            call_count[0] += 1
            if call_count[0] > 2:
                raise StopIteration()

        with patch.object(api, "get_workflow_runs", return_value=runs):
            with patch("time.sleep", side_effect=mock_sleep):
                with patch("time.time") as mock_time:
                    # Simulate timeout
                    mock_time.side_effect = [0, 5, 15, 25]  # Start, then past timeout
                    result = api.wait_for_workflow("test.yml", timeout=10, poll_interval=5)

        assert result is None


class TestCreateIssue:
    """Tests for GitHubAPI.create_issue method."""

    def test_create_issue_basic(self):
        """create_issue should create issue with title and body."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 1,
            "number": 42,
            "title": "Test Issue",
            "html_url": "https://github.com/.../issues/42",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response) as mock_req:
            result = api.create_issue("Test Issue", "Issue body")

            call_args = mock_req.call_args
            assert call_args.kwargs["json_data"]["title"] == "Test Issue"
            assert call_args.kwargs["json_data"]["body"] == "Issue body"

        assert result["number"] == 42

    def test_create_issue_with_labels(self):
        """create_issue should add labels."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "number": 42}
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response) as mock_req:
            api.create_issue("Test", "Body", labels=["bug", "urgent"])

            call_args = mock_req.call_args
            assert call_args.kwargs["json_data"]["labels"] == ["bug", "urgent"]


class TestAddIssueComment:
    """Tests for GitHubAPI.add_issue_comment method."""

    def test_add_issue_comment(self):
        """add_issue_comment should add comment to issue."""
        from src.github_api import GitHubAPI

        api = GitHubAPI(token="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "body": "Test comment",
            "html_url": "https://github.com/.../issues/42#issuecomment-123",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(api, "_request", return_value=mock_response) as mock_req:
            result = api.add_issue_comment(42, "Test comment")

            call_args = mock_req.call_args
            assert "42" in call_args.args[1]
            assert call_args.kwargs["json_data"]["body"] == "Test comment"

        assert result["id"] == 123


class TestGetAPI:
    """Tests for get_api convenience function."""

    def test_get_api_returns_instance(self):
        """get_api should return GitHubAPI instance."""
        from src.github_api import get_api, GitHubAPI

        with patch.dict(os.environ, {"GH_TOKEN": "test_token"}):
            api = get_api()
            assert isinstance(api, GitHubAPI)
