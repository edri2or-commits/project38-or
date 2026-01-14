"""Tests for Alert Manager Module.

Tests cover:
- Maintenance window management
- Alert suppression logic
- Rate limiting
- Alert sending
- Runbook integration
- Performance alert integration
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.alert_manager import Alert, AlertManager, AlertResult, MaintenanceWindow

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def n8n_webhook_url():
    """Mock n8n webhook URL."""
    return "https://n8n.example.com/webhook/alerts"


@pytest.fixture
def telegram_chat_id():
    """Mock Telegram chat ID."""
    return "123456789"


@pytest.fixture
def alert_manager(n8n_webhook_url, telegram_chat_id):
    """Alert manager instance."""
    return AlertManager(
        n8n_webhook_url=n8n_webhook_url,
        telegram_chat_id=telegram_chat_id,
    )


@pytest.fixture
def mock_alert():
    """Mock alert."""
    return Alert(
        alert_id="test-alert-123",
        severity="warning",
        title="Test Alert",
        message="This is a test alert",
        runbook_url="https://docs.example.com/runbook",
        tags=["test", "performance"],
        metadata={"metric": "latency_ms", "value": 500.0},
    )


# =============================================================================
# MAINTENANCE WINDOW TESTS
# =============================================================================


def test_maintenance_window_creation():
    """Test MaintenanceWindow creation."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now,
        end=now + timedelta(hours=2),
        reason="Database migration",
        suppress_all=True,
        created_by="admin",
        tags=["database", "migration"],
    )

    assert window.reason == "Database migration"
    assert window.suppress_all is True
    assert window.created_by == "admin"
    assert "database" in window.tags


def test_maintenance_window_is_active():
    """Test maintenance window active check."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Maintenance",
    )

    assert window.is_active() is True
    assert window.is_active(now) is True
    assert window.is_active(now - timedelta(hours=2)) is False
    assert window.is_active(now + timedelta(hours=2)) is False


def test_maintenance_window_to_dict():
    """Test MaintenanceWindow serialization."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now,
        end=now + timedelta(hours=2),
        reason="Planned maintenance",
        tags=["system"],
    )

    data = window.to_dict()
    assert data["reason"] == "Planned maintenance"
    assert "start" in data
    assert "end" in data
    assert data["tags"] == ["system"]


# =============================================================================
# ALERT TESTS
# =============================================================================


def test_alert_creation(mock_alert):
    """Test Alert creation."""
    assert mock_alert.alert_id == "test-alert-123"
    assert mock_alert.severity == "warning"
    assert mock_alert.title == "Test Alert"
    assert mock_alert.runbook_url == "https://docs.example.com/runbook"
    assert "test" in mock_alert.tags


def test_alert_dedupe_key_default():
    """Test Alert dedupe_key defaults to title."""
    alert = Alert(
        alert_id="test-123",
        severity="info",
        title="Test Title",
        message="Test message",
    )

    assert alert.dedupe_key == "Test Title"


def test_alert_dedupe_key_custom():
    """Test Alert with custom dedupe_key."""
    alert = Alert(
        alert_id="test-123",
        severity="info",
        title="Test Title",
        message="Test message",
        dedupe_key="custom_key",
    )

    assert alert.dedupe_key == "custom_key"


def test_alert_to_dict(mock_alert):
    """Test Alert serialization."""
    data = mock_alert.to_dict()

    assert data["alert_id"] == "test-alert-123"
    assert data["severity"] == "warning"
    assert data["title"] == "Test Alert"
    assert "runbook_url" in data
    assert "timestamp" in data


# =============================================================================
# ALERT RESULT TESTS
# =============================================================================


def test_alert_result_success():
    """Test AlertResult for successful send."""
    now = datetime.now(UTC)
    result = AlertResult(
        success=True,
        alert_id="alert-123",
        sent_at=now,
    )

    assert result.success is True
    assert result.suppressed is False
    assert result.rate_limited is False
    assert result.sent_at == now


def test_alert_result_suppressed():
    """Test AlertResult for suppressed alert."""
    result = AlertResult(
        success=False,
        alert_id="alert-123",
        suppressed=True,
        suppression_reason="Maintenance window",
    )

    assert result.success is False
    assert result.suppressed is True
    assert result.suppression_reason == "Maintenance window"


def test_alert_result_rate_limited():
    """Test AlertResult for rate limited alert."""
    result = AlertResult(
        success=False,
        alert_id="alert-123",
        rate_limited=True,
    )

    assert result.success is False
    assert result.rate_limited is True


def test_alert_result_to_dict():
    """Test AlertResult serialization."""
    result = AlertResult(
        success=True,
        alert_id="alert-123",
        sent_at=datetime.now(UTC),
    )

    data = result.to_dict()
    assert data["success"] is True
    assert data["alert_id"] == "alert-123"
    assert "sent_at" in data


# =============================================================================
# ALERT MANAGER INITIALIZATION TESTS
# =============================================================================


