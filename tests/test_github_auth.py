"""Tests for the GitHub App authentication module."""

from unittest.mock import MagicMock, patch


class TestGitHubAuthImports:
    """Test that github_auth module imports correctly."""

    def test_module_imports(self):
        """Test that github_auth module can be imported."""
        from src import github_auth

        assert hasattr(github_auth, "generate_jwt")
        assert hasattr(github_auth, "get_installation_token")
        assert hasattr(github_auth, "configure_gh_cli")

    def test_constants_exist(self):
        """Test that required constants are defined."""
        from src.github_auth import GITHUB_APP_ID, GITHUB_INSTALLATION_ID

        assert GITHUB_APP_ID == 2497877
        assert GITHUB_INSTALLATION_ID == 100231961


class TestGenerateJWT:
    """Tests for JWT generation."""

    def test_generate_jwt_returns_string(self):
        """Test that generate_jwt returns a string."""
        with patch("src.github_auth.jwt.encode") as mock_encode:
            mock_encode.return_value = "header.payload.signature"

            from src.github_auth import GITHUB_APP_ID, generate_jwt

            result = generate_jwt(GITHUB_APP_ID, "fake_key")

            assert isinstance(result, str)
            mock_encode.assert_called_once()

    def test_generate_jwt_uses_rs256(self):
        """Test that RS256 algorithm is used."""
        with patch("src.github_auth.jwt.encode") as mock_encode:
            mock_encode.return_value = "test.jwt.token"

            from src.github_auth import generate_jwt

            generate_jwt(12345, "fake_key")

            call_args = mock_encode.call_args
            assert call_args[1]["algorithm"] == "RS256"


class TestGetInstallationToken:
    """Tests for installation token retrieval."""

    def test_returns_none_without_private_key(self):
        """Test that None is returned when private key unavailable."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            mock_sm.return_value.get_secret.return_value = None

            from src.github_auth import get_installation_token

            result = get_installation_token()

            assert result is None

    def test_returns_token_on_success(self):
        """Test successful token retrieval."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            with patch("src.github_auth.generate_jwt") as mock_jwt:
                with patch("src.github_auth.requests.post") as mock_post:
                    mock_sm.return_value.get_secret.return_value = "fake_key"
                    mock_jwt.return_value = "fake.jwt"
                    mock_response = MagicMock()
                    mock_response.json.return_value = {"token": "ghs_test"}
                    mock_post.return_value = mock_response

                    from src.github_auth import get_installation_token

                    result = get_installation_token()

                    assert result == "ghs_test"


class TestConfigureGhCli:
    """Tests for gh CLI configuration."""

    def test_returns_false_without_token(self):
        """Test that False is returned when token unavailable."""
        with patch("src.github_auth.get_installation_token") as mock_token:
            mock_token.return_value = None

            from src.github_auth import configure_gh_cli

            result = configure_gh_cli()

            assert result is False

    def test_returns_false_without_gh(self):
        """Test that False is returned when gh not installed."""
        with patch("src.github_auth.get_installation_token") as mock_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                mock_token.return_value = "test_token"
                mock_which.return_value = None

                from src.github_auth import configure_gh_cli

                result = configure_gh_cli()

                assert result is False
