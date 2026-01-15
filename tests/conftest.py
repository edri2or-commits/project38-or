"""Pytest configuration and fixtures for project38-or tests"""

import sys
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

# Create mock exception classes
_NotFound = type("NotFound", (Exception,), {})
_PermissionDenied = type("PermissionDenied", (Exception,), {})


# Create mock modules before any src imports
class MockExceptions:
    NotFound = _NotFound
    PermissionDenied = _PermissionDenied


# Create the mock client that will be used by all tests
_mock_client_instance = MagicMock()


class MockSecretManager:
    SecretManagerServiceClient = MagicMock(return_value=_mock_client_instance)


# Install mocks into sys.modules
_mock_google = MagicMock()
_mock_api_core = MagicMock()
_mock_api_core.exceptions = MockExceptions
_mock_cloud = MagicMock()
_mock_cloud.secretmanager = MockSecretManager

sys.modules["google"] = _mock_google
sys.modules["google.api_core"] = _mock_api_core
sys.modules["google.api_core.exceptions"] = MockExceptions
sys.modules["google.cloud"] = _mock_cloud
sys.modules["google.cloud.secretmanager"] = MockSecretManager


@pytest.fixture
def mock_secret_data() -> dict[str, str]:
    """Mock secret data for testing (NOT real secrets)"""
    return {
        "TEST-SECRET-1": "test-value-1",
        "TEST-SECRET-2": "test-value-2",
        "ANTHROPIC-API": "mock-anthropic-key-for-testing",
    }


@pytest.fixture
def mock_gcp_client(mock_secret_data: dict[str, str]) -> Generator[MagicMock, None, None]:
    """Mock GCP Secret Manager client for testing without GCP access"""
    # Reset mock for this test
    _mock_client_instance.reset_mock()

    # Mock access_secret_version
    def mock_access_secret_version(request: dict) -> MagicMock:
        name = request.get("name", "")
        # Extract secret_id from path: projects/{project}/secrets/{secret_id}/versions/{version}
        parts = name.split("/")
        if len(parts) >= 4:
            secret_id = parts[3]
            if secret_id in mock_secret_data:
                response = MagicMock()
                response.payload.data.decode.return_value = mock_secret_data[secret_id]
                return response

        # Simulate NotFound
        raise _NotFound(f"Secret not found: {name}")

    _mock_client_instance.access_secret_version.side_effect = mock_access_secret_version

    # Mock list_secrets
    secrets_list = []
    for secret_name in mock_secret_data:
        mock_secret = MagicMock()
        mock_secret.name = f"projects/test-project/secrets/{secret_name}"
        secrets_list.append(mock_secret)
    _mock_client_instance.list_secrets.return_value = secrets_list

    yield _mock_client_instance


@pytest.fixture
def secret_manager(mock_gcp_client: MagicMock):
    """Create SecretManager instance with mocked GCP client"""
    # Import here after mocks are set up
    from src.secrets_manager import SecretManager

    manager = SecretManager(project_id="test-project")
    # Clear any cached data from previous tests
    manager.clear_cache()
    return manager
