"""Tests for secrets health monitoring.

Tests the secrets_health module in src/secrets_health.py.
Covers:
- SecretAccessMetrics calculation and status determination
- WIFHealthMonitor success/failure recording
- Alert cooldown logic
- Health report generation
- Active health check functionality
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the secrets_manager module before any imports that might need it
# This allows patching src.secrets_manager.SecretManager
_mock_secrets_manager = MagicMock()
_mock_secrets_manager.SecretManager = MagicMock
sys.modules["src.secrets_manager"] = _mock_secrets_manager


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Test that HealthStatus has expected values."""
        from src.secrets_health import HealthStatus

        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestSecretAccessMetrics:
    """Tests for SecretAccessMetrics dataclass."""

    def test_default_values(self):
        """Test that metrics initialize with correct defaults."""
        from src.secrets_health import SecretAccessMetrics

        metrics = SecretAccessMetrics()

        assert metrics.total_attempts == 0
        assert metrics.successful_attempts == 0
        assert metrics.failed_attempts == 0
        assert metrics.last_success_time is None
        assert metrics.last_failure_time is None
        assert metrics.last_failure_reason is None
        assert metrics.consecutive_failures == 0

    def test_success_rate_no_attempts(self):
        """Test success rate is 100% with no attempts."""
        from src.secrets_health import SecretAccessMetrics

        metrics = SecretAccessMetrics()

        assert metrics.success_rate == 100.0

    def test_success_rate_all_successful(self):
        """Test success rate is 100% when all attempts succeed."""
        from src.secrets_health import SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=10,
            successful_attempts=10,
            failed_attempts=0,
        )

        assert metrics.success_rate == 100.0

    def test_success_rate_mixed(self):
        """Test success rate calculation with mixed results."""
        from src.secrets_health import SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=10,
            successful_attempts=8,
            failed_attempts=2,
        )

        assert metrics.success_rate == 80.0

    def test_success_rate_all_failed(self):
        """Test success rate is 0% when all attempts fail."""
        from src.secrets_health import SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=5,
            successful_attempts=0,
            failed_attempts=5,
        )

        assert metrics.success_rate == 0.0

    def test_status_healthy(self):
        """Test status is HEALTHY with no failures and high success rate."""
        from src.secrets_health import HealthStatus, SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=100,
            successful_attempts=95,
            failed_attempts=5,
            consecutive_failures=0,
        )

        assert metrics.status == HealthStatus.HEALTHY

    def test_status_degraded_one_consecutive_failure(self):
        """Test status is DEGRADED with one consecutive failure."""
        from src.secrets_health import HealthStatus, SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=100,
            successful_attempts=99,
            failed_attempts=1,
            consecutive_failures=1,
        )

        assert metrics.status == HealthStatus.DEGRADED

    def test_status_degraded_low_success_rate(self):
        """Test status is DEGRADED when success rate < 90%."""
        from src.secrets_health import HealthStatus, SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=100,
            successful_attempts=85,  # 85%
            failed_attempts=15,
            consecutive_failures=0,
        )

        assert metrics.status == HealthStatus.DEGRADED

    def test_status_unhealthy_three_consecutive_failures(self):
        """Test status is UNHEALTHY with 3+ consecutive failures."""
        from src.secrets_health import HealthStatus, SecretAccessMetrics

        metrics = SecretAccessMetrics(
            total_attempts=10,
            successful_attempts=7,
            failed_attempts=3,
            consecutive_failures=3,
        )

        assert metrics.status == HealthStatus.UNHEALTHY


