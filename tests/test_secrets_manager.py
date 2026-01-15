"""Unit tests for SecretManager module"""

import os
from unittest.mock import MagicMock


class TestSecretManager:
    """Test suite for SecretManager class"""

    def test_get_secret_success(self, secret_manager, mock_secret_data: dict[str, str]) -> None:
        """Test successful secret retrieval"""
        result = secret_manager.get_secret("TEST-SECRET-1")
        assert result == mock_secret_data["TEST-SECRET-1"]

    def test_get_secret_not_found(self, secret_manager) -> None:
        """Test secret not found returns None"""
        result = secret_manager.get_secret("NONEXISTENT-SECRET")
        assert result is None

    def test_get_secret_caching(self, secret_manager, mock_gcp_client: MagicMock) -> None:
        """Test that secrets are cached after first retrieval"""
        # First call
        secret_manager.get_secret("TEST-SECRET-1")
        call_count_after_first = mock_gcp_client.access_secret_version.call_count

        # Second call should use cache
        secret_manager.get_secret("TEST-SECRET-1")
        call_count_after_second = mock_gcp_client.access_secret_version.call_count

        # Should not have made another API call
        assert call_count_after_first == call_count_after_second

    def test_clear_cache(self, secret_manager, mock_gcp_client: MagicMock) -> None:
        """Test cache clearing works correctly"""
        # Populate cache
        secret_manager.get_secret("TEST-SECRET-1")
        initial_call_count = mock_gcp_client.access_secret_version.call_count

        # Clear cache
        secret_manager.clear_cache()

        # Next call should hit API again
        secret_manager.get_secret("TEST-SECRET-1")
        assert mock_gcp_client.access_secret_version.call_count > initial_call_count

    def test_list_secrets(self, secret_manager, mock_secret_data: dict[str, str]) -> None:
        """Test listing available secrets"""
        secrets = secret_manager.list_secrets()
        assert len(secrets) == len(mock_secret_data)
        for secret_name in mock_secret_data:
            assert secret_name in secrets

    def test_verify_access_exists(self, secret_manager) -> None:
        """Test verify_access returns True for existing secrets"""
        assert secret_manager.verify_access("TEST-SECRET-1") is True

    def test_verify_access_not_exists(self, secret_manager) -> None:
        """Test verify_access returns False for non-existing secrets"""
        assert secret_manager.verify_access("NONEXISTENT-SECRET") is False

    def test_load_secrets_to_env(self, secret_manager) -> None:
        """Test loading secrets into environment variables"""
        # Clean up any existing env vars
        env_var_name = "TEST_ENV_VAR_FOR_PYTEST"
        if env_var_name in os.environ:
            del os.environ[env_var_name]

        mapping = {env_var_name: "TEST-SECRET-1"}
        loaded_count = secret_manager.load_secrets_to_env(mapping)

        assert loaded_count == 1
        assert env_var_name in os.environ
        assert os.environ[env_var_name] == "test-value-1"

        # Cleanup
        del os.environ[env_var_name]

    def test_load_secrets_to_env_partial_failure(self, secret_manager) -> None:
        """Test loading secrets with some failures"""
        env_var_1 = "TEST_ENV_VAR_SUCCESS"
        env_var_2 = "TEST_ENV_VAR_FAIL"

        # Clean up
        for var in [env_var_1, env_var_2]:
            if var in os.environ:
                del os.environ[var]

        mapping = {
            env_var_1: "TEST-SECRET-1",
            env_var_2: "NONEXISTENT-SECRET",
        }
        loaded_count = secret_manager.load_secrets_to_env(mapping)

        assert loaded_count == 1
        assert env_var_1 in os.environ
        assert env_var_2 not in os.environ

        # Cleanup
        if env_var_1 in os.environ:
            del os.environ[env_var_1]


class TestSecretManagerInit:
    """Test SecretManager initialization"""

    def test_default_project_id(self, mock_gcp_client: MagicMock) -> None:
        """Test default project ID is set correctly"""
        from src.secrets_manager import SecretManager

        manager = SecretManager()
        assert manager.project_id == "project38-483612"

    def test_custom_project_id(self, mock_gcp_client: MagicMock) -> None:
        """Test custom project ID is respected"""
        from src.secrets_manager import SecretManager

        manager = SecretManager(project_id="custom-project")
        assert manager.project_id == "custom-project"


class TestConvenienceFunction:
    """Test module-level convenience functions"""

    def test_get_secret_function(self, mock_gcp_client: MagicMock) -> None:
        """Test the get_secret convenience function"""
        from src.secrets_manager import get_secret

        result = get_secret("TEST-SECRET-1", project_id="test-project")
        assert result == "test-value-1"