def test_alert_manager_init(alert_manager, n8n_webhook_url, telegram_chat_id):
    """Test AlertManager initialization."""
    assert alert_manager.n8n_webhook_url == n8n_webhook_url
    assert alert_manager.telegram_chat_id == telegram_chat_id
    assert alert_manager.rate_limit_minutes["critical"] == 15
    assert alert_manager.rate_limit_minutes["warning"] == 60
    assert alert_manager.rate_limit_minutes["info"] == 1440


def test_alert_manager_custom_rate_limits():
    """Test AlertManager with custom rate limits."""
    custom_limits = {
        "critical": 10,
        "warning": 30,
        "info": 720,
    }

    manager = AlertManager(
        n8n_webhook_url="https://test.com",
        rate_limit_minutes=custom_limits,
    )

    assert manager.rate_limit_minutes["critical"] == 10
    assert manager.rate_limit_minutes["warning"] == 30


# =============================================================================
# MAINTENANCE WINDOW MANAGEMENT TESTS
# =============================================================================


def test_add_maintenance_window(alert_manager):
    """Test adding maintenance window."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now,
        end=now + timedelta(hours=2),
        reason="Database upgrade",
    )

    alert_manager.add_maintenance_window(window)

    assert len(alert_manager.maintenance_windows) == 1
    assert alert_manager.maintenance_windows[0].reason == "Database upgrade"


def test_remove_expired_windows(alert_manager):
    """Test removing expired maintenance windows."""
    now = datetime.now(UTC)

    # Add expired window
    expired_window = MaintenanceWindow(
        start=now - timedelta(hours=3),
        end=now - timedelta(hours=1),
        reason="Past maintenance",
    )

    # Add active window
    active_window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Current maintenance",
    )

    alert_manager.add_maintenance_window(expired_window)
    alert_manager.add_maintenance_window(active_window)

    assert len(alert_manager.maintenance_windows) == 2

    removed = alert_manager.remove_expired_windows()

    assert removed == 1
    assert len(alert_manager.maintenance_windows) == 1
    assert alert_manager.maintenance_windows[0].reason == "Current maintenance"


# =============================================================================
# SUPPRESSION TESTS
# =============================================================================


def test_is_suppressed_no_windows(alert_manager):
    """Test suppression check with no maintenance windows."""
    suppressed, reason = alert_manager.is_suppressed("warning")

    assert suppressed is False
    assert reason is None


def test_is_suppressed_active_window_all(alert_manager):
    """Test suppression with active suppress_all window."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Full maintenance",
        suppress_all=True,
    )

    alert_manager.add_maintenance_window(window)

    # All severities should be suppressed
    for severity in ["info", "warning", "critical"]:
        suppressed, reason = alert_manager.is_suppressed(severity)
        assert suppressed is True
        assert "Full maintenance" in reason


def test_is_suppressed_active_window_info_only(alert_manager):
    """Test suppression with active info-only window."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Partial maintenance",
        suppress_all=False,
    )

    alert_manager.add_maintenance_window(window)

    # Only info should be suppressed
    suppressed, _ = alert_manager.is_suppressed("info")
    assert suppressed is True

    suppressed, _ = alert_manager.is_suppressed("warning")
    assert suppressed is False

    suppressed, _ = alert_manager.is_suppressed("critical")
    assert suppressed is False


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================


def test_should_rate_limit_no_history(alert_manager):
    """Test rate limiting with no alert history."""
    should_limit = alert_manager.should_rate_limit("test_key", "warning")

    assert should_limit is False


def test_should_rate_limit_within_cooldown(alert_manager):
    """Test rate limiting within cooldown period."""
    dedupe_key = "test_key"
    alert_manager._alert_history[dedupe_key] = datetime.now(UTC) - timedelta(minutes=5)

    # Warning cooldown is 60 minutes, so should be rate limited
    should_limit = alert_manager.should_rate_limit(dedupe_key, "warning")

    assert should_limit is True


def test_should_rate_limit_after_cooldown(alert_manager):
    """Test rate limiting after cooldown period."""
    dedupe_key = "test_key"
    alert_manager._alert_history[dedupe_key] = datetime.now(UTC) - timedelta(minutes=65)

    # Warning cooldown is 60 minutes, so should not be rate limited
    should_limit = alert_manager.should_rate_limit(dedupe_key, "warning")

    assert should_limit is False


def test_should_rate_limit_different_severities(alert_manager):
    """Test rate limiting with different severity cooldowns."""
    dedupe_key = "test_key"
    alert_manager._alert_history[dedupe_key] = datetime.now(UTC) - timedelta(minutes=20)

    # Critical cooldown is 15 minutes - should not be rate limited
    assert alert_manager.should_rate_limit(dedupe_key, "critical") is False

    # Warning cooldown is 60 minutes - should be rate limited
    assert alert_manager.should_rate_limit(dedupe_key, "warning") is True


# =============================================================================
# SEND ALERT TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_send_alert_success(alert_manager):
    """Test successful alert sending."""
    with patch.object(alert_manager, "_send_to_n8n", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await alert_manager.send_alert(
            severity="warning",
            title="Test Alert",
            message="This is a test",
            runbook_url="https://docs.example.com/runbook",
        )

        assert result.success is True
        assert result.suppressed is False
        assert result.rate_limited is False
        assert result.sent_at is not None
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_suppressed(alert_manager):
    """Test alert sending during maintenance window."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Maintenance",
        suppress_all=True,
    )
    alert_manager.add_maintenance_window(window)

    result = await alert_manager.send_alert(
        severity="warning",
        title="Test Alert",
        message="This is a test",
    )

    assert result.success is False
    assert result.suppressed is True
    assert "Maintenance" in result.suppression_reason


