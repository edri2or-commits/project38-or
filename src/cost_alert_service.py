"""Cost Alert Service - Integrates Cost Monitor with n8n Notifications.

This service monitors Railway costs and triggers n8n workflows
when budget thresholds are exceeded.

Example:
    >>> from src.cost_alert_service import CostAlertService
    >>> from src.cost_monitor import CostMonitor
    >>>
    >>> service = CostAlertService(
    ...     cost_monitor=monitor,
    ...     n8n_webhook_url="https://n8n.railway.app/webhook/cost-alert"
    ... )
    >>>
    >>> # Check and send alerts
    >>> result = await service.check_and_alert(
    ...     deployment_id="abc123",
    ...     budget=50.0
    ... )
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from src.workflows.cost_alert_workflow import (
    create_alert_payload,
    get_severity_from_percentage,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class AlertResult:
    """Result of alert check and notification.

    Attributes:
        alert_sent: Whether an alert was sent
        severity: Alert severity (critical, warning, info)
        budget: Monthly budget
        projected_cost: Projected monthly cost
        percentage_used: Percentage of budget used
        message: Status message
        timestamp: When the check was performed
    """

    alert_sent: bool
    severity: str
    budget: float
    projected_cost: float
    percentage_used: float
    message: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_sent": self.alert_sent,
            "severity": self.severity,
            "budget": self.budget,
            "projected_cost": self.projected_cost,
            "percentage_used": self.percentage_used,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# COST ALERT SERVICE
# =============================================================================


class CostAlertService:
    """Service for monitoring costs and sending alerts.

    Integrates CostMonitor with n8n webhooks to provide automated
    cost alerting via Telegram.

    Features:
    - Automatic severity detection (critical/warning/info)
    - Configurable alert thresholds
    - Rate limiting to prevent alert spam
    - Detailed alert payloads with recommendations

    Attributes:
        cost_monitor: CostMonitor instance for getting cost data
        n8n_webhook_url: URL for n8n cost-alert webhook
        warning_threshold: Percentage threshold for warnings (default: 80)
        critical_threshold: Percentage threshold for critical (default: 100)
    """

    def __init__(
        self,
        cost_monitor: Any,
        n8n_webhook_url: str,
        warning_threshold: float = 80.0,
        critical_threshold: float = 100.0,
    ):
        """Initialize cost alert service.

        Args:
            cost_monitor: CostMonitor instance
            n8n_webhook_url: n8n webhook URL for cost alerts
            warning_threshold: Percentage threshold for warning alerts
            critical_threshold: Percentage threshold for critical alerts
        """
        self.cost_monitor = cost_monitor
        self.n8n_webhook_url = n8n_webhook_url
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

        # Rate limiting: track last alert time per severity
        self._last_alert: dict[str, datetime] = {}
        self._alert_cooldown_minutes = {
            "critical": 15,  # Alert every 15 minutes for critical
            "warning": 60,  # Alert every hour for warnings
            "info": 1440,  # Alert once per day for info
        }

    async def check_and_alert(
        self,
        deployment_id: str,
        budget: float,
        force: bool = False,
    ) -> AlertResult:
        """Check costs and send alert if thresholds exceeded.

        Args:
            deployment_id: Railway deployment ID
            budget: Monthly budget in USD
            force: Force send alert regardless of rate limiting

        Returns:
            AlertResult with check details and alert status

        Example:
            >>> result = await service.check_and_alert(
            ...     deployment_id="abc123",
            ...     budget=50.0
            ... )
            >>> if result.alert_sent:
            ...     print(f"Alert sent: {result.severity}")
        """
        now = datetime.now(UTC)

        # Get current cost estimate
        exceeded, projected_cost = await self.cost_monitor.is_budget_exceeded(
            deployment_id, budget
        )

        percentage_used = round((projected_cost / budget) * 100, 1)
        severity = get_severity_from_percentage(percentage_used)

        # Check rate limiting
        should_alert = force or self._should_send_alert(severity, now)

        if not should_alert:
            return AlertResult(
                alert_sent=False,
                severity=severity,
                budget=budget,
                projected_cost=projected_cost,
                percentage_used=percentage_used,
                message=f"Alert rate limited (last: {self._last_alert.get(severity, 'never')})",
                timestamp=now,
            )

        # Get recommendations if available
        try:
            usage = await self.cost_monitor.get_current_usage(deployment_id)
            recommendations = self.cost_monitor.get_cost_optimization_recommendations(
                usage
            )
            recommendations_text = "\n".join(
                [f"• {r['title']}" for r in recommendations[:3]]
            )
        except Exception:
            recommendations_text = "Unable to fetch recommendations"

        # Create and send alert
        payload = create_alert_payload(
            severity=severity,
            budget=budget,
            projected_cost=projected_cost,
            percentage_used=percentage_used,
            status="alert" if exceeded else "ok",
            recommendations=recommendations_text,
        )

        try:
            alert_sent = await self._send_alert(payload)
            if alert_sent:
                self._last_alert[severity] = now
                message = "Alert sent to Telegram via n8n"
            else:
                message = "Failed to send alert"
        except Exception as e:
            alert_sent = False
            message = f"Error sending alert: {e}"
            logger.error(f"Failed to send cost alert: {e}")

        return AlertResult(
            alert_sent=alert_sent,
            severity=severity,
            budget=budget,
            projected_cost=projected_cost,
            percentage_used=percentage_used,
            message=message,
            timestamp=now,
        )

    def _should_send_alert(self, severity: str, now: datetime) -> bool:
        """Check if alert should be sent based on rate limiting.

        Args:
            severity: Alert severity
            now: Current timestamp

        Returns:
            True if alert should be sent
        """
        if severity not in self._last_alert:
            return True

        last_alert = self._last_alert[severity]
        cooldown_minutes = self._alert_cooldown_minutes.get(severity, 60)

        from datetime import timedelta

        return (now - last_alert) >= timedelta(minutes=cooldown_minutes)

    async def _send_alert(self, payload: dict[str, Any]) -> bool:
        """Send alert to n8n webhook.

        Args:
            payload: Alert payload

        Returns:
            True if alert sent successfully
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.n8n_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )

                if response.status_code < 300:
                    logger.info(
                        "Cost alert sent successfully",
                        extra={
                            "severity": payload.get("severity"),
                            "projected_cost": payload.get("projected_cost"),
                        },
                    )
                    return True
                else:
                    logger.warning(
                        f"Cost alert failed: HTTP {response.status_code}",
                        extra={"response": response.text[:200]},
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Cost alert timeout: n8n webhook did not respond")
            return False
        except httpx.HTTPError as e:
            logger.error(f"Cost alert HTTP error: {e}")
            return False

    async def send_weekly_report(
        self,
        deployment_id: str,
        budget: float,
    ) -> AlertResult:
        """Send weekly cost summary report.

        Sends an info-level alert with current cost status,
        regardless of threshold status.

        Args:
            deployment_id: Railway deployment ID
            budget: Monthly budget in USD

        Returns:
            AlertResult with report status
        """
        return await self.check_and_alert(
            deployment_id=deployment_id,
            budget=budget,
            force=True,  # Always send weekly report
        )

    def reset_rate_limits(self) -> None:
        """Reset rate limiting state.

        Use this to force alerts to be sent immediately.
        """
        self._last_alert.clear()
        logger.info("Cost alert rate limits reset")

    def get_alert_status(self) -> dict[str, Any]:
        """Get current alert rate limiting status.

        Returns:
            Dictionary with last alert times and cooldowns
        """
        return {
            "last_alerts": {
                k: v.isoformat() for k, v in self._last_alert.items()
            },
            "cooldowns": self._alert_cooldown_minutes,
            "webhook_url": self.n8n_webhook_url,
            "thresholds": {
                "warning": self.warning_threshold,
                "critical": self.critical_threshold,
            },
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_cost_alert_service(
    n8n_base_url: str | None = None,
    railway_api_token: str | None = None,
) -> CostAlertService | None:
    """Create CostAlertService with default configuration.

    Args:
        n8n_base_url: n8n instance URL (or from N8N_BASE_URL env var)
        railway_api_token: Railway API token (or from RAILWAY_API_TOKEN env var)

    Returns:
        CostAlertService instance or None if configuration missing

    Example:
        >>> service = create_cost_alert_service()
        >>> if service:
        ...     result = await service.check_and_alert("deploy-id", 50.0)
    """
    import os

    n8n_url = n8n_base_url or os.environ.get("N8N_BASE_URL")
    railway_token = railway_api_token or os.environ.get("RAILWAY_API_TOKEN")

    if not n8n_url or not railway_token:
        logger.warning(
            "CostAlertService not configured: missing N8N_BASE_URL or RAILWAY_API_TOKEN"
        )
        return None

    # Import here to avoid circular imports
    from src.cost_monitor import CostMonitor, RailwayPricing
    from src.railway_client import RailwayClient

    railway_client = RailwayClient(api_token=railway_token)
    cost_monitor = CostMonitor(
        railway_client=railway_client,
        pricing=RailwayPricing.hobby(),
    )

    webhook_url = f"{n8n_url.rstrip('/')}/webhook/cost-alert"

    return CostAlertService(
        cost_monitor=cost_monitor,
        n8n_webhook_url=webhook_url,
    )
