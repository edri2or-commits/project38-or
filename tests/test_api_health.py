"""
Tests for health check API endpoint.

This module tests the health check and root endpoints.
"""

from fastapi.testclient import TestClient

from src.api.main import app

# Create test client
client = TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_returns_200(self):
        """Test that health check endpoint returns 200 status code."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self):
        """Test that health check returns correct response structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "database" in data

    def test_health_check_status_healthy_or_degraded(self):
        """Test that health check returns healthy or degraded status."""
        response = client.get("/health")
        data = response.json()

        # Status can be "healthy" (DB connected) or "degraded" (DB disconnected)
        assert data["status"] in ["healthy", "degraded"]

    def test_health_check_version(self):
        """Test that health check returns correct API version."""
        response = client.get("/health")
        data = response.json()

        assert data["version"] == "0.1.0"

    def test_health_check_database_status(self):
        """Test that database status is reported."""
        response = client.get("/health")
        data = response.json()

        # Database can be "connected" or "disconnected"
        assert data["database"] in ["connected", "disconnected"]


class TestRootEndpoint:
    """Tests for / root endpoint."""

    def test_root_returns_200(self):
        """Test that root endpoint returns 200 status code."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_structure(self):
        """Test that root endpoint returns correct structure."""
        response = client.get("/")
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data

    def test_root_metadata(self):
        """Test that root endpoint returns correct metadata."""
        response = client.get("/")
        data = response.json()

        assert data["name"] == "Agent Platform API"
        assert data["version"] == "0.1.0"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"
