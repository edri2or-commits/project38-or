"""Tests for secrets autonomy modules.

Tests cover:
- WIF health monitoring (secrets_health.py)
- Token rotation interlock (token_rotation.py)
- Credential lifecycle auto-refresh
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.secrets_health import (
    HealthStatus,
    SecretAccessMetrics,
    WIFHealthMonitor,
    get_wif_monitor,
)
from src.token_rotation import (
    RotationResult,
    RotationState,
    TokenRotationInterlock,
    get_rotation_interlock,
)

# =============================================================================
# SecretAccessMetrics Tests
# =============================================================================


class TestSecretAccessMetrics:
    """Tests for SecretAccessMetrics dataclass."""

    def test_initial_values(self):
        """Test default metric values."""
        metrics = SecretAccessMetrics()
        assert metrics.total_attempts == 0
        assert metrics.successful_attempts == 0
        assert metrics.failed_attempts == 0
        assert metrics.consecutive_failures == 0

    def test_success_rate_empty(self):
        """Test success rate with no attempts."""
        metrics = SecretAccessMetrics()
        assert metrics.success_rate == 100.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = SecretAccessMetrics(
            total_attempts=10,
            successful_attempts=8,
            failed_attempts=2,
        )
        assert metrics.success_rate == 80.0

    def test_status_healthy(self):
        """Test healthy status determination."""
        metrics = SecretAccessMetrics(
            total_attempts=100,
            successful_attempts=95,
            failed_attempts=5,
            consecutive_failures=0,
        )
        assert metrics.status == HealthStatus.HEALTHY

    def test_status_degraded_consecutive(self):
        """Test degraded status from consecutive failures."""
        metrics = SecretAccessMetrics(
            total_attempts=10,
            successful_attempts=9,
            failed_attempts=1,
            consecutive_failures=1,
        )
        assert metrics.status == HealthStatus.DEGRADED

    def test_status_degraded_rate(self):
        """Test degraded status from low success rate."""
        metrics = SecretAccessMetrics(
            total_attempts=100,
            successful_attempts=85,
            failed_attempts=15,
            consecutive_failures=0,
        )
        assert metrics.status == HealthStatus.DEGRADED

    def test_status_unhealthy(self):
        """Test unhealthy status from many consecutive failures."""
        metrics = SecretAccessMetrics(
            consecutive_failures=3,
        )
        assert metrics.status == HealthStatus.UNHEALTHY


# =============================================================================
# WIFHealthMonitor Tests
# =============================================================================


class TestWIFHealthMonitor:
    """Tests for WIFHealthMonitor class."""

    def test_record_success(self):
        """Test recording successful secret access."""
        monitor = WIFHealthMonitor()
        monitor.record_success("test-secret")

        assert monitor.metrics.total_attempts == 1
        assert monitor.metrics.successful_attempts == 1
        assert monitor.metrics.consecutive_failures == 0
        assert monitor.metrics.last_success_time is not None

    def test_record_failure(self):
        """Test recording failed secret access."""
        monitor = WIFHealthMonitor()
        monitor.record_failure("test-secret", "PermissionDenied")

        assert monitor.metrics.total_attempts == 1
        assert monitor.metrics.failed_attempts == 1
        assert monitor.metrics.consecutive_failures == 1
        assert monitor.metrics.last_failure_reason == "PermissionDenied"

    def test_consecutive_failures_reset(self):
        """Test that success resets consecutive failures."""
        monitor = WIFHealthMonitor()
        monitor.record_failure("test-secret", "Error1")
        monitor.record_failure("test-secret", "Error2")
        assert monitor.metrics.consecutive_failures == 2

        monitor.record_success("test-secret")
        assert monitor.metrics.consecutive_failures == 0

    def test_get_health_report(self):
        """Test health report generation."""
        monitor = WIFHealthMonitor()
        monitor.record_success("test")
        monitor.record_failure("test", "TestError")

        report = monitor.get_health_report()

        assert "status" in report
        assert "metrics" in report
        assert "alerting" in report
        assert report["metrics"]["total_attempts"] == 2

    @pytest.mark.asyncio
    async def test_check_wif_health_success(self):
        """Test WIF health check with successful GCP access."""
        monitor = WIFHealthMonitor()

        with patch("src.secrets_health.SecretManager") as mock_manager:
            mock_instance = MagicMock()
            mock_instance.list_secrets.return_value = ["secret1", "secret2"]
            mock_manager.return_value = mock_instance

            result = await monitor.check_wif_health()

            assert result["wif_status"] == "healthy"
            assert result["secrets_accessible"] is True
            assert result["secrets_count"] == 2

    @pytest.mark.asyncio
    async def test_check_wif_health_failure(self):
        """Test WIF health check with GCP access failure."""
        monitor = WIFHealthMonitor()

        with patch("src.secrets_health.SecretManager") as mock_manager:
            mock_manager.side_effect = Exception("Auth failed")

            result = await monitor.check_wif_health()

            assert result["wif_status"] == "unhealthy"
            assert result["secrets_accessible"] is False

    def test_global_monitor_singleton(self):
        """Test that get_wif_monitor returns singleton."""
        monitor1 = get_wif_monitor()
        monitor2 = get_wif_monitor()
        assert monitor1 is monitor2


# =============================================================================
# TokenRotationInterlock Tests
# =============================================================================


class TestTokenRotationInterlock:
    """Tests for TokenRotationInterlock class."""

    def test_initial_state(self):
        """Test initial interlock state."""
        interlock = TokenRotationInterlock()
        assert interlock._rotation_in_progress == {}
        assert interlock._rotation_history == []

    @pytest.mark.asyncio
    async def test_rotate_token_not_found(self):
        """Test rotation when secret doesn't exist."""
        interlock = TokenRotationInterlock()

        with patch.object(interlock, "_get_current_version", return_value=None):
            result = await interlock.rotate_token("test-secret", "new-value")

            assert result.success is False
            assert result.state == RotationState.VALIDATING_OLD
            assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_rotate_token_success(self):
        """Test successful token rotation."""
        interlock = TokenRotationInterlock()

        with (
            patch.object(interlock, "_get_current_version", return_value="1"),
            patch.object(interlock, "_get_secret_value", return_value="old-value"),
            patch.object(interlock, "_add_secret_version", return_value="2"),
        ):
            result = await interlock.rotate_token("test-secret", "new-value")

            assert result.success is True
            assert result.old_version == "1"
            assert result.new_version == "2"
            assert result.state == RotationState.COMPLETED

    @pytest.mark.asyncio
    async def test_rotate_token_with_validator_success(self):
        """Test rotation with successful validation."""
        interlock = TokenRotationInterlock()

        def validator(token: str) -> bool:
            return token == "new-value"

        with (
            patch.object(interlock, "_get_current_version", return_value="1"),
            patch.object(interlock, "_get_secret_value", return_value="old-value"),
            patch.object(interlock, "_add_secret_version", return_value="2"),
        ):
            result = await interlock.rotate_token("test-secret", "new-value", validator)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_rotate_token_with_validator_failure_rollback(self):
        """Test rotation rollback when validation fails."""
        interlock = TokenRotationInterlock()

        def validator(token: str) -> bool:
            return False  # Validation fails

        with (
            patch.object(interlock, "_get_current_version", return_value="1"),
            patch.object(interlock, "_get_secret_value", return_value="old-value"),
            patch.object(interlock, "_add_secret_version", return_value="2"),
            patch.object(interlock, "_disable_version") as mock_disable,
        ):
            result = await interlock.rotate_token("test-secret", "new-value", validator)

            assert result.success is False
            assert result.state == RotationState.ROLLBACK
            mock_disable.assert_called_once_with("test-secret", "2")

    @pytest.mark.asyncio
    async def test_rotation_concurrent_prevention(self):
        """Test that concurrent rotations are prevented."""
        interlock = TokenRotationInterlock()
        interlock._rotation_in_progress["test-secret"] = True

        result = await interlock.rotate_token("test-secret", "new-value")

        assert result.success is False
        assert "already in progress" in result.error

    def test_get_rotation_history(self):
        """Test rotation history retrieval."""
        interlock = TokenRotationInterlock()
        interlock._rotation_history = [
            RotationResult(
                success=True,
                secret_name="secret1",
                old_version="1",
                new_version="2",
                state=RotationState.COMPLETED,
            ),
            RotationResult(
                success=False,
                secret_name="secret2",
                old_version="1",
                new_version=None,
                state=RotationState.FAILED,
                error="Test error",
            ),
        ]

        all_history = interlock.get_rotation_history()
        assert len(all_history) == 2

        filtered = interlock.get_rotation_history("secret1")
        assert len(filtered) == 1
        assert filtered[0]["secret_name"] == "secret1"

    def test_global_interlock_singleton(self):
        """Test that get_rotation_interlock returns singleton."""
        interlock1 = get_rotation_interlock()
        interlock2 = get_rotation_interlock()
        assert interlock1 is interlock2


