"""Alert Manager - Centralized Alerting with Suppression and Runbooks.

Manages all alerts across the system with features like:
- Alert suppression for maintenance windows
- Runbook links for incident response
- Alert deduplication and rate limiting
- Multi-channel notification (Telegram, n8n webhooks)
- Alert history and audit trail

Based on Week 4 requirements from implementation-roadmap.md.

Example:
    >>> from src.alert_manager import AlertManager, MaintenanceWindow
    >>> manager = AlertManager(
    ...     n8n_webhook_url="https://n8n.example.com/webhook/alerts",
    ...     telegram_chat_id="123456789"
    ... )
    >>>
    >>> # Suppress alerts during maintenance
    >>> window = MaintenanceWindow(
    ...     start=datetime.now(UTC),
    ...     end=datetime.now(UTC) + timedelta(hours=2),
    ...     reason="Database migration",
    ... )
    >>> manager.add_maintenance_window(window)
    >>>
    >>> # Send alert with runbook
    >>> await manager.send_alert(
    ...     severity="critical",
    ...     title="High Error Rate",
    ...     message="Error rate exceeds 5%",
    ...     runbook_url="https://docs.example.com/runbooks/high-error-rate",
    ... )
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class MaintenanceWindow:
    """Scheduled maintenance window for alert suppression.

    Attributes:
        start: Maintenance start time
        end: Maintenance end time
        reason: Human-readable reason for maintenance
        suppress_all: If True, suppresses all alerts. If False, only suppresses info alerts.
        created_by: Who created the maintenance window
        tags: Optional tags for categorization (e.g., ["database", "migration"])
    """

    start: datetime
    end: datetime
    reason: str
    suppress_all: bool = False
    created_by: str = "system"
    tags: list[str] = field(default_factory=list)

    def is_active(self, at_time: datetime | None = None) -> bool:
        """Check if maintenance window is currently active.

        Args:
            at_time: Time to check (default: now)

        Returns:
            True if maintenance window is active
        """
        check_time = at_time or datetime.now(UTC)
        return self.start <= check_time <= self.end

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "reason": self.reason,
            "suppress_all": self.suppress_all,
            "created_by": self.created_by,
            "tags": self.tags,
        }


@dataclass
class Alert:
    """Alert with metadata and runbook link.

    Attributes:
        alert_id: Unique alert identifier
        severity: Alert severity (info, warning, critical)
        title: Short alert title
        message: Detailed alert message
        runbook_url: URL to runbook documentation
        timestamp: When the alert was created
        tags: Optional tags for categorization
        metadata: Additional metadata (e.g., metric values, thresholds)
        dedupe_key: Key for alert deduplication (default: title)
    """

    alert_id: str
    severity: str
    title: str
    message: str
    runbook_url: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str | None = None

    def __post_init__(self):
        """Set dedupe_key to title if not provided."""
        if self.dedupe_key is None:
            self.dedupe_key = self.title

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "runbook_url": self.runbook_url,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
            "dedupe_key": self.dedupe_key,
        }


@dataclass
class AlertResult:
    """Result of alert sending operation.

    Attributes:
        success: Whether alert was sent successfully
        alert_id: Unique identifier of the alert
        suppressed: Whether alert was suppressed
        suppression_reason: Reason for suppression (if applicable)
        rate_limited: Whether alert was rate limited
        sent_at: When the alert was sent
        error: Error message if sending failed
    """

    success: bool
    alert_id: str
    suppressed: bool = False
    suppression_reason: str | None = None
    rate_limited: bool = False
    sent_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "alert_id": self.alert_id,
            "suppressed": self.suppressed,
            "suppression_reason": self.suppression_reason,
            "rate_limited": self.rate_limited,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error": self.error,
        }


# =============================================================================
# ALERT MANAGER
# =============================================================================


class AlertManager:
    """Centralized alert management with suppression and runbooks.

    Features:
    - Alert deduplication (same alert within time window)
    - Rate limiting per severity level
    - Maintenance window suppression
    - Runbook link integration
    - Multi-channel notification (n8n, Telegram)
    - Alert history tracking

    Attributes:
        n8n_webhook_url: n8n webhook URL for alerts
        telegram_chat_id: Telegram chat ID for notifications
        rate_limit_minutes: Rate limit per dedupe key
        maintenance_windows: Active maintenance windows
    """

    def __init__(
        self,
        n8n_webhook_url: str | None = None,
        telegram_chat_id: str | None = None,
        rate_limit_minutes: dict[str, int] | None = None,
    ):
        """Initialize alert manager.

        Args:
            n8n_webhook_url: n8n webhook URL for alert notifications
            telegram_chat_id: Telegram chat ID for direct notifications
            rate_limit_minutes: Rate limit per severity (default: critical=15, warning=60, info=1440)
        """
        self.n8n_webhook_url = n8n_webhook_url
        self.telegram_chat_id = telegram_chat_id

        # Default rate limits (minutes between alerts of same dedupe_key)
        self.rate_limit_minutes = rate_limit_minutes or {
            "critical": 15,  # Allow critical alerts every 15 minutes
            "warning": 60,  # Warnings every hour
            "info": 1440,  # Info once per day
        }

        # Maintenance windows
        self.maintenance_windows: list[MaintenanceWindow] = []

        # Alert history for deduplication
        self._alert_history: dict[str, datetime] = {}  # dedupe_key -> last_sent_time

    def add_maintenance_window(self, window: MaintenanceWindow) -> None:
        """Add a maintenance window for alert suppression.

        Args:
            window: Maintenance window configuration

        Example:
            >>> window = MaintenanceWindow(
            ...     start=datetime.now(UTC),
            ...     end=datetime.now(UTC) + timedelta(hours=2),
            ...     reason="Database migration"
            ... )
            >>> manager.add_maintenance_window(window)
        """
        self.maintenance_windows.append(window)
        logger.info(
            "Added maintenance window",
            extra={
                "start": window.start.isoformat(),
                "end": window.end.isoformat(),
                "reason": window.reason,
            },
        )

    def remove_expired_windows(self) -> int:
        """Remove expired maintenance windows.

        Returns:
            Number of windows removed
        """
        now = datetime.now(UTC)
        before_count = len(self.maintenance_windows)
        self.maintenance_windows = [w for w in self.maintenance_windows if w.end > now]
        removed = before_count - len(self.maintenance_windows)

        if removed > 0:
            logger.info(f"Removed {removed} expired maintenance windows")

        return removed

    def is_suppressed(self, severity: str) -> tuple[bool, str | None]:
        """Check if alerts should be suppressed.

        Args:
            severity: Alert severity level

        Returns:
            Tuple of (is_suppressed, reason)

        Example:
            >>> suppressed, reason = manager.is_suppressed("warning")
            >>> if suppressed:
            ...     print(f"Alert suppressed: {reason}")
        """
        now = datetime.now(UTC)

        # Remove expired windows
        self.remove_expired_windows()

        # Check active maintenance windows
        for window in self.maintenance_windows:
            if window.is_active(now):
                if window.suppress_all:
                    return True, f"Maintenance: {window.reason}"
                elif severity == "info":
                    return True, f"Info alerts suppressed during maintenance: {window.reason}"

        return False, None

    def should_rate_limit(self, dedupe_key: str, severity: str) -> bool:
        """Check if alert should be rate limited.

        Args:
            dedupe_key: Deduplication key
            severity: Alert severity

        Returns:
            True if alert should be rate limited
        """
        if dedupe_key not in self._alert_history:
            return False

        last_sent = self._alert_history[dedupe_key]
        limit_minutes = self.rate_limit_minutes.get(severity, 60)
        cooldown = timedelta(minutes=limit_minutes)

        return (datetime.now(UTC) - last_sent) < cooldown

    async def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        runbook_url: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        force: bool = False,
    ) -> AlertResult:
        """Send alert with suppression and rate limiting.

        Args:
            severity: Alert severity (info, warning, critical)
            title: Short alert title
            message: Detailed alert message
            runbook_url: URL to runbook documentation
            tags: Optional tags for categorization
            metadata: Additional metadata
            dedupe_key: Key for deduplication (default: title)
            force: Force send alert, bypassing suppression and rate limits

        Returns:
            AlertResult with send status

        Example:
            >>> result = await manager.send_alert(
            ...     severity="critical",
            ...     title="High Error Rate",
            ...     message="Error rate exceeds 5%",
            ...     runbook_url="https://docs.example.com/runbooks/high-error-rate"
            ... )
            >>> if result.success:
            ...     print(f"Alert sent: {result.alert_id}")
        """
        import uuid

        alert_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            title=title,
            message=message,
            runbook_url=runbook_url,
            timestamp=now,
            tags=tags or [],
            metadata=metadata or {},
            dedupe_key=dedupe_key,
        )

        # Check suppression
        if not force:
            suppressed, reason = self.is_suppressed(severity)
            if suppressed:
                logger.info(
                    "Alert suppressed",
                    extra={
                        "alert_id": alert_id,
                        "title": title,
                        "reason": reason,
                    },
                )
                return AlertResult(
                    success=False,
                    alert_id=alert_id,
                    suppressed=True,
                    suppression_reason=reason,
                )

            # Check rate limiting
            if self.should_rate_limit(alert.dedupe_key or title, severity):
                logger.info(
                    "Alert rate limited",
                    extra={
                        "alert_id": alert_id,
                        "title": title,
                        "dedupe_key": alert.dedupe_key,
                    },
                )
                return AlertResult(
                    success=False,
                    alert_id=alert_id,
                    rate_limited=True,
                )

        # Send alert
        try:
            sent = await self._send_to_n8n(alert)

            if sent:
                # Update alert history
                self._alert_history[alert.dedupe_key or title] = now

                logger.info(
                    "Alert sent successfully",
                    extra={
                        "alert_id": alert_id,
                        "severity": severity,
                        "title": title,
                    },
                )

                return AlertResult(
                    success=True,
                    alert_id=alert_id,
                    sent_at=now,
                )
            else:
                return AlertResult(
                    success=False,
                    alert_id=alert_id,
                    error="Failed to send to n8n",
                )

        except Exception as e:
            logger.error(
                f"Failed to send alert: {e}",
                exc_info=True,
                extra={"alert_id": alert_id, "title": title},
            )
            return AlertResult(
                success=False,
                alert_id=alert_id,
                error=str(e),
            )

    async def _send_to_n8n(self, alert: Alert) -> bool:
        """Send alert to n8n webhook.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully
        """
        if not self.n8n_webhook_url:
            logger.warning("n8n webhook URL not configured")
            return False

        # Build alert payload
        payload = {
            "alert_id": alert.alert_id,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "runbook_url": alert.runbook_url,
            "timestamp": alert.timestamp.isoformat(),
            "tags": alert.tags,
            "metadata": alert.metadata,
            "telegram_chat_id": self.telegram_chat_id,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.n8n_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )

                return response.status_code < 300

        except httpx.TimeoutException:
            logger.error("Alert webhook timeout")
            return False
        except httpx.HTTPError as e:
            logger.error(f"Alert webhook error: {e}")
            return False

    async def send_performance_alert(
        self,
        anomaly: Any,
        baseline_stats: dict[str, Any],
    ) -> AlertResult:
        """Send performance anomaly alert with runbook.

        Args:
            anomaly: Anomaly object from PerformanceBaseline
            baseline_stats: Baseline statistics dictionary

        Returns:
            AlertResult with send status

        Example:
            >>> from src.performance_baseline import PerformanceBaseline
            >>> baseline = PerformanceBaseline(database_url="...")
            >>> anomalies = await baseline.detect_anomalies()
            >>> for anomaly in anomalies:
            ...     result = await manager.send_performance_alert(
            ...         anomaly, await baseline.get_baseline_stats()
            ...     )
        """
        # Map metric names to runbook URLs
        runbook_mapping = {
            "latency_ms": "https://docs.example.com/runbooks/high-latency",
            "error_rate_pct": "https://docs.example.com/runbooks/high-error-rate",
            "cpu_percent": "https://docs.example.com/runbooks/high-cpu",
            "memory_percent": "https://docs.example.com/runbooks/high-memory",
            "throughput_rph": "https://docs.example.com/runbooks/low-throughput",
        }

        runbook_url = runbook_mapping.get(anomaly.metric_name)

        # Build detailed message
        if anomaly.metric_name in baseline_stats:
            baseline = baseline_stats[anomaly.metric_name]
            message = (
                f"**Performance Anomaly Detected**\n\n"
                f"Metric: {anomaly.metric_name}\n"
                f"Current: {anomaly.current_value:.2f}\n"
                f"Expected: {anomaly.expected_value:.2f} ± {baseline.stddev:.2f}\n"
                f"Deviation: {anomaly.deviation_stddev:.1f}σ\n"
                f"Severity: {anomaly.severity}\n\n"
                f"Baseline Statistics:\n"
                f"- P50: {baseline.median:.2f}\n"
                f"- P95: {baseline.p95:.2f}\n"
                f"- P99: {baseline.p99:.2f}\n"
                f"- Sample Count: {baseline.sample_count}"
            )
        else:
            message = anomaly.message

        return await self.send_alert(
            severity=anomaly.severity,
            title=f"Performance Anomaly: {anomaly.metric_name}",
            message=message,
            runbook_url=runbook_url,
            tags=["performance", "anomaly", anomaly.metric_name],
            metadata={
                "metric_name": anomaly.metric_name,
                "current_value": anomaly.current_value,
                "expected_value": anomaly.expected_value,
                "deviation_stddev": anomaly.deviation_stddev,
            },
            dedupe_key=f"performance_{anomaly.metric_name}",
        )

    def get_status(self) -> dict[str, Any]:
        """Get current alert manager status.

        Returns:
            Dictionary with status information

        Example:
            >>> status = manager.get_status()
            >>> print(f"Active windows: {status['active_maintenance_windows']}")
        """
        now = datetime.now(UTC)
        self.remove_expired_windows()

        active_windows = [w for w in self.maintenance_windows if w.is_active(now)]

        return {
            "n8n_configured": bool(self.n8n_webhook_url),
            "telegram_configured": bool(self.telegram_chat_id),
            "rate_limits": self.rate_limit_minutes,
            "active_maintenance_windows": len(active_windows),
            "maintenance_windows": [w.to_dict() for w in active_windows],
            "total_alerts_sent": len(self._alert_history),
            "alert_history_size": len(self._alert_history),
        }

    def clear_history(self) -> None:
        """Clear alert history (for testing or manual reset)."""
        self._alert_history.clear()
        logger.info("Alert history cleared")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_alert_manager(
    n8n_base_url: str | None = None,
    telegram_chat_id: str | None = None,
) -> AlertManager | None:
    """Create AlertManager with default configuration.

    Args:
        n8n_base_url: n8n instance URL (or from N8N_BASE_URL env var)
        telegram_chat_id: Telegram chat ID (or from TELEGRAM_CHAT_ID env var)

    Returns:
        AlertManager instance or None if configuration missing

    Example:
        >>> manager = create_alert_manager()
        >>> if manager:
        ...     await manager.send_alert(
        ...         severity="warning",
        ...         title="High Latency",
        ...         message="Latency exceeds baseline"
        ...     )
    """
    import os

    n8n_url = n8n_base_url or os.environ.get("N8N_BASE_URL")
    chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not n8n_url:
        logger.warning("AlertManager not fully configured: missing N8N_BASE_URL")
        # Still return manager for testing, but notifications won't work
        return AlertManager(telegram_chat_id=chat_id)

    webhook_url = f"{n8n_url.rstrip('/')}/webhook/alerts"

    return AlertManager(
        n8n_webhook_url=webhook_url,
        telegram_chat_id=chat_id,
    )
