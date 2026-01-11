"""
Tests for health check API endpoint.

This module tests the health check and root endpoints.
"""

import pytest
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

    def test_health_check_status_healthy(self):
        """Test that health check returns healthy status."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_check_version(self):
        """Test that health check returns correct API version."""
        response = client.get("/health")
        data = response.json()

        assert data["version"] == "0.1.0"

    def test_health_check_database_not_connected(self):
        """Test that database status is not_connected (before DB integration)."""
        response = client.get("/health")
        data = response.json()

        assert data["database"] == "not_connected"


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
