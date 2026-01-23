"""Tests for Night Watch API endpoints.

Tests the nightwatch module in src/api/routes/nightwatch.py.
Covers:
- Night Watch status endpoint
- Tick operation endpoint
- Morning summary endpoint
- Activity log listing
- Telegram test endpoint
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the module
from src.api.routes.nightwatch import (
    NightWatchStatus,
    ActivityLogEntry,
    TickResult,
    SummaryResult,
    get_nightwatch_status,
    nightwatch_tick,
    send_morning_summary,
    get_summary,
    list_activities,
    test_telegram_send,
)


class TestNightWatchStatus:
    """Tests for NightWatchStatus response model."""

    def test_status_model(self):
        """Test creating a status response."""
        status = NightWatchStatus(
            enabled=True,
            is_night_hours=True,
            current_hour_utc=3,
            night_start_hour=0,
            night_end_hour=6,
            self_healing_enabled=True,
            telegram_configured=True,
        )

        assert status.enabled is True
        assert status.is_night_hours is True
        assert status.current_hour_utc == 3

    def test_status_model_disabled(self):
        """Test status when Night Watch is disabled."""
        status = NightWatchStatus(
            enabled=False,
            is_night_hours=False,
            current_hour_utc=12,
            night_start_hour=0,
            night_end_hour=6,
            self_healing_enabled=False,
            telegram_configured=False,
        )

        assert status.enabled is False
        assert status.telegram_configured is False


class TestTickResult:
    """Tests for TickResult response model."""

    def test_tick_success(self):
        """Test tick result on success."""
        result = TickResult(
            status="success",
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=150,
            activities=[{"type": "health_check", "success": True}],
        )

        assert result.status == "success"
        assert result.duration_ms == 150
        assert len(result.activities) == 1

    def test_tick_error(self):
        """Test tick result on error."""
        result = TickResult(
            status="error",
            timestamp=datetime.now(UTC).isoformat(),
            error="Connection failed",
        )

        assert result.status == "error"
        assert result.error == "Connection failed"


class TestSummaryResult:
    """Tests for SummaryResult response model."""

    def test_summary_success(self):
        """Test summary result on success."""
        result = SummaryResult(
            status="sent",
            summary={"total_activities": 10, "health_checks_passed": 8},
        )

        assert result.status == "sent"
        assert result.summary["total_activities"] == 10

    def test_summary_error(self):
        """Test summary result on error."""
        result = SummaryResult(
            status="error",
            error="Telegram API failed",
        )

        assert result.status == "error"
        assert result.error == "Telegram API failed"


class TestGetNightwatchStatus:
    """Tests for get_nightwatch_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_enabled(self):
        """Test getting status when Night Watch is enabled."""
        mock_service = MagicMock()
        mock_service.config.enabled = True
        mock_service.config.night_start_hour = 0
        mock_service.config.night_end_hour = 6
        mock_service.config.enable_self_healing = True
        mock_service.config.telegram_chat_id = "123456"
        mock_service.is_night_hours.return_value = True

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await get_nightwatch_status()

        assert result.enabled is True
        assert result.telegram_configured is True

    @pytest.mark.asyncio
    async def test_get_status_disabled(self):
        """Test getting status when Night Watch is disabled."""
        mock_service = MagicMock()
        mock_service.config.enabled = False
        mock_service.config.night_start_hour = 0
        mock_service.config.night_end_hour = 6
        mock_service.config.enable_self_healing = False
        mock_service.config.telegram_chat_id = None
        mock_service.is_night_hours.return_value = False

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await get_nightwatch_status()

        assert result.enabled is False
        assert result.telegram_configured is False


class TestNightwatchTick:
    """Tests for nightwatch_tick endpoint."""

    @pytest.mark.asyncio
    async def test_tick_success(self):
        """Test successful tick operation."""
        mock_service = MagicMock()
        mock_service.tick = AsyncMock(return_value={
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_ms": 150,
            "activities": [{"type": "health_check"}],
        })

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await nightwatch_tick(db_session=mock_session)

        assert result.status == "success"
        assert result.duration_ms == 150

    @pytest.mark.asyncio
    async def test_tick_error(self):
        """Test tick operation when error occurs."""
        mock_service = MagicMock()
        mock_service.tick = AsyncMock(side_effect=Exception("Database connection failed"))

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await nightwatch_tick(db_session=mock_session)

        assert result.status == "error"
        assert "Database connection failed" in result.error


