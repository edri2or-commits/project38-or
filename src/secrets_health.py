"""Secrets health monitoring and alerting.

Monitors GCP Secret Manager access health and sends alerts on failures.
Implements CRITICAL-4: WIF monitoring with alerting.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class SecretAccessMetrics:
    """Metrics for secret access attempts."""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    last_success_time: float | None = None
    last_failure_time: float | None = None
    last_failure_reason: str | None = None
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_attempts == 0:
            return 100.0
        return (self.successful_attempts / self.total_attempts) * 100

    @property
    def status(self) -> HealthStatus:
        """Determine health status based on metrics."""
        if self.consecutive_failures >= 3:
            return HealthStatus.UNHEALTHY
        if self.consecutive_failures >= 1 or self.success_rate < 90:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


@dataclass
class WIFHealthMonitor:
    """Monitor Workload Identity Federation health.

    Tracks GCP Secret Manager access and alerts on failures.
    """

    metrics: SecretAccessMetrics = field(default_factory=SecretAccessMetrics)
    alert_webhook_url: str | None = None
    alert_cooldown_seconds: int = 300  # 5 minutes between alerts
    _last_alert_time: float = 0

    def __post_init__(self):
        """Initialize with environment config."""
        self.alert_webhook_url = os.environ.get("N8N_ALERT_WEBHOOK_URL")

    def record_success(self, secret_name: str) -> None:
        """Record a successful secret access.

        Args:
            secret_name: Name of the accessed secret (not logged for security).
        """
        self.metrics.total_attempts += 1
        self.metrics.successful_attempts += 1
        self.metrics.last_success_time = time.time()
        self.metrics.consecutive_failures = 0
        logger.debug("Secret access successful")

    def record_failure(self, secret_name: str, reason: str) -> None:
        """Record a failed secret access and potentially alert.

        Args:
            secret_name: Name of the secret (not logged for security).
            reason: Failure reason (safe to log).
        """
        self.metrics.total_attempts += 1
        self.metrics.failed_attempts += 1
        self.metrics.last_failure_time = time.time()
        self.metrics.last_failure_reason = reason
        self.metrics.consecutive_failures += 1

        logger.warning(
            f"Secret access failed: {reason}. "
            f"Consecutive failures: {self.metrics.consecutive_failures}"
        )

        # Check if alert should be sent
        if self._should_alert():
            asyncio.create_task(self._send_alert(reason))

    def _should_alert(self) -> bool:
        """Determine if an alert should be sent."""
        if self.metrics.consecutive_failures < 2:
            return False

        current_time = time.time()
        if current_time - self._last_alert_time < self.alert_cooldown_seconds:
            return False

        return True

    async def _send_alert(self, reason: str) -> None:
        """Send alert via n8n webhook.

        Args:
            reason: Failure reason to include in alert.
        """
        self._last_alert_time = time.time()

        if not self.alert_webhook_url:
            logger.error(
                "WIF ALERT: GCP authentication failing! "
                f"Reason: {reason}. "
                f"Consecutive failures: {self.metrics.consecutive_failures}. "
                "No webhook configured for external alerting."
            )
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    self.alert_webhook_url,
                    json={
                        "alert_type": "wif_failure",
                        "severity": "critical",
                        "message": f"GCP WIF authentication failing: {reason}",
                        "metrics": {
                            "consecutive_failures": self.metrics.consecutive_failures,
                            "success_rate": self.metrics.success_rate,
                            "total_attempts": self.metrics.total_attempts,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                logger.info("WIF failure alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send WIF alert: {type(e).__name__}")

    def get_health_report(self) -> dict:
        """Get comprehensive health report.

        Returns:
            Dict with health status and metrics.
        """
        return {
            "status": self.metrics.status.value,
            "metrics": {
                "total_attempts": self.metrics.total_attempts,
                "successful_attempts": self.metrics.successful_attempts,
                "failed_attempts": self.metrics.failed_attempts,
                "success_rate_percent": round(self.metrics.success_rate, 2),
                "consecutive_failures": self.metrics.consecutive_failures,
                "last_success": (
                    datetime.fromtimestamp(self.metrics.last_success_time).isoformat()
                    if self.metrics.last_success_time
                    else None
                ),
                "last_failure": (
                    datetime.fromtimestamp(self.metrics.last_failure_time).isoformat()
                    if self.metrics.last_failure_time
                    else None
                ),
                "last_failure_reason": self.metrics.last_failure_reason,
            },
            "alerting": {
                "webhook_configured": bool(self.alert_webhook_url),
                "cooldown_seconds": self.alert_cooldown_seconds,
            },
        }

    async def check_wif_health(self) -> dict:
        """Perform active health check of WIF authentication.

        Returns:
            Dict with health check results.
        """
        from src.secrets_manager import SecretManager

        try:
            manager = SecretManager()
            # Try to list secrets (doesn't expose values)
            secrets = manager.list_secrets()

            if secrets:
                self.record_success("health_check")
                return {
                    "wif_status": "healthy",
                    "secrets_accessible": True,
                    "secrets_count": len(secrets),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                self.record_failure("health_check", "No secrets returned")
                return {
                    "wif_status": "degraded",
                    "secrets_accessible": False,
                    "error": "No secrets returned - possible WIF issue",
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            error_type = type(e).__name__
            self.record_failure("health_check", error_type)
            return {
                "wif_status": "unhealthy",
                "secrets_accessible": False,
                "error": f"WIF authentication failed: {error_type}",
                "timestamp": datetime.utcnow().isoformat(),
            }


# Global monitor instance
_monitor: WIFHealthMonitor | None = None


def get_wif_monitor() -> WIFHealthMonitor:
    """Get the global WIF health monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = WIFHealthMonitor()
    return _monitor
