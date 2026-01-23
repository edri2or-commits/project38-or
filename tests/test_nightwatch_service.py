"""Tests for NightWatch Service module.

Tests the autonomous overnight operations service in src/nightwatch/service.py.
Covers:
- NightWatchService class
- Configuration loading
- Health checks, metrics collection, anomaly detection
- Morning summary generation and delivery
- Singleton pattern
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the activity_log module before importing service
_mock_activity_log = MagicMock()
_mock_activity_log.ActivityType = MagicMock()
_mock_activity_log.ActivityType.SYSTEM_START = MagicMock(value="system_start")
_mock_activity_log.ActivityType.HEALTH_CHECK = MagicMock(value="health_check")
_mock_activity_log.ActivityType.METRIC_COLLECTION = MagicMock(value="metric_collection")
_mock_activity_log.ActivityType.ANOMALY_DETECTED = MagicMock(value="anomaly_detected")
_mock_activity_log.ActivityType.SELF_HEALING = MagicMock(value="self_healing")
_mock_activity_log.ActivityType.ALERT_SENT = MagicMock(value="alert_sent")
_mock_activity_log.ActivityType.ERROR = MagicMock(value="error")

_mock_activity_log.ActivitySeverity = MagicMock()
_mock_activity_log.ActivitySeverity.INFO = MagicMock(value="info")
_mock_activity_log.ActivitySeverity.WARNING = MagicMock(value="warning")
_mock_activity_log.ActivitySeverity.ERROR = MagicMock(value="error")
_mock_activity_log.ActivitySeverity.CRITICAL = MagicMock(value="critical")

_mock_activity_log.NightWatchConfig = MagicMock


# Create a proper NightWatchSummary class for testing
class MockNightWatchSummary:
    """Mock NightWatchSummary that returns proper values."""

    def __init__(self, **kwargs):
        self.period_start = kwargs.get("period_start")
        self.period_end = kwargs.get("period_end")
        self.total_activities = kwargs.get("total_activities", 0)
        self.health_checks_passed = 0
        self.health_checks_failed = 0
        self.anomalies_detected = 0
        self.self_healing_actions = 0
        self.alerts_sent = 0
        self.critical_events = []
        self.services_affected = []
        self.overall_status = "healthy"


_mock_activity_log.NightWatchSummary = MockNightWatchSummary


# Create ActivityLog mock with created_at that supports comparison operators
class MockColumn:
    """Mock column that supports comparison operators for SQLAlchemy."""

    def __ge__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()


_mock_activity_log_class = MagicMock()
_mock_activity_log_class.created_at = MockColumn()
_mock_activity_log.ActivityLog = _mock_activity_log_class

sys.modules["src.models.activity_log"] = _mock_activity_log


class TestNightWatchServiceInit:
    """Tests for NightWatchService initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        from src.nightwatch.service import NightWatchService

        with patch.dict(
            "os.environ",
            {
                "NIGHTWATCH_ENABLED": "true",
                "NIGHTWATCH_START_HOUR": "0",
                "NIGHTWATCH_END_HOUR": "6",
            },
            clear=False,
        ):
            service = NightWatchService()

            assert service.telegram_url is not None
            assert service.monitoring_url is not None
            assert service._http_client is None

    def test_init_with_custom_urls(self):
        """Test initialization with custom URLs."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService(
            telegram_url="https://custom-telegram.test",
            monitoring_url="https://custom-monitoring.test",
        )

        assert service.telegram_url == "https://custom-telegram.test"
        assert service.monitoring_url == "https://custom-monitoring.test"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.enabled = True
        mock_config.night_start_hour = 22
        mock_config.night_end_hour = 5

        service = NightWatchService(config=mock_config)

        assert service.config == mock_config


class TestLoadConfigFromEnv:
    """Tests for _load_config_from_env method."""

    def test_load_default_config(self):
        """Test loading default config from environment."""
        from src.nightwatch.service import NightWatchService

        with patch.dict(
            "os.environ",
            {
                "NIGHTWATCH_ENABLED": "true",
                "NIGHTWATCH_START_HOUR": "0",
                "NIGHTWATCH_END_HOUR": "6",
                "NIGHTWATCH_HEALTH_INTERVAL": "60",
                "NIGHTWATCH_CHAT_ID": "0",
                "NIGHTWATCH_SELF_HEALING": "true",
                "NIGHTWATCH_MAX_HEALING": "3",
            },
            clear=False,
        ):
            service = NightWatchService()
            # Config is loaded in __init__
            assert service.config is not None

    def test_load_disabled_config(self):
        """Test loading config with Night Watch disabled."""
        from src.nightwatch.service import NightWatchService

        with patch.dict(
            "os.environ",
            {"NIGHTWATCH_ENABLED": "false"},
            clear=False,
        ):
            service = NightWatchService()
            # Mock config creation
            assert service.config is not None


class TestHttpClient:
    """Tests for HTTP client management."""

    @pytest.mark.asyncio
    async def test_get_http_client_creates_client(self):
        """Test that _get_http_client creates a client on first call."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        assert service._http_client is None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await service._get_http_client()

            mock_client_class.assert_called_once_with(timeout=30.0)
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_http_client_reuses_client(self):
        """Test that _get_http_client reuses existing client."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_client = AsyncMock()
        service._http_client = mock_client

        client = await service._get_http_client()

        assert client == mock_client

    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        """Test that close() closes the HTTP client."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_client = AsyncMock()
        service._http_client = mock_client

        await service.close()

        mock_client.aclose.assert_called_once()
        assert service._http_client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        """Test that close() is safe when no client exists."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        assert service._http_client is None

        await service.close()  # Should not raise

        assert service._http_client is None


class TestIsNightHours:
    """Tests for is_night_hours method."""

    def test_is_night_hours_during_night(self):
        """Test is_night_hours returns True during night hours."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)

        with patch("src.nightwatch.service.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 3  # 3 AM
            mock_datetime.now.return_value = mock_now

            result = service.is_night_hours()

            assert result is True

    def test_is_night_hours_during_day(self):
        """Test is_night_hours returns False during day hours."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)

        with patch("src.nightwatch.service.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 14  # 2 PM
            mock_datetime.now.return_value = mock_now

            result = service.is_night_hours()

            assert result is False

    def test_is_night_hours_at_boundary_start(self):
        """Test is_night_hours at start boundary (inclusive)."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)

        with patch("src.nightwatch.service.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 0  # Midnight
            mock_datetime.now.return_value = mock_now

            result = service.is_night_hours()

            assert result is True

    def test_is_night_hours_at_boundary_end(self):
        """Test is_night_hours at end boundary (exclusive)."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)

        with patch("src.nightwatch.service.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 6  # 6 AM is not night
            mock_datetime.now.return_value = mock_now

            result = service.is_night_hours()

            assert result is False


class TestTick:
    """Tests for tick method."""

    @pytest.mark.asyncio
    async def test_tick_when_disabled(self):
        """Test tick returns early when Night Watch is disabled."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.enabled = False

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        result = await service.tick(mock_session)

        assert result["status"] == "disabled"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_tick_performs_health_check(self):
        """Test tick performs health check."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.enabled = True
        mock_config.enable_self_healing = False

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(
                service,
                "_perform_health_check",
                new_callable=AsyncMock,
                return_value={"type": "health_check", "healthy": True},
            ) as mock_health:
                with patch.object(
                    service,
                    "_collect_metrics",
                    new_callable=AsyncMock,
                    return_value={"type": "metric_collection", "success": True},
                ):
                    with patch.object(
                        service,
                        "_check_anomalies",
                        new_callable=AsyncMock,
                        return_value={"type": "anomaly_check", "anomalies_found": 0},
                    ):
                        result = await service.tick(mock_session)

                        assert result["status"] == "success"
                        mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_triggers_self_healing(self):
        """Test tick triggers self-healing when anomalies detected."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.enabled = True
        mock_config.enable_self_healing = True

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(
                service,
                "_perform_health_check",
                new_callable=AsyncMock,
                return_value={"type": "health_check", "healthy": True},
            ):
                with patch.object(
                    service,
                    "_collect_metrics",
                    new_callable=AsyncMock,
                    return_value={"type": "metric_collection", "success": True},
                ):
                    with patch.object(
                        service,
                        "_check_anomalies",
                        new_callable=AsyncMock,
                        return_value={"type": "anomaly_check", "anomalies_found": 2},
                    ):
                        with patch.object(
                            service,
                            "_attempt_self_healing",
                            new_callable=AsyncMock,
                            return_value={"type": "self_healing", "attempted": True},
                        ) as mock_healing:
                            result = await service.tick(mock_session)

                            assert result["status"] == "success"
                            mock_healing.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_handles_exception(self):
        """Test tick handles exceptions gracefully."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.enabled = True

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(
                service,
                "_perform_health_check",
                new_callable=AsyncMock,
                side_effect=Exception("Test error"),
            ):
                result = await service.tick(mock_session)

                assert result["status"] == "error"
                assert "Test error" in result["error"]


class TestPerformHealthCheck:
    """Tests for _perform_health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "database": "connected"}

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await service._perform_health_check(mock_session)

                assert result["type"] == "health_check"
                assert result["healthy"] is True
                assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test failed health check."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await service._perform_health_check(mock_session)

                assert result["type"] == "health_check"
                assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health check handles exceptions."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.side_effect = Exception("Connection failed")
                mock_get_client.return_value = mock_client

                result = await service._perform_health_check(mock_session)

                assert result["type"] == "health_check"
                assert result["healthy"] is False
                assert "Connection failed" in result["error"]


class TestCollectMetrics:
    """Tests for _collect_metrics method."""

    @pytest.mark.asyncio
    async def test_collect_metrics_success(self):
        """Test successful metric collection."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"count": 5}

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await service._collect_metrics(mock_session)

                assert result["type"] == "metric_collection"
                assert result["success"] is True
                assert result["metrics_count"] == 5

    @pytest.mark.asyncio
    async def test_collect_metrics_failure(self):
        """Test failed metric collection."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await service._collect_metrics(mock_session)

                assert result["type"] == "metric_collection"
                assert result["success"] is False

    @pytest.mark.asyncio
    async def test_collect_metrics_exception(self):
        """Test metric collection handles exceptions."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.post.side_effect = Exception("Timeout")
                mock_get_client.return_value = mock_client

                result = await service._collect_metrics(mock_session)

                assert result["type"] == "metric_collection"
                assert result["success"] is False
                assert "Timeout" in result["error"]


class TestCheckAnomalies:
    """Tests for _check_anomalies method."""

    @pytest.mark.asyncio
    async def test_check_anomalies_none_found(self):
        """Test anomaly check with no anomalies."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "anomalies_detected": 0,
            "state": "running",
        }

        with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await service._check_anomalies(mock_session)

            assert result["type"] == "anomaly_check"
            assert result["success"] is True
            assert result["anomalies_found"] == 0

    @pytest.mark.asyncio
    async def test_check_anomalies_found(self):
        """Test anomaly check with anomalies detected."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "anomalies_detected": 3,
            "state": "running",
        }

        with patch.object(service, "_log_activity", new_callable=AsyncMock):
            with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await service._check_anomalies(mock_session)

                assert result["type"] == "anomaly_check"
                assert result["anomalies_found"] == 3

    @pytest.mark.asyncio
    async def test_check_anomalies_api_failure(self):
        """Test anomaly check handles API failure."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await service._check_anomalies(mock_session)

            assert result["type"] == "anomaly_check"
            assert result["success"] is False
            assert result["anomalies_found"] == 0

    @pytest.mark.asyncio
    async def test_check_anomalies_exception(self):
        """Test anomaly check handles exceptions."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_get_client.return_value = mock_client

            result = await service._check_anomalies(mock_session)

            assert result["type"] == "anomaly_check"
            assert result["success"] is False
            assert "Network error" in result["error"]


class TestAttemptSelfHealing:
    """Tests for _attempt_self_healing method."""

    @pytest.mark.asyncio
    async def test_attempt_self_healing(self):
        """Test self-healing attempt logs activity."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()
        anomaly_result = {"anomalies_found": 2}

        with patch.object(service, "_log_activity", new_callable=AsyncMock) as mock_log:
            result = await service._attempt_self_healing(mock_session, anomaly_result)

            assert result["type"] == "self_healing"
            assert result["attempted"] is True
            assert result["anomalies_addressed"] == 2
            mock_log.assert_called_once()


