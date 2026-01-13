"""Tests for GitHub App Client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.github_app_client import (
    GitHubAppAuthenticationError,
    GitHubAppClient,
    GitHubAppNotFoundError,
    GitHubAppRateLimitError,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_private_key():
    """Mock RSA private key for testing."""
    return """-----BEGIN RSA PRIVATE KEY-----
MIIBogIBAAJBANLJhPHhITqQbPklG3ibCVxwGMRfp/v4XqhfdQHdcVfHap6NQ5Wo
k/4xIA+ui35/MmNartNuC+BdZ1tMuVCPFZcCAwEAAQ==
-----END RSA PRIVATE KEY-----"""


@pytest.fixture
def github_client(mock_private_key):
    """Create a GitHub App client instance for testing."""
    return GitHubAppClient(
        app_id="123456",
        private_key=mock_private_key,
        installation_id="789012",
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestGitHubAppClientInit:
    """Tests for GitHubAppClient initialization."""

    def test_init_with_required_params(self, mock_private_key):
        """Test initialization with required parameters."""
        client = GitHubAppClient(
            app_id="123456",
            private_key=mock_private_key,
            installation_id="789012",
        )

        assert client.app_id == "123456"
        assert client.private_key == mock_private_key
        assert client.installation_id == "789012"
        assert client.base_url == "https://api.github.com"
        assert client._installation_token is None
        assert client._token_expires_at is None

    def test_init_with_custom_base_url(self, mock_private_key):
        """Test initialization with custom base URL."""
        client = GitHubAppClient(
            app_id="123456",
            private_key=mock_private_key,
            installation_id="789012",
            base_url="https://github.enterprise.com/api/v3",
        )

        assert client.base_url == "https://github.enterprise.com/api/v3"


# ============================================================================
# JWT GENERATION TESTS
# ============================================================================


class TestGenerateJWT:
    """Tests for JWT generation."""

    def test_generate_jwt_returns_string(self, github_client):
        """Test that JWT generation returns a string."""
        with patch("src.github_app_client.jwt.encode") as mock_encode:
            mock_encode.return_value = "header.payload.signature"

            jwt_token = github_client.generate_jwt()

            assert isinstance(jwt_token, str)
            assert jwt_token == "header.payload.signature"

    def test_generate_jwt_uses_rs256(self, github_client):
        """Test that RS256 algorithm is used."""
        with patch("src.github_app_client.jwt.encode") as mock_encode:
            mock_encode.return_value = "test.jwt.token"

            github_client.generate_jwt()

            call_args = mock_encode.call_args
            assert call_args[1]["algorithm"] == "RS256"

    def test_generate_jwt_payload_structure(self, github_client):
        """Test JWT payload structure."""
        with patch("src.github_app_client.jwt.encode") as mock_encode:
            with patch("src.github_app_client.time.time") as mock_time:
                mock_time.return_value = 1000000
                mock_encode.return_value = "test.jwt.token"

                github_client.generate_jwt()

                payload = mock_encode.call_args[0][0]
                assert payload["iat"] == 1000000 - 60  # Clock drift tolerance
                assert payload["exp"] == 1000000 + 600  # 10 minutes
                assert payload["iss"] == "123456"  # App ID

    def test_generate_jwt_raises_on_error(self, github_client):
        """Test that JWT generation raises exception on error."""
        with patch("src.github_app_client.jwt.encode") as mock_encode:
            mock_encode.side_effect = Exception("JWT encoding failed")

            with pytest.raises(GitHubAppAuthenticationError):
                github_client.generate_jwt()


# ============================================================================
# INSTALLATION TOKEN TESTS
# ============================================================================


class TestGetInstallationToken:
    """Tests for installation token retrieval."""

    @pytest.mark.asyncio
    async def test_get_installation_token_success(self, github_client):
        """Test successful installation token retrieval."""
        with patch.object(github_client, "generate_jwt") as mock_jwt:
            mock_jwt.return_value = "fake.jwt.token"

            mock_response = Mock()
            mock_response.json.return_value = {
                "token": "ghs_test_installation_token",
                "expires_at": "2026-01-13T12:00:00Z",
            }
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                token = await github_client.get_installation_token()

                assert token == "ghs_test_installation_token"
                assert github_client._installation_token == token
                assert github_client._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_get_installation_token_caching(self, github_client):
        """Test that installation token is cached."""
        # Set up cached token that's still valid
        github_client._installation_token = "cached_token"
        github_client._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        token = await github_client.get_installation_token()

        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_installation_token_refresh_before_expiry(self, github_client):
        """Test that token is refreshed 5 minutes before expiration."""
        # Set up token that expires in 3 minutes (< 5 minute threshold)
        github_client._installation_token = "old_token"
        github_client._token_expires_at = datetime.now(UTC) + timedelta(minutes=3)

        with patch.object(github_client, "generate_jwt") as mock_jwt:
            mock_jwt.return_value = "fake.jwt.token"

            mock_response = Mock()
            mock_response.json.return_value = {
                "token": "new_token",
                "expires_at": "2026-01-13T13:00:00Z",
            }
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                token = await github_client.get_installation_token()

                assert token == "new_token"

    @pytest.mark.asyncio
    async def test_get_installation_token_http_error(self, github_client):
        """Test that HTTP errors raise GitHubAppAuthenticationError."""
        with patch.object(github_client, "generate_jwt") as mock_jwt:
            mock_jwt.return_value = "fake.jwt.token"

            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                with pytest.raises(GitHubAppAuthenticationError):
                    await github_client.get_installation_token()


# ============================================================================
# API REQUEST TESTS
# ============================================================================


class TestApiRequest:
    """Tests for _api_request method."""

    @pytest.mark.asyncio
    async def test_api_request_success(self, github_client):
        """Test successful API request."""
        with patch.object(github_client, "get_installation_token") as mock_get_token:
            mock_get_token.return_value = "test_token"

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test_data"}
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                    return_value=mock_response
                )

                result = await github_client._api_request("GET", "/test/endpoint")

                assert result == {"data": "test_data"}

    @pytest.mark.asyncio
    async def test_api_request_with_json_data(self, github_client):
        """Test API request with JSON data."""
        with patch.object(github_client, "get_installation_token") as mock_get_token:
            mock_get_token.return_value = "test_token"

            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"created": True}
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient") as mock_client:
                mock_request = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value.request = mock_request

                result = await github_client._api_request(
                    "POST", "/test/endpoint", json_data={"key": "value"}
                )

                assert result == {"created": True}
                call_args = mock_request.call_args
                assert call_args[1]["json"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_api_request_with_params(self, github_client):
        """Test API request with query parameters."""
        with patch.object(github_client, "get_installation_token") as mock_get_token:
            mock_get_token.return_value = "test_token"

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient") as mock_client:
                mock_request = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value.request = mock_request

                result = await github_client._api_request(
                    "GET", "/test/endpoint", params={"page": 1, "per_page": 10}
                )

                assert result == {"results": []}
                call_args = mock_request.call_args
                assert call_args[1]["params"] == {"page": 1, "per_page": 10}

    @pytest.mark.asyncio
    async def test_api_request_204_no_content(self, github_client):
        """Test API request with 204 No Content response."""
        with patch.object(github_client, "get_installation_token") as mock_get_token:
            mock_get_token.return_value = "test_token"

            mock_response = AsyncMock()
            mock_response.status_code = 204
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                    return_value=mock_response
                )

                result = await github_client._api_request("DELETE", "/test/endpoint")

                assert result == {}

    @pytest.mark.asyncio
    async def test_api_request_rate_limit_error(self, github_client):
        """Test that 429 rate limit raises GitHubAppRateLimitError."""
        with patch.object(github_client, "get_installation_token") as mock_get_token:
            mock_get_token.return_value = "test_token"

            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"X-RateLimit-Reset": "1234567890"}

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                    return_value=mock_response
                )

                with pytest.raises(GitHubAppRateLimitError):
                    await github_client._api_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_api_request_not_found_error(self, github_client):
        """Test that 404 raises GitHubAppNotFoundError."""
        with patch.object(github_client, "get_installation_token") as mock_get_token:
            mock_get_token.return_value = "test_token"

            mock_response = AsyncMock()
            mock_response.status_code = 404

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                    return_value=mock_response
                )

                with pytest.raises(GitHubAppNotFoundError):
                    await github_client._api_request("GET", "/test/endpoint")


# ============================================================================
# WORKFLOW OPERATIONS TESTS
# ============================================================================


class TestWorkflowOperations:
    """Tests for workflow operations."""

    @pytest.mark.asyncio
    async def test_trigger_workflow(self, github_client):
        """Test triggering a workflow."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {}

            await github_client.trigger_workflow(
                owner="test-owner",
                repo="test-repo",
                workflow_id="deploy.yml",
                ref="main",
                inputs={"environment": "production"},
            )

            mock_request.assert_called_once_with(
                method="POST",
                endpoint="/repos/test-owner/test-repo/actions/workflows/deploy.yml/dispatches",
                json_data={
                    "ref": "main",
                    "inputs": {"environment": "production"},
                },
            )

    @pytest.mark.asyncio
    async def test_get_workflow_runs(self, github_client):
        """Test getting workflow runs."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "workflow_runs": [
                    {"id": 1, "name": "Test", "status": "completed"},
                    {"id": 2, "name": "Deploy", "status": "in_progress"},
                ]
            }

            runs = await github_client.get_workflow_runs(
                owner="test-owner", repo="test-repo", status="completed", limit=5
            )

            assert len(runs) == 2
            assert runs[0]["id"] == 1
            mock_request.assert_called_once_with(
                method="GET",
                endpoint="/repos/test-owner/test-repo/actions/runs",
                params={"per_page": 5, "status": "completed"},
            )


# ============================================================================
# ISSUE OPERATIONS TESTS
# ============================================================================


class TestIssueOperations:
    """Tests for issue operations."""

    @pytest.mark.asyncio
    async def test_create_issue(self, github_client):
        """Test creating an issue."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "number": 42,
                "html_url": "https://github.com/test-owner/test-repo/issues/42",
            }

            issue = await github_client.create_issue(
                owner="test-owner",
                repo="test-repo",
                title="Bug Report",
                body="Something is broken",
                labels=["bug"],
                assignees=["user1"],
            )

            assert issue["number"] == 42
            mock_request.assert_called_once_with(
                method="POST",
                endpoint="/repos/test-owner/test-repo/issues",
                json_data={
                    "title": "Bug Report",
                    "body": "Something is broken",
                    "labels": ["bug"],
                    "assignees": ["user1"],
                },
            )

    @pytest.mark.asyncio
    async def test_add_issue_comment(self, github_client):
        """Test adding a comment to an issue."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {"id": 123, "body": "Test comment"}

            comment = await github_client.add_issue_comment(
                owner="test-owner",
                repo="test-repo",
                issue_number=42,
                body="Test comment",
            )

            assert comment["id"] == 123
            mock_request.assert_called_once_with(
                method="POST",
                endpoint="/repos/test-owner/test-repo/issues/42/comments",
                json_data={"body": "Test comment"},
            )

    @pytest.mark.asyncio
    async def test_close_issue_without_comment(self, github_client):
        """Test closing an issue without a comment."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {"state": "closed"}

            result = await github_client.close_issue(
                owner="test-owner", repo="test-repo", issue_number=42
            )

            assert result["state"] == "closed"
            mock_request.assert_called_once_with(
                method="PATCH",
                endpoint="/repos/test-owner/test-repo/issues/42",
                json_data={"state": "closed"},
            )

    @pytest.mark.asyncio
    async def test_close_issue_with_comment(self, github_client):
        """Test closing an issue with a final comment."""
        with patch.object(github_client, "add_issue_comment") as mock_comment:
            with patch.object(github_client, "_api_request") as mock_request:
                mock_comment.return_value = {"id": 123}
                mock_request.return_value = {"state": "closed"}

                result = await github_client.close_issue(
                    owner="test-owner",
                    repo="test-repo",
                    issue_number=42,
                    comment="Fixed",
                )

                assert result["state"] == "closed"
                mock_comment.assert_called_once_with("test-owner", "test-repo", 42, "Fixed")


