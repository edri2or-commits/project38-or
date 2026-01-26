"""Night Watch API endpoints for autonomous overnight operations.

This module provides endpoints for:
- Cron-triggered tick operations
- Morning summary generation and delivery
- Night Watch status and configuration
- Activity log querying
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.business.api.database import get_session as get_db_session
from apps.business.models.activity_log import ActivityLog
from apps.business.nightwatch import get_night_watch

logger = logging.getLogger(__name__)
router = APIRouter()


class NightWatchStatus(BaseModel):
    """Response model for Night Watch status."""

    enabled: bool
    is_night_hours: bool
    current_hour_utc: int
    night_start_hour: int
    night_end_hour: int
    self_healing_enabled: bool
    telegram_configured: bool


class ActivityLogEntry(BaseModel):
    """Response model for activity log entries."""

    id: int
    activity_type: str
    severity: str
    service_name: str | None
    description: str
    success: bool
    duration_ms: int | None
    created_at: str


class TickResult(BaseModel):
    """Response model for tick operation."""

    status: str
    timestamp: str
    duration_ms: int | None = None
    activities: list[dict] = []
    error: str | None = None


class SummaryResult(BaseModel):
    """Response model for morning summary."""

    status: str
    summary: dict | None = None
    error: str | None = None


@router.get("/api/nightwatch/status", response_model=NightWatchStatus)
async def get_nightwatch_status() -> NightWatchStatus:
    """Get current Night Watch status and configuration.

    Returns whether Night Watch is enabled, if it's currently
    night hours, and configuration settings.
    """
    service = get_night_watch()
    now = datetime.now(UTC)

    return NightWatchStatus(
        enabled=service.config.enabled,
        is_night_hours=service.is_night_hours(),
        current_hour_utc=now.hour,
        night_start_hour=service.config.night_start_hour,
        night_end_hour=service.config.night_end_hour,
        self_healing_enabled=service.config.enable_self_healing,
        telegram_configured=service.config.telegram_chat_id is not None,
    )


@router.post("/api/nightwatch/tick", response_model=TickResult)
async def nightwatch_tick(
    db_session: AsyncSession = Depends(get_db_session),
) -> TickResult:
    """Execute one tick of Night Watch operations.

    This endpoint is called by Railway cron every hour during night hours.
    Performs health checks, metric collection, and anomaly detection.
    """
    service = get_night_watch()

    try:
        result = await service.tick(db_session)

        return TickResult(
            status=result.get("status", "unknown"),
            timestamp=result.get("timestamp", datetime.now(UTC).isoformat()),
            duration_ms=result.get("duration_ms"),
            activities=result.get("activities", []),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Night Watch tick failed: {e}", exc_info=True)
        return TickResult(
            status="error",
            timestamp=datetime.now(UTC).isoformat(),
            error=str(e),
        )


@router.post("/api/nightwatch/morning-summary", response_model=SummaryResult)
async def send_morning_summary(
    db_session: AsyncSession = Depends(get_db_session),
) -> SummaryResult:
    """Generate and send the morning summary.

    This endpoint is called by Railway cron at 06:00 UTC.
    Aggregates overnight activities and sends summary to Telegram.
    """
    service = get_night_watch()

    try:
        result = await service.send_morning_summary(db_session)

        return SummaryResult(
            status=result.get("status", "unknown"),
            summary=result.get("summary"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Morning summary failed: {e}", exc_info=True)
        return SummaryResult(
            status="error",
            error=str(e),
        )


@router.get("/api/nightwatch/summary")
async def get_summary(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get the current night's summary without sending it.

    Useful for testing and debugging the summary generation.
    """
    service = get_night_watch()

    try:
        summary = await service.generate_morning_summary(db_session)

        return {
            "period_start": summary.period_start.isoformat(),
            "period_end": summary.period_end.isoformat(),
            "total_activities": summary.total_activities,
            "health_checks_passed": summary.health_checks_passed,
            "health_checks_failed": summary.health_checks_failed,
            "anomalies_detected": summary.anomalies_detected,
            "self_healing_actions": summary.self_healing_actions,
            "alerts_sent": summary.alerts_sent,
            "critical_events": summary.critical_events,
            "services_affected": summary.services_affected,
            "overall_status": summary.overall_status,
        }

    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/nightwatch/activities")
async def list_activities(
    hours: int = Query(default=6, ge=1, le=168, description="Hours to look back"),
    activity_type: str | None = Query(default=None, description="Filter by type"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List recent activity log entries.

    Args:
        hours: Number of hours to look back (1-168)
        activity_type: Filter by activity type
        severity: Filter by severity level
        limit: Maximum number of results

    Returns:
        List of activity log entries
    """
    try:
        since = datetime.now(UTC) - timedelta(hours=hours)

        query = select(ActivityLog).where(ActivityLog.created_at >= since)

        if activity_type:
            query = query.where(ActivityLog.activity_type == activity_type)
        if severity:
            query = query.where(ActivityLog.severity == severity)

        query = query.order_by(ActivityLog.created_at.desc()).limit(limit)

        result = await db_session.execute(query)
        activities = result.scalars().all()

        return {
            "count": len(activities),
            "since": since.isoformat(),
            "activities": [
                {
                    "id": a.id,
                    "activity_type": a.activity_type,
                    "severity": a.severity,
                    "service_name": a.service_name,
                    "description": a.description,
                    "success": a.success,
                    "duration_ms": a.duration_ms,
                    "created_at": a.created_at.isoformat(),
                }
                for a in activities
            ],
        }

    except Exception as e:
        logger.error(f"Failed to list activities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/nightwatch/test-telegram")
async def test_telegram_send(
    message: str = Query(default="Test message from Night Watch"),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Test Telegram message sending.

    Sends a test message to the configured Telegram chat.
    Used for verifying the connection before enabling Night Watch.
    """
    import httpx

    service = get_night_watch()

    if not service.config.telegram_chat_id:
        return {
            "status": "error",
            "error": "No Telegram chat_id configured. Set NIGHTWATCH_CHAT_ID env var.",
        }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            test_message = f"\U0001f9ea <b>Night Watch Test</b>\n\n{message}"

            # Use direct Telegram API if token is available
            if service.telegram_token:
                response = await client.post(
                    f"https://api.telegram.org/bot{service.telegram_token}/sendMessage",
                    json={
                        "chat_id": service.config.telegram_chat_id,
                        "text": test_message,
                        "parse_mode": "HTML",
                    },
                )
                response_data = response.json()
                if response_data.get("ok"):
                    return {
                        "status": "sent",
                        "chat_id": service.config.telegram_chat_id,
                        "method": "direct_api",
                        "telegram_response": response_data,
                    }
                else:
                    return {
                        "status": "failed",
                        "method": "direct_api",
                        "error": response_data.get("description", "Unknown error"),
                    }
            else:
                # Fall back to Railway telegram-bot service
                response = await client.post(
                    f"{service.telegram_url}/send",
                    params={
                        "chat_id": service.config.telegram_chat_id,
                        "text": test_message,
                        "parse_mode": "HTML",
                    },
                )

                if response.status_code == 200:
                    return {
                        "status": "sent",
                        "chat_id": service.config.telegram_chat_id,
                        "method": "railway_service",
                        "telegram_response": response.json(),
                    }
                else:
                    return {
                        "status": "failed",
                        "method": "railway_service",
                        "status_code": response.status_code,
                        "response": response.text,
                    }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
