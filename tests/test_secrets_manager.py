"""
Tests for the SecretManager module.

Note: These tests use mocking to avoid actual GCP API calls.
Secrets are NEVER printed or exposed in test output.
"""

import os
from unittest.mock import MagicMock, patch

from src.secrets_manager import SecretManager, get_secret


class TestSecretManager:
    """Tests for SecretManager class."""

    def test_init_default_project(self):
        """Test default project ID is set correctly."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient"):
            manager = SecretManager()
            assert manager.project_id == "project38-483612"

    def test_init_custom_project(self):
        """Test custom project ID is accepted."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient"):
            manager = SecretManager(project_id="custom-project")
            assert manager.project_id == "custom-project"

    def test_get_secret_success(self):
        """Test successful secret retrieval."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            # Setup mock
            mock_response = MagicMock()
            mock_response.payload.data = b"test-secret-value"
            mock_client.return_value.access_secret_version.return_value = mock_response

            manager = SecretManager()
            result = manager.get_secret("test-secret")

            # Verify secret was retrieved (but never print it!)
            assert result is not None
            assert len(result) > 0

    def test_get_secret_caching(self):
        """Test that secrets are cached after first retrieval."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            mock_response = MagicMock()
            mock_response.payload.data = b"cached-value"
            mock_client.return_value.access_secret_version.return_value = mock_response

            manager = SecretManager()

            # First call
            manager.get_secret("cached-secret")
            # Second call should use cache
            manager.get_secret("cached-secret")

            # API should only be called once due to caching
            assert mock_client.return_value.access_secret_version.call_count == 1

    def test_get_secret_not_found(self):
        """Test handling of non-existent secret."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            from google.api_core import exceptions

            mock_client.return_value.access_secret_version.side_effect = exceptions.NotFound(
                "Secret not found"
            )

            manager = SecretManager()
            result = manager.get_secret("nonexistent")

            assert result is None

    def test_get_secret_permission_denied(self):
        """Test handling of permission denied."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            from google.api_core import exceptions

            mock_client.return_value.access_secret_version.side_effect = (
                exceptions.PermissionDenied("Access denied")
            )

            manager = SecretManager()
            result = manager.get_secret("forbidden")

            assert result is None

    def test_list_secrets(self):
        """Test listing available secrets."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            # Setup mock secrets
            mock_secret1 = MagicMock()
            mock_secret1.name = "projects/test/secrets/secret-1"
            mock_secret2 = MagicMock()
            mock_secret2.name = "projects/test/secrets/secret-2"

            mock_client.return_value.list_secrets.return_value = [mock_secret1, mock_secret2]

            manager = SecretManager()
            secrets = manager.list_secrets()

            assert len(secrets) == 2
            assert "secret-1" in secrets
            assert "secret-2" in secrets

    def test_verify_access_success(self):
        """Test verify_access returns True for accessible secrets."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            mock_response = MagicMock()
            mock_response.payload.data = b"value"
            mock_client.return_value.access_secret_version.return_value = mock_response

            manager = SecretManager()
            result = manager.verify_access("accessible-secret")

            assert result is True

    def test_verify_access_failure(self):
        """Test verify_access returns False for inaccessible secrets."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            from google.api_core import exceptions

            mock_client.return_value.access_secret_version.side_effect = exceptions.NotFound(
                "Not found"
            )

            manager = SecretManager()
            result = manager.verify_access("inaccessible-secret")

            assert result is False

    def test_load_secrets_to_env(self):
        """Test loading secrets into environment variables."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            mock_response = MagicMock()
            mock_response.payload.data = b"env-value"
            mock_client.return_value.access_secret_version.return_value = mock_response

            manager = SecretManager()
            loaded = manager.load_secrets_to_env({"TEST_VAR": "test-secret"})

            assert loaded == 1
            assert "TEST_VAR" in os.environ
            # Clean up
            del os.environ["TEST_VAR"]

    def test_clear_cache(self):
        """Test cache clearing."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient"):
            manager = SecretManager()
            manager._secrets_cache["key"] = "value"

            manager.clear_cache()

            assert len(manager._secrets_cache) == 0


class TestGetSecretFunction:
    """Tests for the standalone get_secret function."""

    def test_get_secret_convenience_function(self):
        """Test the convenience function works correctly."""
        with patch("src.secrets_manager.secretmanager.SecretManagerServiceClient") as mock_client:
            mock_response = MagicMock()
            mock_response.payload.data = b"convenience-value"
            mock_client.return_value.access_secret_version.return_value = mock_response

            result = get_secret("test-secret")

            assert result is not None
