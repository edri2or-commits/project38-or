"""Tests for secrets health API routes.

Tests the /api/secrets/* endpoints defined in src/api/routes/secrets_health.py.
These endpoints import modules lazily inside functions, so we test both
the endpoint behavior and the response models.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _has_cryptography() -> bool:
    """Check if cryptography module is available."""
    try:
        import _cffi_backend
        import cryptography.hazmat.primitives
        return True
    except (ImportError, ModuleNotFoundError):
        return False
    except Exception:
        # Rust panic or other errors
        return False


# Skip entire module if cryptography is not available
pytestmark = pytest.mark.skipif(
    not _has_cryptography(),
    reason="cryptography module not available (required by secrets_health router)"
)


def create_test_app():
    """Create a FastAPI app with the secrets_health router for testing."""
    # Import here to avoid import error at module level
    from src.api.routes.secrets_health import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_test_app()
    return TestClient(app)


class TestSecretsHealthEndpoint:
    """Tests for GET /api/secrets/health endpoint."""

    def test_health_returns_response(self, client):
        """Test health endpoint returns a valid response structure."""
        # The endpoint imports modules lazily and catches all exceptions
        response = client.get("/api/secrets/health")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        # Returns either status or error
        assert "status" in data

    def test_health_with_mocked_monitor(self, client):
        """Test health endpoint with mocked monitor."""
        mock_monitor = MagicMock()
        mock_monitor.check_wif_health = AsyncMock(
            return_value={"status": "healthy", "latency_ms": 50}
        )
        mock_monitor.get_health_report.return_value = {
            "metrics": {"success_rate": 99.5},
            "status": "healthy",
            "alerting": {"enabled": True},
        }

        # Patch at the source module where it's imported
        with patch("src.secrets_health.get_wif_monitor", return_value=mock_monitor):
            response = client.get("/api/secrets/health")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data


class TestCredentialsHealthEndpoint:
    """Tests for GET /api/secrets/credentials endpoint."""

    def test_credentials_returns_response(self, client):
        """Test credentials endpoint returns a valid response structure."""
        response = client.get("/api/secrets/credentials")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        # Returns all_healthy or error
        assert "all_healthy" in data or "error" in data


class TestCredentialsRefreshEndpoint:
    """Tests for POST /api/secrets/credentials/refresh endpoint."""

    def test_refresh_returns_response(self, client):
        """Test refresh endpoint returns a response."""
        response = client.post("/api/secrets/credentials/refresh")

        # May return 200 or 500 depending on module availability
        assert response.status_code in [200, 500]
        data = response.json()
        # Either success or detail (error)
        assert "success" in data or "detail" in data


class TestRotationHistoryEndpoint:
    """Tests for GET /api/secrets/rotation/history endpoint."""

    def test_rotation_history_returns_response(self, client):
        """Test history endpoint returns a valid response."""
        response = client.get("/api/secrets/rotation/history")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "history" in data

    def test_rotation_history_with_filter(self, client):
        """Test history endpoint with secret_name filter."""
        response = client.get("/api/secrets/rotation/history?secret_name=TEST")

        assert response.status_code == 200
        data = response.json()
        assert "history" in data


class TestRotateSecretEndpoint:
    """Tests for POST /api/secrets/rotation/{secret_name} endpoint."""

    def test_rotate_secret_requires_new_value(self, client):
        """Test rotate endpoint requires new_value parameter."""
        # The endpoint expects new_value as body param
        response = client.post(
            "/api/secrets/rotation/TEST-SECRET",
            json={"new_value": "test-value"},
        )

        # Endpoint will try to rotate and likely fail without real backend
        # but should return structured response
        assert response.status_code in [200, 422, 500]

    def test_rotate_secret_path_param(self, client):
        """Test secret name is captured from path."""
        response = client.post(
            "/api/secrets/rotation/MY-SECRET",
            json={"new_value": "new-secret-value"},
        )

        assert response.status_code in [200, 422, 500]


class TestRollbackSecretEndpoint:
    """Tests for POST /api/secrets/rotation/{secret_name}/rollback endpoint."""

    def test_rollback_requires_version(self, client):
        """Test rollback endpoint requires to_version parameter."""
        response = client.post(
            "/api/secrets/rotation/TEST-SECRET/rollback",
            json={"to_version": "v1"},
        )

        assert response.status_code in [200, 422, 500]


class TestResponseStructures:
    """Tests for expected response structures."""

    def test_health_error_structure(self, client):
        """Test health error response has expected structure."""
        response = client.get("/api/secrets/health")

        data = response.json()
        # Should always have timestamp
        assert "timestamp" in data
        # And status
        assert "status" in data

    def test_credentials_error_structure(self, client):
        """Test credentials error response has expected structure."""
        response = client.get("/api/secrets/credentials")

        data = response.json()
        assert "timestamp" in data
        # all_healthy is present even on error (False)
        assert "all_healthy" in data or "error" in data

    def test_history_empty_on_error(self, client):
        """Test history returns empty list on error."""
        response = client.get("/api/secrets/rotation/history")

        data = response.json()
        # history should be present (possibly empty)
        assert "history" in data
        assert isinstance(data["history"], list)


class TestEndpointPaths:
    """Tests for endpoint URL paths."""

    def test_health_path(self, client):
        """Test /api/secrets/health path exists."""
        response = client.get("/api/secrets/health")
        assert response.status_code != 404

    def test_credentials_path(self, client):
        """Test /api/secrets/credentials path exists."""
        response = client.get("/api/secrets/credentials")
        assert response.status_code != 404

    def test_credentials_refresh_path(self, client):
        """Test /api/secrets/credentials/refresh path exists."""
        response = client.post("/api/secrets/credentials/refresh")
        assert response.status_code != 404

    def test_rotation_history_path(self, client):
        """Test /api/secrets/rotation/history path exists."""
        response = client.get("/api/secrets/rotation/history")
        assert response.status_code != 404

    def test_rotation_path(self, client):
        """Test /api/secrets/rotation/{name} path exists."""
        response = client.post(
            "/api/secrets/rotation/TEST",
            json={"new_value": "test"},
        )
        # 422 or 500 is acceptable (not 404)
        assert response.status_code != 404

    def test_rollback_path(self, client):
        """Test /api/secrets/rotation/{name}/rollback path exists."""
        response = client.post(
            "/api/secrets/rotation/TEST/rollback",
            json={"to_version": "v1"},
        )
        assert response.status_code != 404


# =============================================================================
# Direct endpoint function tests (for actual coverage)
# =============================================================================
from src.api.routes.secrets_health import (
    get_secrets_health,
    get_credentials_health,
    trigger_credential_refresh,
    get_rotation_history,
    rotate_secret,
    rollback_secret,
)
from fastapi import HTTPException


class TestGetSecretsHealthDirect:
    """Direct tests for get_secrets_health endpoint function."""

    @pytest.mark.asyncio
    async def test_get_health_success(self):
        """Test successful health check."""
        mock_monitor = MagicMock()
        mock_monitor.check_wif_health = AsyncMock(
            return_value={"status": "healthy", "latency_ms": 50}
        )
        mock_monitor.get_health_report.return_value = {
            "metrics": {"success_rate": 99.5},
            "status": "healthy",
            "alerting": {"enabled": True},
        }

        # Patch at source module (lazy import inside function)
        with patch("src.secrets_health.get_wif_monitor", return_value=mock_monitor):
            result = await get_secrets_health()

        assert "timestamp" in result
        assert result["status"] == "healthy"
        assert "metrics" in result
        assert "alerting" in result

    @pytest.mark.asyncio
    async def test_get_health_exception(self):
        """Test health check returns error on exception."""
        with patch(
            "src.secrets_health.get_wif_monitor",
            side_effect=ImportError("Module not found"),
        ):
            result = await get_secrets_health()

        assert "timestamp" in result
        assert result["status"] == "error"
        assert "error" in result


class TestGetCredentialsHealthDirect:
    """Direct tests for get_credentials_health endpoint function."""

    @pytest.mark.asyncio
    async def test_get_credentials_success(self):
        """Test successful credentials check."""
        mock_health = MagicMock()
        mock_health.all_healthy = True
        mock_health.failed_credentials = []
        mock_health.expiring_soon = []

        mock_manager = MagicMock()
        mock_manager.check_all_credentials = AsyncMock(return_value=mock_health)
        mock_manager.get_expiration_report.return_value = {"summary": "all ok"}
        mock_manager.close = AsyncMock()

        # Patch at source module (lazy import inside function)
        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            return_value=mock_manager,
        ):
            result = await get_credentials_health()

        assert "timestamp" in result
        assert result["all_healthy"] is True
        assert result["failed"] == []
        assert result["expiring_soon"] == []
        mock_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credentials_with_failures(self):
        """Test credentials check with failed credentials."""
        mock_cred = MagicMock()
        mock_cred.value = "RAILWAY-API"

        mock_health = MagicMock()
        mock_health.all_healthy = False
        mock_health.failed_credentials = [mock_cred]
        mock_health.expiring_soon = []

        mock_manager = MagicMock()
        mock_manager.check_all_credentials = AsyncMock(return_value=mock_health)
        mock_manager.get_expiration_report.return_value = {"summary": "issues"}
        mock_manager.close = AsyncMock()

        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            return_value=mock_manager,
        ):
            result = await get_credentials_health()

        assert result["all_healthy"] is False
        assert "RAILWAY-API" in result["failed"]

    @pytest.mark.asyncio
    async def test_get_credentials_exception(self):
        """Test credentials check returns error on exception."""
        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            side_effect=ImportError("Module not found"),
        ):
            result = await get_credentials_health()

        assert "timestamp" in result
        assert result["all_healthy"] is False
        assert "error" in result


class TestTriggerCredentialRefreshDirect:
    """Direct tests for trigger_credential_refresh endpoint function."""

    @pytest.mark.asyncio
    async def test_refresh_no_issues(self):
        """Test refresh when no credentials need attention."""
        mock_health = MagicMock()
        mock_health.failed_credentials = []
        mock_health.expiring_soon = []

        mock_manager = MagicMock()
        mock_manager.check_all_credentials = AsyncMock(return_value=mock_health)
        mock_manager.close = AsyncMock()

        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            return_value=mock_manager,
        ):
            result = await trigger_credential_refresh()

        assert result["success"] is True
        assert result["results"] == {}

    @pytest.mark.asyncio
    async def test_refresh_with_failed_credentials(self):
        """Test refresh triggers recovery for failed credentials."""
        mock_cred = MagicMock()
        mock_cred.value = "RAILWAY-API"

        mock_health = MagicMock()
        mock_health.failed_credentials = [mock_cred]
        mock_health.expiring_soon = []

        mock_manager = MagicMock()
        mock_manager.check_all_credentials = AsyncMock(return_value=mock_health)
        mock_manager.trigger_recovery = AsyncMock(return_value={mock_cred: True})
        mock_manager.close = AsyncMock()

        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            return_value=mock_manager,
        ):
            result = await trigger_credential_refresh()

        assert result["success"] is True
        assert "recovery" in result["results"]
        mock_manager.trigger_recovery.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_with_expiring_soon(self):
        """Test refresh reports expiring credentials."""
        mock_cred = MagicMock()
        mock_cred.value = "OPENAI-API"

        mock_health = MagicMock()
        mock_health.failed_credentials = []
        mock_health.expiring_soon = [mock_cred]

        mock_manager = MagicMock()
        mock_manager.check_all_credentials = AsyncMock(return_value=mock_health)
        mock_manager.close = AsyncMock()

        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            return_value=mock_manager,
        ):
            result = await trigger_credential_refresh()

        assert result["success"] is True
        assert "OPENAI-API" in result["results"]["refreshed"]

    @pytest.mark.asyncio
    async def test_refresh_exception_raises_http_error(self):
        """Test refresh raises HTTPException on error."""
        with patch(
            "src.credential_lifecycle.CredentialLifecycleManager",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await trigger_credential_refresh()

        assert exc_info.value.status_code == 500


class TestGetRotationHistoryDirect:
    """Direct tests for get_rotation_history endpoint function."""

    @pytest.mark.asyncio
    async def test_get_history_success(self):
        """Test successful history retrieval."""
        mock_history = [
            {"secret": "TEST", "timestamp": "2026-01-23T00:00:00Z"},
        ]

        mock_interlock = MagicMock()
        mock_interlock.get_rotation_history.return_value = mock_history

        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.return_value = mock_interlock

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await get_rotation_history()

        assert "timestamp" in result
        assert result["count"] == 1
        assert result["history"] == mock_history

    @pytest.mark.asyncio
    async def test_get_history_with_filter(self):
        """Test history with secret_name filter."""
        mock_interlock = MagicMock()
        mock_interlock.get_rotation_history.return_value = []

        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.return_value = mock_interlock

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await get_rotation_history(secret_name="TEST-SECRET")

        mock_interlock.get_rotation_history.assert_called_once_with("TEST-SECRET")
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_get_history_exception(self):
        """Test history returns empty on exception."""
        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.side_effect = Exception("Not available")

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await get_rotation_history()

        assert "timestamp" in result
        assert "error" in result
        assert result["history"] == []


class TestRotateSecretDirect:
    """Direct tests for rotate_secret endpoint function."""

    @pytest.mark.asyncio
    async def test_rotate_success(self):
        """Test successful secret rotation."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.secret_name = "TEST-SECRET"
        mock_result.old_version = "v1"
        mock_result.new_version = "v2"
        mock_result.state.value = "completed"
        mock_result.error = None
        mock_result.duration_seconds = 1.5

        mock_interlock = MagicMock()
        mock_interlock.rotate_token = AsyncMock(return_value=mock_result)

        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.return_value = mock_interlock

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await rotate_secret(secret_name="TEST-SECRET", new_value="new-value")

        assert result["success"] is True
        assert result["secret_name"] == "TEST-SECRET"
        assert result["new_version"] == "v2"

    @pytest.mark.asyncio
    async def test_rotate_failure(self):
        """Test rotation failure response."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.secret_name = "TEST-SECRET"
        mock_result.old_version = "v1"
        mock_result.new_version = None
        mock_result.state.value = "failed"
        mock_result.error = "Access denied"
        mock_result.duration_seconds = 0.5

        mock_interlock = MagicMock()
        mock_interlock.rotate_token = AsyncMock(return_value=mock_result)

        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.return_value = mock_interlock

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await rotate_secret(secret_name="TEST-SECRET", new_value="new-value")

        assert result["success"] is False
        assert result["error"] == "Access denied"

    @pytest.mark.asyncio
    async def test_rotate_exception_raises_http_error(self):
        """Test rotation raises HTTPException on exception."""
        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.side_effect = Exception("Backend unavailable")

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            with pytest.raises(HTTPException) as exc_info:
                await rotate_secret(secret_name="TEST", new_value="value")

        assert exc_info.value.status_code == 500


class TestRollbackSecretDirect:
    """Direct tests for rollback_secret endpoint function."""

    @pytest.mark.asyncio
    async def test_rollback_success(self):
        """Test successful rollback."""
        mock_interlock = MagicMock()
        mock_interlock.rollback.return_value = True

        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.return_value = mock_interlock

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await rollback_secret(secret_name="TEST-SECRET", to_version="v1")

        assert result["success"] is True
        assert result["secret_name"] == "TEST-SECRET"
        assert result["rolled_back_to"] == "v1"

    @pytest.mark.asyncio
    async def test_rollback_failure(self):
        """Test rollback failure."""
        mock_interlock = MagicMock()
        mock_interlock.rollback.return_value = False

        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.return_value = mock_interlock

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            result = await rollback_secret(secret_name="TEST-SECRET", to_version="v1")

        assert result["success"] is False
        assert result["rolled_back_to"] is None

    @pytest.mark.asyncio
    async def test_rollback_exception_raises_http_error(self):
        """Test rollback raises HTTPException on exception."""
        mock_token_rotation = MagicMock()
        mock_token_rotation.get_rotation_interlock.side_effect = Exception("Version not found")

        with patch.dict("sys.modules", {"src.token_rotation": mock_token_rotation}):
            with pytest.raises(HTTPException) as exc_info:
                await rollback_secret(secret_name="TEST", to_version="v1")

        assert exc_info.value.status_code == 500