class TestLogActivity:
    """Tests for _log_activity method."""

    @pytest.mark.asyncio
    async def test_log_activity_creates_record(self):
        """Test that _log_activity creates an ActivityLog record."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()
        mock_session = AsyncMock()

        # Import mocked types
        from src.models.activity_log import ActivitySeverity, ActivityType

        await service._log_activity(
            mock_session,
            ActivityType.HEALTH_CHECK,
            ActivitySeverity.INFO,
            description="Test activity",
            service_name="test-service",
            success=True,
            duration_ms=100,
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


class TestGenerateMorningSummary:
    """Tests for generate_morning_summary method."""

    @pytest.mark.asyncio
    async def test_generate_summary_empty_activities(self):
        """Test summary generation with no activities."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        # Mock the query result - select is imported inside the function
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        with patch("sqlalchemy.select") as mock_select:
            mock_select.return_value = MagicMock()
            summary = await service.generate_morning_summary(mock_session)

            # Summary is a mock object
            assert summary is not None

    @pytest.mark.asyncio
    async def test_generate_summary_with_activities(self):
        """Test summary generation with activities."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        # Create mock activities
        mock_activity1 = MagicMock()
        mock_activity1.activity_type = "health_check"
        mock_activity1.success = True
        mock_activity1.severity = "info"
        mock_activity1.service_name = "main-api"
        mock_activity1.description = "Health check passed"

        mock_activity2 = MagicMock()
        mock_activity2.activity_type = "anomaly_detected"
        mock_activity2.success = True
        mock_activity2.severity = "warning"
        mock_activity2.service_name = None
        mock_activity2.description = "Anomaly detected"

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_activity1, mock_activity2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        with patch("sqlalchemy.select") as mock_select:
            mock_select.return_value = MagicMock()
            summary = await service.generate_morning_summary(mock_session)

            assert summary is not None


class TestSendMorningSummary:
    """Tests for send_morning_summary method."""

    @pytest.mark.asyncio
    async def test_send_summary_no_chat_id(self):
        """Test send_morning_summary skips if no chat_id configured."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.telegram_chat_id = None

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        result = await service.send_morning_summary(mock_session)

        assert result["status"] == "skipped"
        assert "No Telegram chat_id" in result["reason"]

    @pytest.mark.asyncio
    async def test_send_summary_via_direct_telegram_api(self):
        """Test sending summary via direct Telegram API."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.telegram_chat_id = 12345
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)
        service.telegram_token = "test-token"
        mock_session = AsyncMock()

        # Mock summary generation
        mock_summary = MagicMock()
        mock_summary.total_activities = 10
        mock_summary.health_checks_passed = 5
        mock_summary.health_checks_failed = 0
        mock_summary.overall_status = "healthy"

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        with patch.object(
            service,
            "generate_morning_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ):
            with patch.object(service, "_format_summary_message", return_value="Test message"):
                with patch.object(service, "_log_activity", new_callable=AsyncMock):
                    with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                        mock_client = AsyncMock()
                        mock_client.post.return_value = mock_response
                        mock_get_client.return_value = mock_client

                        result = await service.send_morning_summary(mock_session)

                        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_summary_via_railway_service(self):
        """Test sending summary via Railway telegram-bot service."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.telegram_chat_id = 12345
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)
        service.telegram_token = None  # No direct token
        mock_session = AsyncMock()

        mock_summary = MagicMock()
        mock_summary.total_activities = 10
        mock_summary.health_checks_passed = 5
        mock_summary.health_checks_failed = 0
        mock_summary.overall_status = "healthy"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            service,
            "generate_morning_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ):
            with patch.object(service, "_format_summary_message", return_value="Test message"):
                with patch.object(service, "_log_activity", new_callable=AsyncMock):
                    with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                        mock_client = AsyncMock()
                        mock_client.post.return_value = mock_response
                        mock_get_client.return_value = mock_client

                        result = await service.send_morning_summary(mock_session)

                        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_summary_telegram_error(self):
        """Test handling Telegram API error."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.telegram_chat_id = 12345
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)
        service.telegram_token = "test-token"
        mock_session = AsyncMock()

        mock_summary = MagicMock()
        mock_summary.total_activities = 10
        mock_summary.health_checks_passed = 5
        mock_summary.health_checks_failed = 0
        mock_summary.overall_status = "healthy"

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bad request"}

        with patch.object(
            service,
            "generate_morning_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ):
            with patch.object(service, "_format_summary_message", return_value="Test message"):
                with patch.object(service, "_log_activity", new_callable=AsyncMock):
                    with patch.object(service, "_get_http_client", new_callable=AsyncMock) as mock_get_client:
                        mock_client = AsyncMock()
                        mock_client.post.return_value = mock_response
                        mock_get_client.return_value = mock_client

                        result = await service.send_morning_summary(mock_session)

                        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_send_summary_exception(self):
        """Test handling exception during send."""
        from src.nightwatch.service import NightWatchService

        mock_config = MagicMock()
        mock_config.telegram_chat_id = 12345
        mock_config.night_start_hour = 0
        mock_config.night_end_hour = 6

        service = NightWatchService(config=mock_config)
        mock_session = AsyncMock()

        with patch.object(
            service,
            "generate_morning_summary",
            new_callable=AsyncMock,
            side_effect=Exception("Database error"),
        ):
            result = await service.send_morning_summary(mock_session)

            assert result["status"] == "error"
            assert "Database error" in result["error"]


class TestFormatSummaryMessage:
    """Tests for _format_summary_message method."""

    def test_format_healthy_summary(self):
        """Test formatting healthy summary."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()

        mock_summary = MagicMock()
        mock_summary.overall_status = "healthy"
        mock_summary.period_start = datetime(2026, 1, 23, 0, 0, tzinfo=UTC)
        mock_summary.period_end = datetime(2026, 1, 23, 6, 0, tzinfo=UTC)
        mock_summary.total_activities = 10
        mock_summary.health_checks_passed = 6
        mock_summary.health_checks_failed = 0
        mock_summary.anomalies_detected = 0
        mock_summary.self_healing_actions = 0
        mock_summary.critical_events = []
        mock_summary.services_affected = []

        result = service._format_summary_message(mock_summary)

        assert "Night Watch Summary" in result
        assert "HEALTHY" in result
        assert "00:00 - 06:00 UTC" in result

    def test_format_degraded_summary(self):
        """Test formatting degraded summary."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()

        mock_summary = MagicMock()
        mock_summary.overall_status = "degraded"
        mock_summary.period_start = datetime(2026, 1, 23, 0, 0, tzinfo=UTC)
        mock_summary.period_end = datetime(2026, 1, 23, 6, 0, tzinfo=UTC)
        mock_summary.total_activities = 10
        mock_summary.health_checks_passed = 4
        mock_summary.health_checks_failed = 2
        mock_summary.anomalies_detected = 1
        mock_summary.self_healing_actions = 1
        mock_summary.critical_events = []
        mock_summary.services_affected = ["main-api"]

        result = service._format_summary_message(mock_summary)

        assert "DEGRADED" in result
        assert "Services Affected" in result

    def test_format_critical_summary(self):
        """Test formatting critical summary with events."""
        from src.nightwatch.service import NightWatchService

        service = NightWatchService()

        mock_summary = MagicMock()
        mock_summary.overall_status = "critical"
        mock_summary.period_start = datetime(2026, 1, 23, 0, 0, tzinfo=UTC)
        mock_summary.period_end = datetime(2026, 1, 23, 6, 0, tzinfo=UTC)
        mock_summary.total_activities = 15
        mock_summary.health_checks_passed = 2
        mock_summary.health_checks_failed = 4
        mock_summary.anomalies_detected = 5
        mock_summary.self_healing_actions = 3
        mock_summary.critical_events = ["Database connection lost", "API timeout"]
        mock_summary.services_affected = ["main-api", "database"]

        result = service._format_summary_message(mock_summary)

        assert "CRITICAL" in result
        assert "Critical Events" in result
        assert "Database connection lost" in result


class TestGetNightWatch:
    """Tests for get_night_watch singleton function."""

    def test_get_night_watch_creates_instance(self):
        """Test get_night_watch creates a new instance."""
        from src.nightwatch import service

        # Reset singleton
        service._night_watch = None

        result = service.get_night_watch()

        assert result is not None
        assert isinstance(result, service.NightWatchService)

    def test_get_night_watch_returns_same_instance(self):
        """Test get_night_watch returns the same instance."""
        from src.nightwatch import service

        # Reset singleton
        service._night_watch = None

        instance1 = service.get_night_watch()
        instance2 = service.get_night_watch()

        assert instance1 is instance2
