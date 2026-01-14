"""Tests for Cost Alert Service and n8n Workflow Integration.

Tests cover:
- Alert severity detection
- Rate limiting
- Webhook payload creation
- n8n workflow configuration
"""

import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock google module before importing
sys.modules["google"] = MagicMock()
sys.modules["google.api_core"] = MagicMock()
sys.modules["google.api_core.exceptions"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.secretmanager"] = MagicMock()

from src.cost_alert_service import AlertResult, CostAlertService  # noqa: E402
from src.workflows.cost_alert_workflow import (  # noqa: E402
    COST_ALERT_REGISTRY,
    create_alert_payload,
    create_cost_alert_workflow,
    get_severity_from_percentage,
    get_workflow_connections,
    get_workflow_nodes,
)

# =============================================================================
# ALERT PAYLOAD TESTS
# =============================================================================


class TestAlertPayload:
    """Tests for alert payload creation."""

    def test_create_alert_payload(self):
        """Test creating alert payload with all fields."""
        payload = create_alert_payload(
            severity="warning",
            budget=50.0,
            projected_cost=42.0,
            percentage_used=84.0,
            status="warning",
            recommendations="Consider reducing vCPU allocation",
        )

        assert payload["severity"] == "warning"
        assert payload["budget"] == 50.0
        assert payload["projected_cost"] == 42.0
        assert payload["percentage_used"] == 84.0
        assert payload["status"] == "warning"
        assert "timestamp" in payload

    def test_create_alert_payload_rounding(self):
        """Test that payload values are properly rounded."""
        payload = create_alert_payload(
            severity="info",
            budget=49.999,
            projected_cost=10.12345,
            percentage_used=20.267,
            status="ok",
        )

        assert payload["budget"] == 50.0
        assert payload["projected_cost"] == 10.12
        assert payload["percentage_used"] == 20.3


class TestSeverityDetection:
    """Tests for severity detection from percentage."""

    def test_critical_at_100_percent(self):
        """Test critical severity at 100%."""
        assert get_severity_from_percentage(100.0) == "critical"
        assert get_severity_from_percentage(150.0) == "critical"

    def test_warning_at_80_percent(self):
        """Test warning severity at 80-99%."""
        assert get_severity_from_percentage(80.0) == "warning"
        assert get_severity_from_percentage(99.9) == "warning"

    def test_info_below_80_percent(self):
        """Test info severity below 80%."""
        assert get_severity_from_percentage(0.0) == "info"
        assert get_severity_from_percentage(50.0) == "info"
        assert get_severity_from_percentage(79.9) == "info"


# =============================================================================
# WORKFLOW CONFIGURATION TESTS
# =============================================================================


class TestWorkflowConfiguration:
    """Tests for n8n workflow configuration."""

    def test_create_workflow_structure(self):
        """Test workflow has required structure."""
        workflow = create_cost_alert_workflow()

        assert "name" in workflow
        assert "nodes" in workflow
        assert "connections" in workflow
        assert "active" in workflow
        assert "settings" in workflow

    def test_workflow_has_required_nodes(self):
        """Test workflow has all required nodes."""
        nodes = get_workflow_nodes()
        node_names = [n["name"] for n in nodes]

        assert "Cost Alert Webhook" in node_names
        assert "Check Severity" in node_names
        assert "Format Critical Alert" in node_names
        assert "Format Warning Alert" in node_names
        assert "Format Info Alert" in node_names
        assert "Send Telegram Notification" in node_names

    def test_workflow_connections_valid(self):
        """Test workflow connections are properly structured."""
        connections = get_workflow_connections()

        assert "Cost Alert Webhook" in connections
        assert "Check Severity" in connections
        # Switch should have 3 outputs (critical, warning, info)
        assert len(connections["Check Severity"]["main"]) == 3

    def test_webhook_node_configuration(self):
        """Test webhook node is properly configured."""
        nodes = get_workflow_nodes()
        webhook = next(n for n in nodes if n["name"] == "Cost Alert Webhook")

        assert webhook["type"] == "n8n-nodes-base.webhook"
        assert webhook["parameters"]["path"] == "cost-alert"
        assert webhook["parameters"]["httpMethod"] == "POST"

    def test_telegram_node_configuration(self):
        """Test Telegram node is properly configured."""
        nodes = get_workflow_nodes()
        telegram = next(n for n in nodes if n["name"] == "Send Telegram Notification")

        assert telegram["type"] == "n8n-nodes-base.telegram"
        assert "chatId" in telegram["parameters"]
        assert "text" in telegram["parameters"]


class TestWorkflowRegistry:
    """Tests for workflow registry entries."""

    def test_cost_alert_in_registry(self):
        """Test cost-alert workflow is registered."""
        assert "cost-alert" in COST_ALERT_REGISTRY
        assert COST_ALERT_REGISTRY["cost-alert"]["path"] == "/webhook/cost-alert"
        assert COST_ALERT_REGISTRY["cost-alert"]["method"] == "POST"

    def test_weekly_report_in_registry(self):
        """Test cost-weekly-report workflow is registered."""
        assert "cost-weekly-report" in COST_ALERT_REGISTRY


# =============================================================================
# ALERT SERVICE TESTS
# =============================================================================


class TestCostAlertService:
    """Tests for CostAlertService."""

    @pytest.fixture
    def mock_cost_monitor(self):
        """Create mock cost monitor."""
        monitor = MagicMock()
        monitor.is_budget_exceeded = AsyncMock(return_value=(False, 25.0))
        monitor.get_current_usage = AsyncMock(return_value=MagicMock(cpu_percent=50, memory_mb=512))
        monitor.get_cost_optimization_recommendations = MagicMock(
            return_value=[{"title": "Resources optimized", "priority": "low"}]
        )
        return monitor

    @pytest.fixture
    def service(self, mock_cost_monitor):
        """Create CostAlertService with mocks."""
        return CostAlertService(
            cost_monitor=mock_cost_monitor,
            n8n_webhook_url="https://n8n.test/webhook/cost-alert",
        )

    @pytest.mark.asyncio
    async def test_check_and_alert_below_threshold(self, service):
        """Test no alert sent when below threshold."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await service.check_and_alert(
                deployment_id="test-deploy",
                budget=50.0,
            )

            # Should send info alert (first time)
            assert result.severity == "info"
            assert result.percentage_used == 50.0

    @pytest.mark.asyncio
    async def test_check_and_alert_warning(self, service, mock_cost_monitor):
        """Test warning alert when at 80-99%."""
        mock_cost_monitor.is_budget_exceeded = AsyncMock(return_value=(False, 45.0))

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await service.check_and_alert(
                deployment_id="test-deploy",
                budget=50.0,
            )

            assert result.severity == "warning"
            assert result.percentage_used == 90.0

    @pytest.mark.asyncio
    async def test_check_and_alert_critical(self, service, mock_cost_monitor):
        """Test critical alert when budget exceeded."""
        mock_cost_monitor.is_budget_exceeded = AsyncMock(return_value=(True, 60.0))

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await service.check_and_alert(
                deployment_id="test-deploy",
                budget=50.0,
            )

            assert result.severity == "critical"
            assert result.percentage_used == 120.0

    @pytest.mark.asyncio
    async def test_rate_limiting(self, service):
        """Test rate limiting prevents spam."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # First alert should be sent
            result1 = await service.check_and_alert("test", 50.0)
            assert result1.alert_sent is True

            # Second alert should be rate limited
            result2 = await service.check_and_alert("test", 50.0)
            assert result2.alert_sent is False
            assert "rate limited" in result2.message.lower()

    @pytest.mark.asyncio
    async def test_force_alert_bypasses_rate_limit(self, service):
        """Test force flag bypasses rate limiting."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # First alert
            await service.check_and_alert("test", 50.0)

            # Force second alert
            result = await service.check_and_alert("test", 50.0, force=True)
            assert result.alert_sent is True

    def test_reset_rate_limits(self, service):
        """Test rate limit reset."""
        # Add some rate limit entries
        service._last_alert["critical"] = datetime.now(UTC)
        service._last_alert["warning"] = datetime.now(UTC)

        service.reset_rate_limits()

        assert len(service._last_alert) == 0

    def test_get_alert_status(self, service):
        """Test getting alert status."""
        status = service.get_alert_status()

        assert "last_alerts" in status
        assert "cooldowns" in status
        assert "webhook_url" in status
        assert "thresholds" in status


class TestAlertResult:
    """Tests for AlertResult dataclass."""

    def test_to_dict(self):
        """Test AlertResult serialization."""
        now = datetime.now(UTC)
        result = AlertResult(
            alert_sent=True,
            severity="warning",
            budget=50.0,
            projected_cost=42.0,
            percentage_used=84.0,
            message="Alert sent",
            timestamp=now,
        )

        data = result.to_dict()

        assert data["alert_sent"] is True
        assert data["severity"] == "warning"
        assert data["budget"] == 50.0
        assert data["projected_cost"] == 42.0
        assert data["percentage_used"] == 84.0
        assert data["message"] == "Alert sent"
        assert "timestamp" in data
