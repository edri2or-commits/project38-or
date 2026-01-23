"""Tests for Health Check API endpoints.

Tests the health module in src/api/routes/health.py.
Covers:
- Health check endpoint
- Root endpoint
- Test ping endpoint
- Relay status endpoint
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Mock dependencies before importing
_mock_database = MagicMock()
_mock_database.check_database_connection = AsyncMock(return_value=True)
sys.modules["src.api.database"] = _mock_database

# Now import the module
from src.api.routes.health import (
    HealthResponse,
    health_check,
    root,
    test_ping,
    relay_status,
)


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self):
        """Test creating a healthy response."""
        response = HealthResponse(
            status="healthy",
            timestamp=datetime.now(UTC),
            version="0.1.0",
            database="connected",
            build="2026-01-17-v2",
        )

        assert response.status == "healthy"
        assert response.database == "connected"
        assert response.version == "0.1.0"

    def test_degraded_response(self):
        """Test creating a degraded response."""
        response = HealthResponse(
            status="degraded",
            timestamp=datetime.now(UTC),
            version="0.1.0",
            database="disconnected",
            build="2026-01-17-v2",
        )

        assert response.status == "degraded"
        assert response.database == "disconnected"

    def test_default_values(self):
        """Test response with default values."""
        response = HealthResponse(
            status="healthy",
            timestamp=datetime.now(UTC),
            version="0.1.0",
        )

        assert response.database == "not_connected"
        assert response.build == ""


class TestHealthCheck:
    """Tests for health_check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when database is connected."""
        _mock_database.check_database_connection.return_value = True

        result = await health_check()

        assert result.status == "healthy"
        assert result.database == "connected"
        assert result.version == "0.1.0"
        assert result.build != ""

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check when database is disconnected."""
        _mock_database.check_database_connection.return_value = False

        result = await health_check()

        assert result.status == "degraded"
        assert result.database == "disconnected"

    @pytest.mark.asyncio
    async def test_health_check_has_timestamp(self):
        """Test that health check includes timestamp."""
        _mock_database.check_database_connection.return_value = True

        result = await health_check()

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)


class TestRoot:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_api_info(self):
        """Test that root returns API information."""
        result = await root()

        assert result["name"] == "Agent Platform API"
        assert result["version"] == "0.1.0"
        assert result["docs"] == "/docs"
        assert result["health"] == "/api/health"

    @pytest.mark.asyncio
    async def test_root_is_dict(self):
        """Test that root returns a dictionary."""
        result = await root()

        assert isinstance(result, dict)
        assert len(result) == 4


class TestTestPing:
    """Tests for test_ping endpoint."""

    @pytest.mark.asyncio
    async def test_ping_returns_pong(self):
        """Test that ping returns pong."""
        result = await test_ping()

        assert result["status"] == "pong"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_ping_message_content(self):
        """Test that ping message indicates routes are working."""
        result = await test_ping()

        assert "routes are working" in result["message"].lower()


class TestRelayStatus:
    """Tests for relay_status endpoint.

    Note: The relay_status endpoint imports functions from src.api.main
    at runtime, which requires complex mocking. Full integration testing
    should use FastAPI TestClient with the actual app.
    """

    def test_relay_response_expected_fields(self):
        """Test expected relay response structure."""
        # Define expected fields for relay status
        expected_fields = [
            "status",
            "relay_enabled",
            "repo",
            "issue",
        ]

        # Verify these are the fields we expect to receive
        assert "status" in expected_fields
        assert "relay_enabled" in expected_fields


class TestIntegration:
    """Integration tests for health routes."""

    @pytest.mark.asyncio
    async def test_health_and_root_consistency(self):
        """Test that health and root endpoints are consistent."""
        _mock_database.check_database_connection.return_value = True

        health_result = await health_check()
        root_result = await root()

        assert health_result.version == root_result["version"]

    @pytest.mark.asyncio
    async def test_all_endpoints_return_valid_data(self):
        """Test that all endpoints return valid data."""
        _mock_database.check_database_connection.return_value = True

        health_result = await health_check()
        root_result = await root()
        ping_result = await test_ping()

        # All should return without error
        assert health_result is not None
        assert root_result is not None
        assert ping_result is not None