# =============================================================================
# RotationResult Tests
# =============================================================================


class TestRotationResult:
    """Tests for RotationResult dataclass."""

    def test_auto_timestamp(self):
        """Test that timestamp is auto-generated."""
        result = RotationResult(
            success=True,
            secret_name="test",
            old_version="1",
            new_version="2",
            state=RotationState.COMPLETED,
        )
        assert result.timestamp != ""
        # Should be a valid ISO format
        datetime.fromisoformat(result.timestamp)

    def test_custom_timestamp(self):
        """Test custom timestamp is preserved."""
        custom_ts = "2026-01-15T12:00:00"
        result = RotationResult(
            success=True,
            secret_name="test",
            old_version="1",
            new_version="2",
            state=RotationState.COMPLETED,
            timestamp=custom_ts,
        )
        assert result.timestamp == custom_ts


# =============================================================================
# CredentialLifecycleManager Auto-Refresh Tests
# =============================================================================


class TestCredentialLifecycleAutoRefresh:
    """Tests for CredentialLifecycleManager auto-refresh functionality."""

    @pytest.mark.asyncio
    async def test_start_auto_refresh(self):
        """Test starting auto-refresh."""
        from src.credential_lifecycle import CredentialLifecycleManager

        manager = CredentialLifecycleManager()

        # Start with very short interval for testing
        await manager.start_auto_refresh(interval_seconds=1)
        assert manager._auto_refresh_running is True
        assert manager._auto_refresh_task is not None

        # Stop it
        await manager.stop_auto_refresh()
        assert manager._auto_refresh_running is False
        await manager.close()

    @pytest.mark.asyncio
    async def test_stop_auto_refresh(self):
        """Test stopping auto-refresh."""
        from src.credential_lifecycle import CredentialLifecycleManager

        manager = CredentialLifecycleManager()
        await manager.start_auto_refresh(interval_seconds=60)
        await manager.stop_auto_refresh()

        assert manager._auto_refresh_running is False
        assert manager._auto_refresh_task is None
        await manager.close()

    @pytest.mark.asyncio
    async def test_double_start_warning(self):
        """Test that double start is handled gracefully."""
        from src.credential_lifecycle import CredentialLifecycleManager

        manager = CredentialLifecycleManager()
        await manager.start_auto_refresh(interval_seconds=60)
        await manager.start_auto_refresh(interval_seconds=30)  # Should warn

        # Should still be running with original interval
        assert manager._auto_refresh_running is True

        await manager.stop_auto_refresh()
        await manager.close()
