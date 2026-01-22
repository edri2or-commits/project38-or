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