# ============================================================================
# PULL REQUEST OPERATIONS TESTS
# ============================================================================


class TestPullRequestOperations:
    """Tests for pull request operations."""

    @pytest.mark.asyncio
    async def test_create_pull_request(self, github_client):
        """Test creating a pull request."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "number": 123,
                "html_url": "https://github.com/test-owner/test-repo/pull/123",
            }

            pr = await github_client.create_pull_request(
                owner="test-owner",
                repo="test-repo",
                title="Feature PR",
                body="New feature",
                head="feature/new",
                base="main",
            )

            assert pr["number"] == 123
            mock_request.assert_called_once_with(
                method="POST",
                endpoint="/repos/test-owner/test-repo/pulls",
                json_data={
                    "title": "Feature PR",
                    "body": "New feature",
                    "head": "feature/new",
                    "base": "main",
                },
            )

    @pytest.mark.asyncio
    async def test_merge_pull_request(self, github_client):
        """Test merging a pull request."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {"merged": True, "sha": "abc123"}

            result = await github_client.merge_pull_request(
                owner="test-owner",
                repo="test-repo",
                pull_number=123,
                merge_method="squash",
            )

            assert result["merged"] is True
            mock_request.assert_called_once_with(
                method="PUT",
                endpoint="/repos/test-owner/test-repo/pulls/123/merge",
                json_data={"merge_method": "squash"},
            )

    @pytest.mark.asyncio
    async def test_get_pull_request(self, github_client):
        """Test getting pull request details."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {"number": 123, "state": "open"}

            pr = await github_client.get_pull_request(
                owner="test-owner", repo="test-repo", pull_number=123
            )

            assert pr["state"] == "open"
            mock_request.assert_called_once_with(
                method="GET", endpoint="/repos/test-owner/test-repo/pulls/123"
            )


# ============================================================================
# COMMIT OPERATIONS TESTS
# ============================================================================


class TestCommitOperations:
    """Tests for commit operations."""

    @pytest.mark.asyncio
    async def test_get_recent_commits(self, github_client):
        """Test getting recent commits."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = [
                {"sha": "abc123", "commit": {"message": "First commit"}},
                {"sha": "def456", "commit": {"message": "Second commit"}},
            ]

            commits = await github_client.get_recent_commits(
                owner="test-owner", repo="test-repo", ref="main", limit=2
            )

            assert len(commits) == 2
            assert commits[0]["sha"] == "abc123"
            mock_request.assert_called_once_with(
                method="GET",
                endpoint="/repos/test-owner/test-repo/commits",
                params={"sha": "main", "per_page": 2},
            )

    @pytest.mark.asyncio
    async def test_get_commit_details(self, github_client):
        """Test getting commit details."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "sha": "abc123",
                "files": [{"filename": "test.py"}],
            }

            commit = await github_client.get_commit_details(
                owner="test-owner", repo="test-repo", commit_sha="abc123"
            )

            assert commit["sha"] == "abc123"
            assert len(commit["files"]) == 1
            mock_request.assert_called_once_with(
                method="GET", endpoint="/repos/test-owner/test-repo/commits/abc123"
            )


# ============================================================================
# REPOSITORY OPERATIONS TESTS
# ============================================================================


class TestRepositoryOperations:
    """Tests for repository operations."""

    @pytest.mark.asyncio
    async def test_get_repository_info(self, github_client):
        """Test getting repository information."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {
                "name": "test-repo",
                "default_branch": "main",
                "description": "Test repository",
            }

            repo = await github_client.get_repository_info(owner="test-owner", repo="test-repo")

            assert repo["name"] == "test-repo"
            assert repo["default_branch"] == "main"
            mock_request.assert_called_once_with(
                method="GET", endpoint="/repos/test-owner/test-repo"
            )

    @pytest.mark.asyncio
    async def test_create_repository_dispatch(self, github_client):
        """Test creating a repository dispatch event."""
        with patch.object(github_client, "_api_request") as mock_request:
            mock_request.return_value = {}

            await github_client.create_repository_dispatch(
                owner="test-owner",
                repo="test-repo",
                event_type="deployment-complete",
                client_payload={"environment": "production"},
            )

            mock_request.assert_called_once_with(
                method="POST",
                endpoint="/repos/test-owner/test-repo/dispatches",
                json_data={
                    "event_type": "deployment-complete",
                    "client_payload": {"environment": "production"},
                },
            )
