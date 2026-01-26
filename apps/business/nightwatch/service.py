"""Night Watch Service - Autonomous overnight operations.

This module implements the Night Watch system that performs
autonomous operations during night hours (00:00-06:00 UTC)
and generates morning summaries.

Architecture (ADR-013):
    Railway Cron → /api/nightwatch/tick → NightWatchService
                                              ↓
                                    MonitoringLoop.collect()
                                              ↓
                                    ActivityLog (PostgreSQL)
                                              ↓
    Railway Cron → /api/nightwatch/morning-summary
                                              ↓
                                    Telegram Bot /send
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from apps.business.models.activity_log import (
    ActivityLog,
    ActivitySeverity,
    ActivityType,
    NightWatchConfig,
    NightWatchSummary,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NightWatchService:
    """Orchestrates autonomous night operations.

    This service is triggered by Railway cron jobs and performs:
    1. Hourly health checks and metric collection
    2. Anomaly detection and self-healing
    3. Activity logging for audit trail
    4. Morning summary generation and delivery

    Attributes:
        config: Night Watch configuration
        db_session: Database session for activity logging
        telegram_url: URL to Telegram Bot /send endpoint
        monitoring_url: URL to /api/monitoring endpoints

    Example:
        >>> service = NightWatchService()
        >>> await service.tick()  # Called by cron every hour
        >>> await service.generate_morning_summary()  # Called at 06:00
    """

    def __init__(
        self,
        config: NightWatchConfig | None = None,
        telegram_url: str | None = None,
        monitoring_url: str | None = None,
    ):
        """Initialize Night Watch service.

        Args:
            config: Configuration settings (defaults loaded from env)
            telegram_url: Telegram Bot URL (defaults to env TELEGRAM_BOT_URL)
            monitoring_url: Monitoring API URL (defaults to self /api)
        """
        self.config = config or self._load_config_from_env()
        self.telegram_url = telegram_url or os.getenv(
            "TELEGRAM_BOT_URL",
            "https://telegram-bot-production-053d.up.railway.app",
        )
        self.monitoring_url = monitoring_url or os.getenv(
            "MONITORING_URL",
            "https://or-infra.com",
        )
        # Direct Telegram API token - if set, bypasses Railway telegram-bot service
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self._http_client: httpx.AsyncClient | None = None

    def _load_config_from_env(self) -> NightWatchConfig:
        """Load configuration from environment variables."""
        return NightWatchConfig(
            enabled=os.getenv("NIGHTWATCH_ENABLED", "true").lower() == "true",
            night_start_hour=int(os.getenv("NIGHTWATCH_START_HOUR", "0")),
            night_end_hour=int(os.getenv("NIGHTWATCH_END_HOUR", "6")),
            health_check_interval_minutes=int(
                os.getenv("NIGHTWATCH_HEALTH_INTERVAL", "60")
            ),
            telegram_chat_id=int(os.getenv("NIGHTWATCH_CHAT_ID", "0")) or None,
            enable_self_healing=os.getenv(
                "NIGHTWATCH_SELF_HEALING", "true"
            ).lower() == "true",
            max_healing_actions_per_hour=int(
                os.getenv("NIGHTWATCH_MAX_HEALING", "3")
            ),
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def is_night_hours(self) -> bool:
        """Check if current time is within night hours."""
        now = datetime.now(UTC)
        return self.config.night_start_hour <= now.hour < self.config.night_end_hour

    async def tick(self, db_session: AsyncSession) -> dict[str, Any]:
        """Perform one tick of night watch operations.

        Called by Railway cron every hour during night hours.
        Performs health checks, collects metrics, detects anomalies.

        Args:
            db_session: Database session for logging

        Returns:
            dict: Tick results with activities performed
        """
        if not self.config.enabled:
            return {"status": "disabled", "message": "Night Watch is disabled"}

        start_time = datetime.now(UTC)
        activities: list[dict] = []

        try:
            # Log tick start
            await self._log_activity(
                db_session,
                ActivityType.SYSTEM_START,
                ActivitySeverity.INFO,
                description=f"Night Watch tick started at {start_time.isoformat()}",
            )

            # 1. Perform health check
            health_result = await self._perform_health_check(db_session)
            activities.append(health_result)

            # 2. Collect metrics
            metrics_result = await self._collect_metrics(db_session)
            activities.append(metrics_result)

            # 3. Check for anomalies (if monitoring is running)
            if health_result.get("healthy", False):
                anomaly_result = await self._check_anomalies(db_session)
                activities.append(anomaly_result)

                # 4. Self-healing if enabled and anomalies found
                if (
                    self.config.enable_self_healing
                    and anomaly_result.get("anomalies_found", 0) > 0
                ):
                    healing_result = await self._attempt_self_healing(
                        db_session, anomaly_result
                    )
                    activities.append(healing_result)

            duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

            return {
                "status": "success",
                "timestamp": start_time.isoformat(),
                "duration_ms": duration_ms,
                "activities": activities,
            }

        except Exception as e:
            logger.error(f"Night Watch tick failed: {e}", exc_info=True)
            await self._log_activity(
                db_session,
                ActivityType.ERROR,
                ActivitySeverity.ERROR,
                description=f"Night Watch tick failed: {str(e)}",
                success=False,
            )
            return {
                "status": "error",
                "error": str(e),
                "timestamp": start_time.isoformat(),
            }

    async def _perform_health_check(
        self, db_session: AsyncSession
    ) -> dict[str, Any]:
        """Perform health check on main services."""
        start = datetime.now(UTC)
        client = await self._get_http_client()

        try:
            response = await client.get(f"{self.monitoring_url}/api/health")
            duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

            healthy = response.status_code == 200
            data = response.json() if response.status_code == 200 else {}

            await self._log_activity(
                db_session,
                ActivityType.HEALTH_CHECK,
                ActivitySeverity.INFO if healthy else ActivitySeverity.WARNING,
                service_name="main-api",
                description=f"Health check {'passed' if healthy else 'failed'}",
                details=json.dumps(data),
                success=healthy,
                duration_ms=duration_ms,
            )

            return {
                "type": "health_check",
                "healthy": healthy,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "details": data,
            }

        except Exception as e:
            duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            await self._log_activity(
                db_session,
                ActivityType.HEALTH_CHECK,
                ActivitySeverity.ERROR,
                service_name="main-api",
                description=f"Health check failed: {str(e)}",
                success=False,
                duration_ms=duration_ms,
            )
            return {
                "type": "health_check",
                "healthy": False,
                "error": str(e),
                "duration_ms": duration_ms,
            }

    async def _collect_metrics(self, db_session: AsyncSession) -> dict[str, Any]:
        """Trigger metric collection via monitoring API."""
        start = datetime.now(UTC)
        client = await self._get_http_client()

        try:
            response = await client.post(
                f"{self.monitoring_url}/api/monitoring/collect-now"
            )
            duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

            success = response.status_code == 200
            data = response.json() if success else {}

            await self._log_activity(
                db_session,
                ActivityType.METRIC_COLLECTION,
                ActivitySeverity.INFO if success else ActivitySeverity.WARNING,
                description=f"Collected {data.get('count', 0)} metrics",
                details=json.dumps(data) if success else None,
                success=success,
                duration_ms=duration_ms,
            )

            return {
                "type": "metric_collection",
                "success": success,
                "metrics_count": data.get("count", 0),
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            await self._log_activity(
                db_session,
                ActivityType.METRIC_COLLECTION,
                ActivitySeverity.WARNING,
                description=f"Metric collection failed: {str(e)}",
                success=False,
                duration_ms=duration_ms,
            )
            return {
                "type": "metric_collection",
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms,
            }

    async def _check_anomalies(self, db_session: AsyncSession) -> dict[str, Any]:
        """Check monitoring status for anomalies."""
        client = await self._get_http_client()

        try:
            response = await client.get(
                f"{self.monitoring_url}/api/monitoring/status"
            )

            if response.status_code != 200:
                return {"type": "anomaly_check", "success": False, "anomalies_found": 0}

            data = response.json()
            anomalies = data.get("anomalies_detected", 0)

            if anomalies > 0:
                await self._log_activity(
                    db_session,
                    ActivityType.ANOMALY_DETECTED,
                    ActivitySeverity.WARNING,
                    description=f"Detected {anomalies} anomalies",
                    details=json.dumps(data),
                )

            return {
                "type": "anomaly_check",
                "success": True,
                "anomalies_found": anomalies,
                "monitoring_state": data.get("state", "unknown"),
            }

        except Exception as e:
            return {
                "type": "anomaly_check",
                "success": False,
                "error": str(e),
                "anomalies_found": 0,
            }

    async def _attempt_self_healing(
        self, db_session: AsyncSession, anomaly_result: dict
    ) -> dict[str, Any]:
        """Attempt automatic healing actions."""
        # For now, just log that we would attempt healing
        # Full implementation would call AutonomousController
        anomalies_count = anomaly_result.get("anomalies_found", 0)
        await self._log_activity(
            db_session,
            ActivityType.SELF_HEALING,
            ActivitySeverity.INFO,
            description=f"Self-healing triggered for {anomalies_count} anomalies",
            details=json.dumps(anomaly_result),
        )

        return {
            "type": "self_healing",
            "attempted": True,
            "anomalies_addressed": anomaly_result.get("anomalies_found", 0),
        }

    async def _log_activity(
        self,
        db_session: AsyncSession,
        activity_type: ActivityType,
        severity: ActivitySeverity,
        description: str,
        service_name: str | None = None,
        details: str | None = None,
        success: bool = True,
        duration_ms: int | None = None,
    ) -> None:
        """Log an activity to the database."""
        activity = ActivityLog(
            activity_type=activity_type.value,
            severity=severity.value,
            service_name=service_name,
            description=description,
            details=details,
            success=success,
            duration_ms=duration_ms,
        )
        db_session.add(activity)
        await db_session.commit()
        logger.info(f"[NightWatch] {activity_type.value}: {description}")

    async def generate_morning_summary(
        self, db_session: AsyncSession
    ) -> NightWatchSummary:
        """Generate summary of overnight activities.

        Called by Railway cron at 06:00 UTC.
        Aggregates all activities from the night and creates a summary.

        Args:
            db_session: Database session for querying activities

        Returns:
            NightWatchSummary: Aggregated summary of night activities
        """
        from sqlalchemy import select

        now = datetime.now(UTC)
        night_start = now.replace(
            hour=self.config.night_start_hour, minute=0, second=0, microsecond=0
        )

        # If we're past midnight, night_start was yesterday
        if now.hour >= self.config.night_end_hour:
            night_start = night_start - timedelta(days=1)

        # Query activities from the night period
        query = select(ActivityLog).where(
            ActivityLog.created_at >= night_start,
            ActivityLog.created_at <= now,
        )
        result = await db_session.execute(query)
        activities = result.scalars().all()

        # Aggregate statistics
        summary = NightWatchSummary(
            period_start=night_start,
            period_end=now,
            total_activities=len(activities),
        )

        critical_events = []
        services_affected = set()

        for activity in activities:
            if activity.activity_type == ActivityType.HEALTH_CHECK.value:
                if activity.success:
                    summary.health_checks_passed += 1
                else:
                    summary.health_checks_failed += 1
            elif activity.activity_type == ActivityType.ANOMALY_DETECTED.value:
                summary.anomalies_detected += 1
            elif activity.activity_type == ActivityType.SELF_HEALING.value:
                summary.self_healing_actions += 1
            elif activity.activity_type == ActivityType.ALERT_SENT.value:
                summary.alerts_sent += 1

            if activity.severity in [
                ActivitySeverity.ERROR.value,
                ActivitySeverity.CRITICAL.value,
            ]:
                critical_events.append(activity.description)

            if activity.service_name:
                services_affected.add(activity.service_name)

        summary.critical_events = critical_events
        summary.services_affected = list(services_affected)

        # Determine overall status
        if summary.health_checks_failed > 0 or len(critical_events) > 0:
            summary.overall_status = "degraded"
        if (
            summary.health_checks_failed > summary.health_checks_passed
            or len(critical_events) > 2
        ):
            summary.overall_status = "critical"

        return summary

    async def send_morning_summary(
        self, db_session: AsyncSession
    ) -> dict[str, Any]:
        """Generate and send morning summary via Telegram.

        Called by Railway cron at 06:00 UTC.

        Args:
            db_session: Database session

        Returns:
            dict: Result of summary generation and delivery
        """
        if not self.config.telegram_chat_id:
            return {
                "status": "skipped",
                "reason": "No Telegram chat_id configured",
            }

        try:
            summary = await self.generate_morning_summary(db_session)
            message = self._format_summary_message(summary)

            client = await self._get_http_client()

            # Use direct Telegram API if token is available, otherwise use Railway service
            if self.telegram_token:
                # Direct Telegram API (preferred - bypasses Railway service)
                response = await client.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={
                        "chat_id": self.config.telegram_chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                )
                response_data = response.json()
                success = response_data.get("ok", False)
                if not success:
                    logger.error(f"Telegram API error: {response_data.get('description')}")
            else:
                # Fall back to Railway telegram-bot service
                response = await client.post(
                    f"{self.telegram_url}/send",
                    params={
                        "chat_id": self.config.telegram_chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                )
                success = response.status_code == 200

            await self._log_activity(
                db_session,
                ActivityType.ALERT_SENT,
                ActivitySeverity.INFO,
                description="Morning summary sent to Telegram",
                success=success,
            )

            return {
                "status": "sent" if success else "failed",
                "summary": {
                    "total_activities": summary.total_activities,
                    "health_checks_passed": summary.health_checks_passed,
                    "health_checks_failed": summary.health_checks_failed,
                    "overall_status": summary.overall_status,
                },
            }

        except Exception as e:
            logger.error(f"Failed to send morning summary: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }

    def _format_summary_message(self, summary: NightWatchSummary) -> str:
        """Format summary as Telegram message with HTML."""
        status_emoji = {
            "healthy": "\u2705",  # ✅
            "degraded": "\u26a0\ufe0f",  # ⚠️
            "critical": "\u274c",  # ❌
        }
        unknown_emoji = "\u2753"  # ❓
        check_mark = "\u2705"
        cross_mark = "\u274c"
        bullet = "\u2022"
        warning = "\u26a0\ufe0f"

        emoji = status_emoji.get(summary.overall_status, unknown_emoji)
        start_time = summary.period_start.strftime("%H:%M")
        end_time = summary.period_end.strftime("%H:%M")
        passed = summary.health_checks_passed
        failed = summary.health_checks_failed

        lines = [
            "<b>\U0001f319 Night Watch Summary</b>",  # 🌙
            f"<code>{start_time} - {end_time} UTC</code>",
            "",
            f"Status: {emoji} <b>{summary.overall_status.upper()}</b>",
            "",
            "\U0001f4ca <b>Statistics:</b>",  # 📊
            f"  {bullet} Total activities: {summary.total_activities}",
            f"  {bullet} Health checks: {passed}{check_mark} / {failed}{cross_mark}",
            f"  {bullet} Anomalies detected: {summary.anomalies_detected}",
            f"  {bullet} Self-healing actions: {summary.self_healing_actions}",
        ]

        if summary.critical_events:
            lines.extend([
                "",
                f"{warning} <b>Critical Events:</b>",
            ])
            for event in summary.critical_events[:5]:  # Limit to 5
                lines.append(f"  {bullet} {event}")

        if summary.services_affected:
            lines.extend([
                "",
                "\U0001f3af <b>Services Affected:</b>",  # 🎯
                f"  {', '.join(summary.services_affected)}",
            ])

        lines.extend([
            "",
            "<i>Generated by Night Watch (ADR-013)</i>",
        ])

        return "\n".join(lines)


# Singleton instance
_night_watch: NightWatchService | None = None


def get_night_watch() -> NightWatchService:
    """Get or create the global Night Watch instance."""
    global _night_watch
    if _night_watch is None:
        _night_watch = NightWatchService()
    return _night_watch
