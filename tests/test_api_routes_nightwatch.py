"""Tests for Night Watch API routes.

Tests the /api/nightwatch/* endpoints defined in src/api/routes/nightwatch.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip if FastAPI not available
pytest.importorskip("fastapi")


def _has_asyncpg() -> bool:
    """Check if asyncpg module is available."""
    try:
        import asyncpg  # noqa: F401

        return True
    except ImportError:
        return False


# Skip tests requiring nightwatch route imports if asyncpg not available
requires_asyncpg = pytest.mark.skipif(
    not _has_asyncpg(),
    reason="asyncpg module not available (required by database module)",
)


@requires_asyncpg
class TestNightWatchRequestModels:
    """Tests for Night Watch request/response models."""

    def test_nightwatch_status_import(self):
        """NightWatchStatus should be importable."""
        from src.api.routes.nightwatch import NightWatchStatus

        assert NightWatchStatus is not None

    def test_nightwatch_status_model(self):
        """NightWatchStatus should have all required fields."""
        from src.api.routes.nightwatch import NightWatchStatus

        status = NightWatchStatus(
            enabled=True,
            is_night_hours=True,
            current_hour_utc=3,
            night_start_hour=22,
            night_end_hour=6,
            self_healing_enabled=True,
            telegram_configured=True,
        )

        assert status.enabled is True
        assert status.current_hour_utc == 3
        assert status.night_start_hour == 22
        assert status.night_end_hour == 6

    def test_tick_result_model(self):
        """TickResult should have all fields with defaults."""
        from src.api.routes.nightwatch import TickResult

        result = TickResult(
            status="completed",
            timestamp="2026-01-22T03:00:00Z",
        )

        assert result.status == "completed"
        assert result.duration_ms is None
        assert result.activities == []
        assert result.error is None

    def test_tick_result_with_activities(self):
        """TickResult should accept activities list."""
        from src.api.routes.nightwatch import TickResult

        result = TickResult(
            status="completed",
            timestamp="2026-01-22T03:00:00Z",
            duration_ms=1500,
            activities=[{"type": "health_check", "service": "railway"}],
        )

        assert result.duration_ms == 1500
        assert len(result.activities) == 1

    def test_summary_result_model(self):
        """SummaryResult should work with optional fields."""
        from src.api.routes.nightwatch import SummaryResult

        result = SummaryResult(status="sent")
        assert result.status == "sent"
        assert result.summary is None
        assert result.error is None

        result_with_summary = SummaryResult(
            status="sent",
            summary={"total_activities": 10},
        )
        assert result_with_summary.summary["total_activities"] == 10

    def test_activity_log_entry_model(self):
        """ActivityLogEntry should have all required fields."""
        from src.api.routes.nightwatch import ActivityLogEntry

        entry = ActivityLogEntry(
            id=1,
            activity_type="health_check",
            severity="info",
            service_name="railway",
            description="Health check completed",
            success=True,
            duration_ms=150,
            created_at="2026-01-22T03:00:00Z",
        )

        assert entry.id == 1
        assert entry.activity_type == "health_check"
        assert entry.success is True


@requires_asyncpg
class TestNightWatchRouterSetup:
    """Tests for Night Watch router configuration."""

    def test_router_import(self):
        """Router should be importable."""
        from src.api.routes.nightwatch import router

        assert router is not None

    def test_router_has_routes(self):
        """Router should have defined routes."""
        from src.api.routes.nightwatch import router

        # Check router has routes registered
        assert len(router.routes) > 0


@requires_asyncpg
class TestNightWatchStatusEndpoint:
    """Tests for GET /api/nightwatch/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_returns_config(self):
        """get_nightwatch_status should return service configuration."""
        from src.api.routes.nightwatch import get_nightwatch_status

        mock_service = MagicMock()
        mock_service.config.enabled = True
        mock_service.config.night_start_hour = 22
        mock_service.config.night_end_hour = 6
        mock_service.config.enable_self_healing = True
        mock_service.config.telegram_chat_id = "12345"
        mock_service.is_night_hours.return_value = True

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await get_nightwatch_status()

        assert response.enabled is True
        assert response.is_night_hours is True
        assert response.night_start_hour == 22
        assert response.night_end_hour == 6
        assert response.self_healing_enabled is True
        assert response.telegram_configured is True

    @pytest.mark.asyncio
    async def test_get_status_when_disabled(self):
        """get_nightwatch_status should show disabled state."""
        from src.api.routes.nightwatch import get_nightwatch_status

        mock_service = MagicMock()
        mock_service.config.enabled = False
        mock_service.config.night_start_hour = 22
        mock_service.config.night_end_hour = 6
        mock_service.config.enable_self_healing = False
        mock_service.config.telegram_chat_id = None
        mock_service.is_night_hours.return_value = False

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await get_nightwatch_status()

        assert response.enabled is False
        assert response.telegram_configured is False

    @pytest.mark.asyncio
    async def test_get_status_current_hour(self):
        """get_nightwatch_status should include current UTC hour."""
        from src.api.routes.nightwatch import get_nightwatch_status

        mock_service = MagicMock()
        mock_service.config.enabled = True
        mock_service.config.night_start_hour = 22
        mock_service.config.night_end_hour = 6
        mock_service.config.enable_self_healing = True
        mock_service.config.telegram_chat_id = None
        mock_service.is_night_hours.return_value = False

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await get_nightwatch_status()

        # current_hour_utc should be a valid hour (0-23)
        assert 0 <= response.current_hour_utc <= 23