@pytest.mark.asyncio
async def test_send_alert_rate_limited(alert_manager):
    """Test alert sending with rate limiting."""
    dedupe_key = "test_alert"

    # Send first alert
    with patch.object(alert_manager, "_send_to_n8n", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result1 = await alert_manager.send_alert(
            severity="warning",
            title="Test Alert",
            message="First alert",
            dedupe_key=dedupe_key,
        )

        assert result1.success is True

    # Try to send second alert immediately (should be rate limited)
    result2 = await alert_manager.send_alert(
        severity="warning",
        title="Test Alert",
        message="Second alert",
        dedupe_key=dedupe_key,
    )

    assert result2.success is False
    assert result2.rate_limited is True


@pytest.mark.asyncio
async def test_send_alert_force(alert_manager):
    """Test forced alert sending bypasses suppression and rate limits."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Maintenance",
        suppress_all=True,
    )
    alert_manager.add_maintenance_window(window)

    with patch.object(alert_manager, "_send_to_n8n", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await alert_manager.send_alert(
            severity="warning",
            title="Test Alert",
            message="Forced alert",
            force=True,
        )

        assert result.success is True
        assert result.suppressed is False
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_n8n_failure(alert_manager):
    """Test alert sending when n8n fails."""
    with patch.object(alert_manager, "_send_to_n8n", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = False

        result = await alert_manager.send_alert(
            severity="warning",
            title="Test Alert",
            message="This is a test",
        )

        assert result.success is False
        assert result.error is not None


# =============================================================================
# PERFORMANCE ALERT INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_send_performance_alert(alert_manager):
    """Test sending performance anomaly alert."""
    # Mock anomaly
    class MockAnomaly:
        def __init__(self):
            self.metric_name = "latency_ms"
            self.timestamp = datetime.now(UTC)
            self.current_value = 500.0
            self.expected_value = 150.0
            self.deviation_stddev = 4.5
            self.severity = "warning"
            self.message = "Latency is 4.5σ above baseline"

    anomaly = MockAnomaly()

    # Mock baseline stats
    class MockBaseline:
        def __init__(self):
            self.median = 145.0
            self.p95 = 350.0
            self.p99 = 450.0
            self.stddev = 25.0
            self.sample_count = 100

    baseline_stats = {"latency_ms": MockBaseline()}

    with patch.object(alert_manager, "_send_to_n8n", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await alert_manager.send_performance_alert(anomaly, baseline_stats)

        assert result.success is True
        mock_send.assert_called_once()

        # Check that alert has runbook URL
        call_args = mock_send.call_args[0][0]
        assert call_args.runbook_url is not None
        assert "runbooks" in call_args.runbook_url


# =============================================================================
# STATUS AND UTILITY TESTS
# =============================================================================


def test_get_status(alert_manager):
    """Test getting alert manager status."""
    now = datetime.now(UTC)
    window = MaintenanceWindow(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        reason="Maintenance",
    )
    alert_manager.add_maintenance_window(window)

    status = alert_manager.get_status()

    assert status["n8n_configured"] is True
    assert status["telegram_configured"] is True
    assert status["active_maintenance_windows"] == 1
    assert "rate_limits" in status
    assert "maintenance_windows" in status


def test_clear_history(alert_manager):
    """Test clearing alert history."""
    alert_manager._alert_history["key1"] = datetime.now(UTC)
    alert_manager._alert_history["key2"] = datetime.now(UTC)

    assert len(alert_manager._alert_history) == 2

    alert_manager.clear_history()

    assert len(alert_manager._alert_history) == 0


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


def test_create_alert_manager_success():
    """Test factory function with valid configuration."""
    from src.alert_manager import create_alert_manager

    with patch.dict("os.environ", {"N8N_BASE_URL": "https://n8n.test.com"}):
        manager = create_alert_manager()

        assert manager is not None
        assert "n8n.test.com/webhook/alerts" in manager.n8n_webhook_url


def test_create_alert_manager_no_n8n():
    """Test factory function without n8n configuration."""
    from src.alert_manager import create_alert_manager

    with patch.dict("os.environ", {}, clear=True):
        manager = create_alert_manager()

        # Should still return a manager, but n8n won't work
        assert manager is not None
        assert manager.n8n_webhook_url is None
