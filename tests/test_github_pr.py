"""Tests for github_pr module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src import github_pr


class TestGetGhToken:
    """Tests for _get_gh_token function."""

    def test_get_token_from_env_gh_token(self):
        """Should get token from GH_TOKEN environment variable."""
        with patch.dict("os.environ", {"GH_TOKEN": "test_token_123"}):
            token = github_pr._get_gh_token()
            assert token == "test_token_123"

    def test_get_token_from_env_github_token(self):
        """Should get token from GITHUB_TOKEN if GH_TOKEN not set."""
        with patch.dict(
            "os.environ", {"GITHUB_TOKEN": "test_token_456"}, clear=True
        ):
            token = github_pr._get_gh_token()
            assert token == "test_token_456"

    def test_get_token_from_gh_cli(self):
        """Should get token from gh CLI if env vars not set."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout="gh_cli_token_789\n"
            )

            token = github_pr._get_gh_token()
            assert token == "gh_cli_token_789"

    def test_get_token_none_when_unavailable(self):
        """Should return None when no token available."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            token = github_pr._get_gh_token()
            assert token is None


class TestEnsureGhCli:
    """Tests for ensure_gh_cli function."""

    def test_returns_true_when_gh_exists(self):
        """Should return True if gh CLI already installed."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            result = github_pr.ensure_gh_cli()
            assert result is True

    def test_attempts_install_when_missing(self):
        """Should attempt to install gh when missing."""
        with (
            patch("shutil.which", side_effect=[None, "/usr/bin/gh"]),
            patch("subprocess.run") as mock_run,
            patch("builtins.print"),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            result = github_pr.ensure_gh_cli()
            assert result is True
            assert mock_run.call_count == 2  # apt update + apt install

    def test_returns_false_on_install_failure(self):
        """Should return False if installation fails."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run") as mock_run,
            patch("builtins.print"),
        ):
            mock_run.return_value = MagicMock(returncode=1)

            result = github_pr.ensure_gh_cli()
            assert result is False

    def test_returns_false_on_permission_error(self):
        """Should return False if PermissionError occurs during installation."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", side_effect=PermissionError),
            patch("builtins.print"),
        ):
            result = github_pr.ensure_gh_cli()
            assert result is False

    def test_returns_false_on_subprocess_error(self):
        """Should return False if SubprocessError occurs during installation."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)),
            patch("builtins.print"),
        ):
            result = github_pr.ensure_gh_cli()
            assert result is False


class TestCreatePrWithGh:
    """Tests for create_pr_with_gh function."""

    def test_creates_pr_successfully(self):
        """Should create PR using gh CLI successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/pull/123\n",
            )

            result = github_pr.create_pr_with_gh(
                title="Test PR",
                body="Test body",
                repo="owner/repo",
                head="feature/test",
            )

            assert result is not None
            assert result["url"] == "https://github.com/owner/repo/pull/123"
            assert result["number"] == 123
            assert result["state"] == "open"

    def test_returns_none_on_failure(self):
        """Should return None if gh CLI fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            result = github_pr.create_pr_with_gh(
                title="Test PR",
                body="Test body",
                repo="owner/repo",
            )

            assert result is None

    def test_returns_none_on_subprocess_error(self):
        """Should return None if subprocess raises error."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 30)):
            result = github_pr.create_pr_with_gh(
                title="Test PR",
                body="Test body",
                repo="owner/repo",
                head="feature/test",
            )

            assert result is None


class TestCreatePrWithRequests:
    """Tests for create_pr_with_requests function."""

    def test_creates_pr_successfully(self):
        """Should create PR using requests library successfully."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "html_url": "https://github.com/owner/repo/pull/456",
                "number": 456,
                "state": "open",
            }
            mock_post.return_value = mock_response

            result = github_pr.create_pr_with_requests(
                title="Test PR",
                body="Test body",
                repo="owner/repo",
                head="feature/test",
                token="test_token",
            )

            assert result is not None
            assert result["number"] == 456
            assert result["state"] == "open"

    def test_returns_none_without_token(self):
        """Should return None if no token available."""
        with patch("src.github_pr._get_gh_token", return_value=None):
            result = github_pr.create_pr_with_requests(
                title="Test PR",
                body="Test body",
                repo="owner/repo",
                head="feature/test",
            )

            assert result is None

    def test_returns_none_on_request_failure(self):
        """Should return None if requests fails."""
        with patch("requests.post", side_effect=Exception("Network error")):
            result = github_pr.create_pr_with_requests(
                title="Test PR",
                body="Test body",
                repo="owner/repo",
                head="feature/test",
                token="test_token",
            )

            assert result is None


class TestCreatePr:
    """Tests for create_pr function (main interface)."""

    def test_prefers_gh_cli(self):
        """Should prefer gh CLI when available."""
        with (
            patch("shutil.which", return_value="/usr/bin/gh"),
            patch(
                "src.github_pr.create_pr_with_gh",
                return_value={"number": 123, "url": "test_url"},
            ) as mock_gh,
        ):
            result = github_pr.create_pr(
                title="Test",
                body="Body",
                repo="owner/repo",
                head="test-branch",
            )

            assert result is not None
            mock_gh.assert_called_once()

    def test_falls_back_to_requests(self):
        """Should fall back to requests if gh CLI unavailable."""
        with (
            patch("shutil.which", return_value=None),
            patch(
                "src.github_pr.create_pr_with_requests",
                return_value={"number": 456, "url": "test_url"},
            ) as mock_requests,
        ):
            result = github_pr.create_pr(
                title="Test",
                body="Body",
                repo="owner/repo",
                head="test-branch",
            )

            assert result is not None
            mock_requests.assert_called_once()

    def test_gets_current_branch_if_head_not_provided(self):
        """Should get current branch name if head not provided."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run") as mock_run,
            patch("src.github_pr.create_pr_with_requests") as mock_requests,
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout="current-branch\n"
            )
            mock_requests.return_value = {"number": 789}

            result = github_pr.create_pr(
                title="Test", body="Body", repo="owner/repo"
            )

            # Should have called git to get current branch
            assert mock_run.called
            assert "rev-parse" in str(mock_run.call_args)

    def test_returns_none_when_git_fails_to_get_branch(self):
        """Should return None when git rev-parse fails to get branch name."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run") as mock_run,
        ):
            # git rev-parse returns non-zero (fails to get branch)
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            result = github_pr.create_pr(
                title="Test", body="Body", repo="owner/repo"
            )

            assert result is None

    def test_returns_none_when_all_methods_fail(self):
        """Should return None when both gh and requests fail."""
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", side_effect=Exception),
        ):
            result = github_pr.create_pr(
                title="Test", body="Body", repo="owner/repo"
            )

            assert result is None