class TestWIFHealthMonitor:
    """Tests for WIFHealthMonitor class."""

    def test_init_default_values(self):
        """Test monitor initializes with correct defaults."""
        from src.secrets_health import WIFHealthMonitor

        with patch.dict("os.environ", {}, clear=True):
            monitor = WIFHealthMonitor()

        assert monitor.metrics.total_attempts == 0
        assert monitor.alert_cooldown_seconds == 300
        assert monitor._last_alert_time == 0

    def test_init_with_webhook_url(self):
        """Test monitor uses N8N_ALERT_WEBHOOK_URL from environment."""
        from src.secrets_health import WIFHealthMonitor

        with patch.dict("os.environ", {"N8N_ALERT_WEBHOOK_URL": "https://n8n.test/webhook"}):
            monitor = WIFHealthMonitor()

        assert monitor.alert_webhook_url == "https://n8n.test/webhook"

    def test_record_success_updates_metrics(self):
        """Test that record_success updates all relevant metrics."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        # Add some failures first
        monitor.metrics.consecutive_failures = 2

        monitor.record_success("test-secret")

        assert monitor.metrics.total_attempts == 1
        assert monitor.metrics.successful_attempts == 1
        assert monitor.metrics.consecutive_failures == 0
        assert monitor.metrics.last_success_time is not None

    def test_record_failure_updates_metrics(self):
        """Test that record_failure updates all relevant metrics."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()

        # Disable alerting for this test
        with patch.object(monitor, "_should_alert", return_value=False):
            monitor.record_failure("test-secret", "Authentication failed")

        assert monitor.metrics.total_attempts == 1
        assert monitor.metrics.failed_attempts == 1
        assert monitor.metrics.consecutive_failures == 1
        assert monitor.metrics.last_failure_time is not None
        assert monitor.metrics.last_failure_reason == "Authentication failed"

    def test_record_failure_increments_consecutive_failures(self):
        """Test that consecutive failures are incremented correctly."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()

        with patch.object(monitor, "_should_alert", return_value=False):
            monitor.record_failure("test-secret", "Error 1")
            monitor.record_failure("test-secret", "Error 2")
            monitor.record_failure("test-secret", "Error 3")

        assert monitor.metrics.consecutive_failures == 3
        assert monitor.metrics.total_attempts == 3

    def test_should_alert_false_below_threshold(self):
        """Test that _should_alert returns False with < 2 consecutive failures."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.metrics.consecutive_failures = 1

        assert monitor._should_alert() is False

    def test_should_alert_true_at_threshold(self):
        """Test that _should_alert returns True with >= 2 consecutive failures."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.metrics.consecutive_failures = 2

        assert monitor._should_alert() is True

    def test_should_alert_respects_cooldown(self):
        """Test that _should_alert respects cooldown period."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.metrics.consecutive_failures = 5
        monitor._last_alert_time = time.time()  # Just alerted

        assert monitor._should_alert() is False

    def test_should_alert_after_cooldown(self):
        """Test that _should_alert returns True after cooldown expires."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.metrics.consecutive_failures = 5
        monitor._last_alert_time = time.time() - 400  # 400 seconds ago (> 300 cooldown)

        assert monitor._should_alert() is True

    def test_get_health_report_structure(self):
        """Test that get_health_report returns correct structure."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.alert_webhook_url = "https://test.webhook"

        report = monitor.get_health_report()

        assert "status" in report
        assert "metrics" in report
        assert "alerting" in report

        # Check metrics structure
        assert "total_attempts" in report["metrics"]
        assert "successful_attempts" in report["metrics"]
        assert "failed_attempts" in report["metrics"]
        assert "success_rate_percent" in report["metrics"]
        assert "consecutive_failures" in report["metrics"]
        assert "last_success" in report["metrics"]
        assert "last_failure" in report["metrics"]
        assert "last_failure_reason" in report["metrics"]

        # Check alerting structure
        assert report["alerting"]["webhook_configured"] is True
        assert report["alerting"]["cooldown_seconds"] == 300

    def test_get_health_report_formats_timestamps(self):
        """Test that timestamps are formatted as ISO strings."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.record_success("test")

        report = monitor.get_health_report()

        # Should be ISO format string
        assert report["metrics"]["last_success"] is not None
        datetime.fromisoformat(report["metrics"]["last_success"])  # Should not raise

    @pytest.mark.asyncio
    async def test_send_alert_no_webhook(self):
        """Test that _send_alert logs when no webhook configured."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.alert_webhook_url = None

        # Should not raise, just log
        await monitor._send_alert("Test reason")

        # Verify last_alert_time was updated
        assert monitor._last_alert_time > 0

    @pytest.mark.asyncio
    async def test_send_alert_with_webhook(self):
        """Test that _send_alert sends POST to webhook."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.alert_webhook_url = "https://n8n.test/webhook"
        monitor.metrics.consecutive_failures = 3

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await monitor._send_alert("WIF auth failed")

        # Verify POST was called with correct payload
        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "https://n8n.test/webhook"

        payload = call_args[1]["json"]
        assert payload["alert_type"] == "wif_failure"
        assert payload["severity"] == "critical"
        assert "WIF auth failed" in payload["message"]
        assert payload["metrics"]["consecutive_failures"] == 3

    @pytest.mark.asyncio
    async def test_send_alert_handles_http_error(self):
        """Test that _send_alert handles HTTP errors gracefully."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.alert_webhook_url = "https://n8n.test/webhook"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Should not raise
            await monitor._send_alert("Test reason")

    @pytest.mark.asyncio
    async def test_check_wif_health_success(self):
        """Test check_wif_health with successful secret access."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()

        mock_manager = MagicMock()
        mock_manager.list_secrets.return_value = ["SECRET1", "SECRET2", "SECRET3"]

        with patch("src.secrets_manager.SecretManager", return_value=mock_manager):
            result = await monitor.check_wif_health()

        assert result["wif_status"] == "healthy"
        assert result["secrets_accessible"] is True
        assert result["secrets_count"] == 3
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_check_wif_health_no_secrets(self):
        """Test check_wif_health when no secrets returned."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()

        mock_manager = MagicMock()
        mock_manager.list_secrets.return_value = []

        with patch("src.secrets_manager.SecretManager", return_value=mock_manager):
            with patch.object(monitor, "_should_alert", return_value=False):
                result = await monitor.check_wif_health()

        assert result["wif_status"] == "degraded"
        assert result["secrets_accessible"] is False
        assert "WIF issue" in result["error"]

    @pytest.mark.asyncio
    async def test_check_wif_health_exception(self):
        """Test check_wif_health when SecretManager raises exception."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()

        with patch("src.secrets_manager.SecretManager") as mock_manager_class:
            mock_manager_class.side_effect = PermissionError("Access denied")

            with patch.object(monitor, "_should_alert", return_value=False):
                result = await monitor.check_wif_health()

        assert result["wif_status"] == "unhealthy"
        assert result["secrets_accessible"] is False
        assert "PermissionError" in result["error"]


class TestGetWifMonitor:
    """Tests for get_wif_monitor singleton function."""

    def test_returns_wif_health_monitor(self):
        """Test that get_wif_monitor returns WIFHealthMonitor instance."""
        from src.secrets_health import WIFHealthMonitor, get_wif_monitor

        # Reset global state
        import src.secrets_health

        src.secrets_health._monitor = None

        monitor = get_wif_monitor()

        assert isinstance(monitor, WIFHealthMonitor)

    def test_returns_same_instance(self):
        """Test that get_wif_monitor returns singleton."""
        from src.secrets_health import get_wif_monitor

        # Reset global state
        import src.secrets_health

        src.secrets_health._monitor = None

        monitor1 = get_wif_monitor()
        monitor2 = get_wif_monitor()

        assert monitor1 is monitor2


class TestIntegration:
    """Integration tests for secrets_health module."""

    def test_failure_to_alert_flow(self):
        """Test complete flow from failures to alert triggering."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()
        monitor.alert_webhook_url = "https://test.webhook"

        # First failure - no alert
        with patch.object(monitor, "_send_alert") as mock_alert:
            mock_alert_task = AsyncMock()
            with patch("asyncio.create_task", return_value=mock_alert_task):
                monitor.record_failure("secret1", "Error 1")

        assert monitor.metrics.consecutive_failures == 1

        # Second failure - should trigger alert
        with patch("asyncio.create_task") as mock_create_task:
            monitor.record_failure("secret2", "Error 2")

        # Alert task should have been created
        mock_create_task.assert_called_once()

    def test_success_resets_consecutive_failures(self):
        """Test that success resets consecutive failure count."""
        from src.secrets_health import WIFHealthMonitor

        monitor = WIFHealthMonitor()

        # Add some failures
        with patch.object(monitor, "_should_alert", return_value=False):
            monitor.record_failure("s1", "e1")
            monitor.record_failure("s2", "e2")

        assert monitor.metrics.consecutive_failures == 2

        # Success should reset
        monitor.record_success("s3")

        assert monitor.metrics.consecutive_failures == 0
        assert monitor.metrics.successful_attempts == 1
