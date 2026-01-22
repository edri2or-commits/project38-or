"""ActivityLog model for Night Watch operations.

This module defines the ActivityLog entity schema using SQLModel.
Stores all autonomous activities performed by Night Watch for
morning summary generation and audit trails.
"""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class ActivityType(str, Enum):
    """Types of activities that Night Watch can perform."""

    HEALTH_CHECK = "health_check"
    ANOMALY_DETECTED = "anomaly_detected"
    SELF_HEALING = "self_healing"
    METRIC_COLLECTION = "metric_collection"
    ALERT_SENT = "alert_sent"
    DEPLOYMENT = "deployment"
    ROLLBACK = "rollback"
    ERROR = "error"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"


class ActivitySeverity(str, Enum):
    """Severity levels for activities."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActivityLog(SQLModel, table=True):
    """Database model for Night Watch activity logging.

    Records all autonomous activities performed during night hours
    to enable morning summary generation and audit trails.

    Attributes:
        id: Primary key
        activity_type: Type of activity (health_check, anomaly_detected, etc.)
        severity: Severity level (info, warning, error, critical)
        service_name: Which service was affected (if applicable)
        description: Human-readable description of the activity
        details: JSON-serializable details dict (stored as string)
        success: Whether the activity completed successfully
        duration_ms: How long the activity took
        created_at: When the activity occurred

    Example:
        >>> log = ActivityLog(
        ...     activity_type=ActivityType.HEALTH_CHECK,
        ...     severity=ActivitySeverity.INFO,
        ...     service_name="main-api",
        ...     description="Health check passed",
        ...     success=True,
        ...     duration_ms=150
        ... )
    """

    __tablename__ = "activity_log"

    id: int | None = Field(default=None, primary_key=True)
    activity_type: str = Field(index=True, description="Type of activity")
    severity: str = Field(default="info", index=True, description="Severity level")
    service_name: str | None = Field(default=None, index=True, description="Affected service")
    description: str = Field(description="Human-readable description")
    details: str | None = Field(default=None, description="JSON details string")
    success: bool = Field(default=True, description="Whether activity succeeded")
    duration_ms: int | None = Field(default=None, description="Duration in milliseconds")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    class Config:
        """SQLModel configuration."""

        extra = "forbid"


class NightWatchSummary(SQLModel):
    """Summary of Night Watch activities for morning report.

    Not a database table - generated from ActivityLog aggregation.

    Attributes:
        period_start: Start of the night watch period
        period_end: End of the night watch period
        total_activities: Total number of activities logged
        health_checks_passed: Number of successful health checks
        health_checks_failed: Number of failed health checks
        anomalies_detected: Number of anomalies found
        self_healing_actions: Number of automatic fixes applied
        alerts_sent: Number of alerts dispatched
        critical_events: List of critical events that occurred
        services_affected: List of services that had issues
        overall_status: Overall system status during the night
    """

    period_start: datetime
    period_end: datetime
    total_activities: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    anomalies_detected: int = 0
    self_healing_actions: int = 0
    alerts_sent: int = 0
    critical_events: list[str] = []
    services_affected: list[str] = []
    overall_status: str = "healthy"  # healthy, degraded, critical


class NightWatchConfig(SQLModel):
    """Configuration for Night Watch behavior.

    Not a database table - loaded from environment or config.

    Attributes:
        enabled: Whether Night Watch is active
        night_start_hour: Hour to start night operations (UTC)
        night_end_hour: Hour to end night operations (UTC)
        health_check_interval_minutes: How often to check health
        telegram_chat_id: Chat ID for morning summaries
        enable_self_healing: Whether to auto-fix issues
        max_healing_actions_per_hour: Safety limit on auto-fixes
    """

    enabled: bool = True
    night_start_hour: int = 0  # 00:00 UTC
    night_end_hour: int = 6  # 06:00 UTC
    health_check_interval_minutes: int = 60
    telegram_chat_id: int | None = None
    enable_self_healing: bool = True
    max_healing_actions_per_hour: int = 3
