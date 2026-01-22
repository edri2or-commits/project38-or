"""Tests for MCP Gateway monitoring tools.

Tests the monitoring module in src/mcp_gateway/tools/monitoring.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _has_tenacity() -> bool:
    """Check if tenacity module is available."""
    try:
        import tenacity
        return True
    except ImportError:
        return False


def _can_import_monitoring() -> bool:
    """Check if monitoring module can be imported."""
    try:
        from src.mcp_gateway.tools.monitoring import (
            check_health,
            get_metrics,
            check_deployment_health,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _has_tenacity(),
        reason="tenacity module not available (required by railway)"
    ),
    pytest.mark.skipif(
        not _can_import_monitoring(),
        reason="mcp_gateway.tools.monitoring module not importable"
    ),
]


class TestCheckHealth:
    """Tests for check_health function."""

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self):
        """Test health check when all services are healthy."""
        from src.mcp_gateway.tools.monitoring import check_health

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = "railway-token"
        mock_config.railway_project_id = "proj-123"
        mock_config.n8n_base_url = "http://n8n.local"

        # Mock production app health response
        prod_response = MagicMock()
        prod_response.status_code = 200
        prod_response.json.return_value = {"status": "healthy", "database": "connected", "version": "1.0"}

        # Mock Railway API response
        railway_response = MagicMock()
        railway_response.status_code = 200

        # Mock n8n response
        n8n_response = MagicMock()
        n8n_response.status_code = 200

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = [prod_response, n8n_response]
                mock_instance.post.return_value = railway_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_health()

        assert result["status"] == "healthy"
        assert "services" in result
        assert "timestamp" in result
        assert result["services"]["mcp_gateway"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_check_health_production_unhealthy(self):
        """Test health check when production is unreachable."""
        from src.mcp_gateway.tools.monitoring import check_health
        import httpx

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = ""
        mock_config.n8n_base_url = ""

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_health()

        assert result["status"] == "unhealthy"
        assert result["services"]["production"]["status"] == "unreachable"

    @pytest.mark.asyncio
    async def test_check_health_railway_not_configured(self):
        """Test health check when Railway token is not configured."""
        from src.mcp_gateway.tools.monitoring import check_health

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = ""  # Not configured
        mock_config.n8n_base_url = ""

        prod_response = MagicMock()
        prod_response.status_code = 200
        prod_response.json.return_value = {"status": "healthy"}

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = prod_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_health()

        assert result["services"]["railway_api"]["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_check_health_n8n_not_configured(self):
        """Test health check when n8n is not configured."""
        from src.mcp_gateway.tools.monitoring import check_health

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = ""
        mock_config.n8n_base_url = ""  # Not configured

        prod_response = MagicMock()
        prod_response.status_code = 200
        prod_response.json.return_value = {"status": "healthy"}

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = prod_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_health()

        assert result["services"]["n8n"]["status"] == "not_configured"


class TestGetMetrics:
    """Tests for get_metrics function."""

    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        """Test successful metrics retrieval from production."""
        from src.mcp_gateway.tools.monitoring import get_metrics

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cpu": 25, "memory": 60}

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await get_metrics()

        assert result["status"] == "success"
        assert result["source"] == "production_app"
        assert result["metrics"]["cpu"] == 25

    @pytest.mark.asyncio
    async def test_get_metrics_production_error(self):
        """Test metrics fallback when production is unavailable."""
        from src.mcp_gateway.tools.monitoring import get_metrics

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await get_metrics()

        assert result["status"] == "error"
        assert "500" in result["message"]

    @pytest.mark.asyncio
    async def test_get_metrics_connection_error_fallback(self):
        """Test metrics fallback to MCP Gateway metrics on connection error."""
        from src.mcp_gateway.tools.monitoring import get_metrics
        import httpx

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = httpx.ConnectError("Refused")
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await get_metrics()

        assert result["status"] == "partial"
        assert result["source"] == "mcp_gateway"
        assert "mcp_gateway" in result["metrics"]


class TestCheckDeploymentHealth:
    """Tests for check_deployment_health function."""

    @pytest.mark.asyncio
    async def test_deployment_health_combines_health_and_deployment(self):
        """Test that deployment health combines health check and deployment status."""
        from src.mcp_gateway.tools.monitoring import check_deployment_health

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = "token"
        mock_config.railway_service_id = "svc-123"
        mock_config.railway_environment_id = "env-456"
        mock_config.railway_project_id = "proj-789"
        mock_config.n8n_base_url = ""

        # Mock health check response
        health_response = MagicMock()
        health_response.status_code = 200
        health_response.json.return_value = {"status": "healthy"}

        # Mock Railway API response
        railway_response = MagicMock()
        railway_response.status_code = 200
        railway_response.json.return_value = {"data": {"me": {"name": "test"}}}

        # Mock deployment status response
        deployment_response = MagicMock()
        deployment_response.status_code = 200
        deployment_response.json.return_value = {
            "data": {"deployments": {"edges": [{"node": {"id": "dep-1", "status": "SUCCESS"}}]}}
        }
        deployment_response.raise_for_status = MagicMock()

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = health_response
                mock_instance.post.side_effect = [railway_response, deployment_response]
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_deployment_health()

        assert "health" in result
        assert "deployment" in result
        assert "action_required" in result

    @pytest.mark.asyncio
    async def test_deployment_health_unhealthy_with_recommendation(self):
        """Test that unhealthy status includes recommendation."""
        from src.mcp_gateway.tools.monitoring import check_deployment_health
        import httpx

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = ""
        mock_config.n8n_base_url = ""

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = httpx.ConnectError("Refused")
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_deployment_health()

        assert result["health"]["status"] == "unhealthy"
        assert result["action_required"] is True
        assert result["recommendation"] is not None

    @pytest.mark.asyncio
    async def test_deployment_health_degraded(self):
        """Test degraded status when some services are down."""
        from src.mcp_gateway.tools.monitoring import check_deployment_health

        mock_config = MagicMock()
        mock_config.production_url = "https://prod.local"
        mock_config.railway_token = ""  # Not configured - will cause degraded
        mock_config.n8n_base_url = ""

        health_response = MagicMock()
        health_response.status_code = 200
        health_response.json.return_value = {"status": "healthy"}

        with patch("src.mcp_gateway.tools.monitoring.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = health_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await check_deployment_health()

        assert result["health"]["status"] == "degraded"
        assert "Monitor closely" in result["recommendation"]