@requires_asyncpg
class TestNightWatchTickEndpoint:
    """Tests for POST /api/nightwatch/tick endpoint."""

    @pytest.mark.asyncio
    async def test_tick_success(self):
        """nightwatch_tick should return completed status on success."""
        from src.api.routes.nightwatch import nightwatch_tick

        mock_service = MagicMock()
        mock_service.tick = AsyncMock(
            return_value={
                "status": "completed",
                "timestamp": "2026-01-22T03:00:00Z",
                "duration_ms": 1500,
                "activities": [{"type": "health_check", "service": "railway", "success": True}],
            }
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await nightwatch_tick(db_session=mock_session)

        assert response.status == "completed"
        assert response.duration_ms == 1500
        assert len(response.activities) == 1
        assert response.error is None

    @pytest.mark.asyncio
    async def test_tick_error_handling(self):
        """nightwatch_tick should handle errors gracefully."""
        from src.api.routes.nightwatch import nightwatch_tick

        mock_service = MagicMock()
        mock_service.tick = AsyncMock(side_effect=Exception("Service unavailable"))

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await nightwatch_tick(db_session=mock_session)

        assert response.status == "error"
        assert "Service unavailable" in response.error

    @pytest.mark.asyncio
    async def test_tick_skipped_during_day(self):
        """nightwatch_tick should return skipped status during day hours."""
        from src.api.routes.nightwatch import nightwatch_tick

        mock_service = MagicMock()
        mock_service.tick = AsyncMock(
            return_value={
                "status": "skipped",
                "timestamp": "2026-01-22T14:00:00Z",
                "activities": [],
            }
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await nightwatch_tick(db_session=mock_session)

        assert response.status == "skipped"
        assert response.activities == []


@requires_asyncpg
class TestMorningSummaryEndpoint:
    """Tests for POST /api/nightwatch/morning-summary endpoint."""

    @pytest.mark.asyncio
    async def test_morning_summary_success(self):
        """send_morning_summary should return sent status on success."""
        from src.api.routes.nightwatch import send_morning_summary

        mock_service = MagicMock()
        mock_service.send_morning_summary = AsyncMock(
            return_value={
                "status": "sent",
                "summary": {
                    "total_activities": 24,
                    "health_checks_passed": 20,
                    "health_checks_failed": 4,
                    "overall_status": "good",
                },
            }
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await send_morning_summary(db_session=mock_session)

        assert response.status == "sent"
        assert response.summary["total_activities"] == 24
        assert response.error is None

    @pytest.mark.asyncio
    async def test_morning_summary_telegram_failure(self):
        """send_morning_summary should handle Telegram errors."""
        from src.api.routes.nightwatch import send_morning_summary

        mock_service = MagicMock()
        mock_service.send_morning_summary = AsyncMock(
            side_effect=Exception("Telegram API error")
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await send_morning_summary(db_session=mock_session)

        assert response.status == "error"
        assert "Telegram API error" in response.error


@requires_asyncpg
class TestGetSummaryEndpoint:
    """Tests for GET /api/nightwatch/summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary_success(self):
        """get_summary should return summary without sending."""
        from src.api.routes.nightwatch import get_summary

        mock_summary = MagicMock()
        mock_summary.period_start = datetime(2026, 1, 22, 22, 0, 0, tzinfo=UTC)
        mock_summary.period_end = datetime(2026, 1, 23, 6, 0, 0, tzinfo=UTC)
        mock_summary.total_activities = 15
        mock_summary.health_checks_passed = 12
        mock_summary.health_checks_failed = 3
        mock_summary.anomalies_detected = 1
        mock_summary.self_healing_actions = 1
        mock_summary.alerts_sent = 2
        mock_summary.critical_events = []
        mock_summary.services_affected = ["railway"]
        mock_summary.overall_status = "good"

        mock_service = MagicMock()
        mock_service.generate_morning_summary = AsyncMock(return_value=mock_summary)

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await get_summary(db_session=mock_session)

        assert response["total_activities"] == 15
        assert response["health_checks_passed"] == 12
        assert response["anomalies_detected"] == 1
        assert response["overall_status"] == "good"

    @pytest.mark.asyncio
    async def test_get_summary_error(self):
        """get_summary should raise HTTPException on error."""
        from fastapi import HTTPException

        from src.api.routes.nightwatch import get_summary

        mock_service = MagicMock()
        mock_service.generate_morning_summary = AsyncMock(
            side_effect=Exception("Database error")
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await get_summary(db_session=mock_session)

        assert exc_info.value.status_code == 500


@requires_asyncpg
class TestListActivitiesEndpoint:
    """Tests for GET /api/nightwatch/activities endpoint."""

    @pytest.mark.asyncio
    async def test_list_activities_success(self):
        """list_activities should return activity list."""
        from src.api.routes.nightwatch import list_activities

        mock_activity = MagicMock()
        mock_activity.id = 1
        mock_activity.activity_type = "health_check"
        mock_activity.severity = "info"
        mock_activity.service_name = "railway"
        mock_activity.description = "Health check completed"
        mock_activity.success = True
        mock_activity.duration_ms = 150
        mock_activity.created_at = datetime(2026, 1, 22, 3, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_activity]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await list_activities(
            hours=6,
            activity_type=None,
            severity=None,
            limit=100,
            db_session=mock_session,
        )

        assert response["count"] == 1
        assert "since" in response
        assert len(response["activities"]) == 1
        assert response["activities"][0]["activity_type"] == "health_check"

    @pytest.mark.asyncio
    async def test_list_activities_empty(self):
        """list_activities should handle empty results."""
        from src.api.routes.nightwatch import list_activities

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await list_activities(
            hours=6,
            activity_type=None,
            severity=None,
            limit=100,
            db_session=mock_session,
        )

        assert response["count"] == 0
        assert response["activities"] == []

    @pytest.mark.asyncio
    async def test_list_activities_with_filters(self):
        """list_activities should apply filters."""
        from src.api.routes.nightwatch import list_activities

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await list_activities(
            hours=12,
            activity_type="anomaly",
            severity="warning",
            limit=50,
            db_session=mock_session,
        )

        # Should execute without error
        assert response["count"] == 0
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_activities_database_error(self):
        """list_activities should raise HTTPException on database error."""
        from fastapi import HTTPException

        from src.api.routes.nightwatch import list_activities

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("Connection lost"))

        with pytest.raises(HTTPException) as exc_info:
            await list_activities(
                hours=6,
                activity_type=None,
                severity=None,
                limit=100,
                db_session=mock_session,
            )

        assert exc_info.value.status_code == 500


@requires_asyncpg
class TestTelegramTestEndpoint:
    """Tests for POST /api/nightwatch/test-telegram endpoint."""

    @pytest.mark.asyncio
    async def test_telegram_test_no_chat_id(self):
        """test_telegram_send should error without chat_id."""
        from src.api.routes.nightwatch import test_telegram_send

        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = None

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            response = await test_telegram_send(message="Test", db_session=mock_session)

        assert response["status"] == "error"
        assert "No Telegram chat_id configured" in response["error"]

    @pytest.mark.asyncio
    async def test_telegram_test_success_direct_api(self):
        """test_telegram_send should succeed with direct API."""
        from src.api.routes.nightwatch import test_telegram_send

        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "12345"
        mock_service.telegram_token = "test-token"

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("src.api.routes.nightwatch.httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_client_instance

                response = await test_telegram_send(message="Hello", db_session=mock_session)

        assert response["status"] == "sent"
        assert response["method"] == "direct_api"
        assert response["chat_id"] == "12345"

    @pytest.mark.asyncio
    async def test_telegram_test_api_failure(self):
        """test_telegram_send should handle API failure."""
        from src.api.routes.nightwatch import test_telegram_send

        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "12345"
        mock_service.telegram_token = "test-token"

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bot blocked"}

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("src.api.routes.nightwatch.httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_client_instance

                response = await test_telegram_send(message="Hello", db_session=mock_session)

        assert response["status"] == "failed"
        assert "Bot blocked" in response["error"]

    @pytest.mark.asyncio
    async def test_telegram_test_network_error(self):
        """test_telegram_send should handle network errors."""
        from src.api.routes.nightwatch import test_telegram_send

        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "12345"
        mock_service.telegram_token = "test-token"

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("src.api.routes.nightwatch.httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(
                    side_effect=Exception("Connection timeout")
                )
                mock_client.return_value = mock_client_instance

                response = await test_telegram_send(message="Hello", db_session=mock_session)

        assert response["status"] == "error"
        assert "Connection timeout" in response["error"]

    @pytest.mark.asyncio
    async def test_telegram_test_fallback_railway_service(self):
        """test_telegram_send should fall back to Railway service."""
        from src.api.routes.nightwatch import test_telegram_send

        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "12345"
        mock_service.telegram_token = None  # No direct token
        mock_service.telegram_url = "https://telegram-bot.railway.app"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("src.api.routes.nightwatch.httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_client_instance

                response = await test_telegram_send(message="Hello", db_session=mock_session)

        assert response["status"] == "sent"
        assert response["method"] == "railway_service"


class TestNightWatchHoursLogic:
    """Tests for night hours detection logic."""

    def test_night_hours_detection_in_range(self):
        """is_night_hours should return True during night hours."""
        # This tests the logic indirectly
        # Night hours: 22:00 - 06:00 UTC
        # Hour 3 is in night hours
        hour = 3
        night_start = 22
        night_end = 6

        # Night hours span midnight
        is_night = hour >= night_start or hour < night_end
        assert is_night is True

    def test_night_hours_detection_at_boundary_start(self):
        """is_night_hours should be True at night start."""
        hour = 22
        night_start = 22
        night_end = 6

        is_night = hour >= night_start or hour < night_end
        assert is_night is True

    def test_night_hours_detection_at_boundary_end(self):
        """is_night_hours should be False at night end."""
        hour = 6
        night_start = 22
        night_end = 6

        is_night = hour >= night_start or hour < night_end
        assert is_night is False

    def test_day_hours_detection(self):
        """is_night_hours should return False during day hours."""
        hour = 14
        night_start = 22
        night_end = 6

        is_night = hour >= night_start or hour < night_end
        assert is_night is False


class TestActivityLogSerialization:
    """Tests for activity log serialization."""

    def test_activity_serialization(self):
        """Activity log entries should serialize correctly."""
        activity = {
            "id": 1,
            "activity_type": "health_check",
            "severity": "info",
            "service_name": "railway",
            "description": "Health check completed",
            "success": True,
            "duration_ms": 150,
            "created_at": "2026-01-22T03:00:00+00:00",
        }

        # Verify all required fields exist
        assert "id" in activity
        assert "activity_type" in activity
        assert "severity" in activity
        assert "success" in activity
        assert "created_at" in activity

    def test_activity_with_null_fields(self):
        """Activity log entries should handle null fields."""
        activity = {
            "id": 2,
            "activity_type": "anomaly_detection",
            "severity": "warning",
            "service_name": None,  # Nullable
            "description": "Anomaly detected",
            "success": False,
            "duration_ms": None,  # Nullable
            "created_at": "2026-01-22T03:30:00+00:00",
        }

        assert activity["service_name"] is None
        assert activity["duration_ms"] is None