class TestSendMorningSummary:
    """Tests for send_morning_summary endpoint."""

    @pytest.mark.asyncio
    async def test_send_summary_success(self):
        """Test successful morning summary send."""
        mock_service = MagicMock()
        mock_service.send_morning_summary = AsyncMock(return_value={
            "status": "sent",
            "summary": {"total_activities": 10},
        })

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await send_morning_summary(db_session=mock_session)

        assert result.status == "sent"

    @pytest.mark.asyncio
    async def test_send_summary_error(self):
        """Test morning summary when error occurs."""
        mock_service = MagicMock()
        mock_service.send_morning_summary = AsyncMock(
            side_effect=Exception("Telegram API error")
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await send_morning_summary(db_session=mock_session)

        assert result.status == "error"
        assert "Telegram API error" in result.error


class TestGetSummary:
    """Tests for get_summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary_success(self):
        """Test getting summary without sending."""
        mock_summary = MagicMock()
        mock_summary.period_start = datetime.now(UTC) - timedelta(hours=6)
        mock_summary.period_end = datetime.now(UTC)
        mock_summary.total_activities = 15
        mock_summary.health_checks_passed = 12
        mock_summary.health_checks_failed = 3
        mock_summary.anomalies_detected = 1
        mock_summary.self_healing_actions = 1
        mock_summary.alerts_sent = 2
        mock_summary.critical_events = []
        mock_summary.services_affected = ["api"]
        mock_summary.overall_status = "healthy"

        mock_service = MagicMock()
        mock_service.generate_morning_summary = AsyncMock(return_value=mock_summary)

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await get_summary(db_session=mock_session)

        assert result["total_activities"] == 15
        assert result["health_checks_passed"] == 12
        assert result["overall_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_summary_error(self):
        """Test get summary when error occurs."""
        from fastapi import HTTPException

        mock_service = MagicMock()
        mock_service.generate_morning_summary = AsyncMock(
            side_effect=Exception("Database error")
        )

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await get_summary(db_session=mock_session)

        assert exc_info.value.status_code == 500


class TestListActivities:
    """Tests for list_activities endpoint.

    Note: These tests require FastAPI TestClient for full integration testing
    because the endpoint uses Query() parameters that need FastAPI to resolve.
    Here we test the response models instead.
    """

    def test_activity_log_entry_model(self):
        """Test ActivityLogEntry model creation."""
        entry = ActivityLogEntry(
            id=1,
            activity_type="health_check",
            severity="info",
            service_name="api",
            description="Health check passed",
            success=True,
            duration_ms=50,
            created_at="2026-01-23T00:00:00Z",
        )

        assert entry.id == 1
        assert entry.activity_type == "health_check"
        assert entry.success is True

    def test_activity_log_entry_optional_fields(self):
        """Test ActivityLogEntry with optional fields."""
        entry = ActivityLogEntry(
            id=1,
            activity_type="anomaly",
            severity="warning",
            service_name=None,
            description="Anomaly detected",
            success=False,
            duration_ms=None,
            created_at="2026-01-23T00:00:00Z",
        )

        assert entry.service_name is None
        assert entry.duration_ms is None


class TestTestTelegramSend:
    """Tests for test_telegram_send endpoint."""

    @pytest.mark.asyncio
    async def test_telegram_no_chat_id(self):
        """Test when no chat_id is configured."""
        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = None

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            result = await test_telegram_send(db_session=mock_session)

        assert result["status"] == "error"
        assert "No Telegram chat_id configured" in result["error"]

    @pytest.mark.asyncio
    async def test_telegram_send_direct_api_success(self):
        """Test successful Telegram send via direct API."""
        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "123456"
        mock_service.telegram_token = "test_token"
        mock_service.telegram_url = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await test_telegram_send(
                    message="Test message",
                    db_session=mock_session,
                )

        assert result["status"] == "sent"
        assert result["method"] == "direct_api"

    @pytest.mark.asyncio
    async def test_telegram_send_direct_api_failure(self):
        """Test Telegram send via direct API when it fails."""
        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "123456"
        mock_service.telegram_token = "test_token"

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await test_telegram_send(
                    message="Test message",
                    db_session=mock_session,
                )

        assert result["status"] == "failed"
        assert result["method"] == "direct_api"

    @pytest.mark.asyncio
    async def test_telegram_send_railway_fallback(self):
        """Test Telegram send via Railway service fallback."""
        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "123456"
        mock_service.telegram_token = None  # No direct token
        mock_service.telegram_url = "http://telegram-bot.railway.app"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await test_telegram_send(
                    message="Test message",
                    db_session=mock_session,
                )

        assert result["status"] == "sent"
        assert result["method"] == "railway_service"

    @pytest.mark.asyncio
    async def test_telegram_send_exception(self):
        """Test Telegram send when exception occurs."""
        mock_service = MagicMock()
        mock_service.config.telegram_chat_id = "123456"
        mock_service.telegram_token = "test_token"

        mock_session = AsyncMock()

        with patch("src.api.routes.nightwatch.get_night_watch", return_value=mock_service):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.side_effect = Exception("Connection refused")
                mock_client.return_value.__aenter__.return_value = mock_instance

                result = await test_telegram_send(
                    message="Test message",
                    db_session=mock_session,
                )

        assert result["status"] == "error"
        assert "Connection refused" in result["error"]
