"""Tests for the GitHub App authentication module.

Note: These tests use mocking to avoid actual API calls.
Tokens are NEVER printed or exposed in test output.
"""

from unittest.mock import MagicMock, patch

import pytest

# Try to import, skip all tests if dependencies not available
try:
    from src.github_auth import (
        GITHUB_APP_ID,
        GITHUB_INSTALLATION_ID,
        configure_gh_cli,
        generate_jwt,
        get_installation_token,
    )
    SKIP_TESTS = False
except ImportError:
    SKIP_TESTS = True
    # Define dummy values to prevent NameError
    GITHUB_APP_ID = 0
    GITHUB_INSTALLATION_ID = 0
    configure_gh_cli = None
    generate_jwt = None
    get_installation_token = None


pytestmark = pytest.mark.skipif(SKIP_TESTS, reason="Dependencies not available")


class TestGenerateJWT:
    """Tests for JWT generation."""

    def test_generate_jwt_returns_string(self):
        """Test that generate_jwt returns a non-empty string."""
        with patch("src.github_auth.jwt.encode") as mock_encode:
            mock_encode.return_value = "header.payload.signature"

            result = generate_jwt(GITHUB_APP_ID, "fake_private_key")

            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0
            mock_encode.assert_called_once()

    def test_generate_jwt_uses_correct_algorithm(self):
        """Test that JWT uses RS256 algorithm."""
        with patch("src.github_auth.jwt.encode") as mock_encode:
            mock_encode.return_value = "test.jwt.token"

            generate_jwt(12345, "fake_key")

            # Verify RS256 algorithm is used
            call_args = mock_encode.call_args
            assert call_args[1]["algorithm"] == "RS256"

    def test_generate_jwt_payload_contains_iss(self):
        """Test that JWT payload contains issuer."""
        with patch("src.github_auth.jwt.encode") as mock_encode:
            mock_encode.return_value = "test.jwt.token"

            generate_jwt(12345, "fake_key")

            # Verify payload contains iss (issuer)
            call_args = mock_encode.call_args
            payload = call_args[0][0]
            assert payload["iss"] == 12345


class TestGetInstallationToken:
    """Tests for installation token retrieval."""

    def test_get_installation_token_success(self):
        """Test successful token retrieval."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            with patch("src.github_auth.generate_jwt") as mock_jwt:
                with patch("src.github_auth.requests.post") as mock_post:
                    # Setup mocks
                    mock_sm.return_value.get_secret.return_value = "fake_private_key"
                    mock_jwt.return_value = "fake.jwt.token"

                    mock_response = MagicMock()
                    mock_response.json.return_value = {"token": "ghs_test_token"}
                    mock_response.raise_for_status = MagicMock()
                    mock_post.return_value = mock_response

                    result = get_installation_token()

                    # Token should be returned (but never printed!)
                    assert result is not None
                    assert len(result) > 0

    def test_get_installation_token_no_private_key(self):
        """Test behavior when private key is not available."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            mock_sm.return_value.get_secret.return_value = None

            result = get_installation_token()

            assert result is None

    def test_get_installation_token_api_error(self):
        """Test behavior when GitHub API returns an error."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            with patch("src.github_auth.generate_jwt") as mock_jwt:
                with patch("src.github_auth.requests.post") as mock_post:
                    import requests

                    mock_sm.return_value.get_secret.return_value = "fake_key"
                    mock_jwt.return_value = "fake.jwt.token"
                    mock_post.side_effect = requests.RequestException("API error")

                    result = get_installation_token()

                    assert result is None

    def test_get_installation_token_uses_correct_url(self):
        """Test that correct GitHub API URL is used."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            with patch("src.github_auth.generate_jwt") as mock_jwt:
                with patch("src.github_auth.requests.post") as mock_post:
                    mock_sm.return_value.get_secret.return_value = "fake_key"
                    mock_jwt.return_value = "fake.jwt.token"
                    mock_response = MagicMock()
                    mock_response.json.return_value = {"token": "test"}
                    mock_post.return_value = mock_response

                    get_installation_token()

                    # Verify correct URL was called
                    call_url = mock_post.call_args[0][0]
                    assert "api.github.com" in call_url
                    assert "installations" in call_url
                    assert str(GITHUB_INSTALLATION_ID) in call_url


class TestConfigureGhCli:
    """Tests for gh CLI configuration."""

    def test_configure_gh_cli_no_token(self):
        """Test behavior when token cannot be obtained."""
        with patch("src.github_auth.get_installation_token") as mock_get_token:
            mock_get_token.return_value = None

            result = configure_gh_cli()

            assert result is False

    def test_configure_gh_cli_no_gh_executable(self):
        """Test behavior when gh is not installed."""
        with patch("src.github_auth.get_installation_token") as mock_get_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                mock_get_token.return_value = "test_token"
                mock_which.return_value = None

                result = configure_gh_cli()

                assert result is False

    def test_configure_gh_cli_success(self):
        """Test successful gh CLI configuration."""
        with patch("src.github_auth.get_installation_token") as mock_get_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                with patch("src.github_auth.subprocess.run") as mock_run:
                    mock_get_token.return_value = "test_token"
                    mock_which.return_value = "/usr/bin/gh"
                    mock_run.return_value = MagicMock(returncode=0)

                    result = configure_gh_cli()

                    assert result is True

    def test_configure_gh_cli_sets_env_var(self):
        """Test that GH_TOKEN environment variable is set."""
        import os

        with patch("src.github_auth.get_installation_token") as mock_get_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                with patch("src.github_auth.subprocess.run") as mock_run:
                    mock_get_token.return_value = "test_token_value"
                    mock_which.return_value = "/usr/bin/gh"
                    mock_run.return_value = MagicMock(returncode=0)

                    configure_gh_cli()

                    assert os.environ.get("GH_TOKEN") == "test_token_value"
                    # Cleanup
                    del os.environ["GH_TOKEN"]

    def test_configure_gh_cli_subprocess_error(self):
        """Test behavior when subprocess raises an error."""
        import subprocess

        with patch("src.github_auth.get_installation_token") as mock_get_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                with patch("src.github_auth.subprocess.run") as mock_run:
                    mock_get_token.return_value = "test_token"
                    mock_which.return_value = "/usr/bin/gh"
                    mock_run.side_effect = subprocess.SubprocessError("error")

                    result = configure_gh_cli()

                    assert result is False


class TestConstants:
    """Tests for module constants."""

    def test_app_id_is_set(self):
        """Test that App ID is configured."""
        assert GITHUB_APP_ID == 2497877

    def test_installation_id_is_set(self):
        """Test that Installation ID is configured."""
        assert GITHUB_INSTALLATION_ID == 100231961
