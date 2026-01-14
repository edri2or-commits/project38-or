"""Railway Cost Monitoring Module.

This module provides cost tracking and analysis for Railway deployments.
Implements Week 2 of the Post-Launch Maintenance plan:
- Track Railway resource usage
- Estimate costs based on usage
- Generate cost reports
- Trigger alerts when thresholds are exceeded

Railway Pricing (2026):
- Hobby Plan: $5/month + usage
- Pro Plan: $20/month + usage
- Usage: $0.000231/vCPU-minute, $0.000231/GB-minute RAM

Example:
    >>> from src.cost_monitor import CostMonitor, RailwayPricing
    >>> from src.railway_client import RailwayClient
    >>>
    >>> client = RailwayClient(api_token="...")
    >>> monitor = CostMonitor(railway_client=client)
    >>>
    >>> # Get current month cost estimate
    >>> cost = await monitor.get_current_month_cost()
    >>> print(f"Estimated cost: ${cost.total_cost:.2f}")
    >>>
    >>> # Check if budget exceeded
    >>> if await monitor.is_budget_exceeded(budget=50.0):
    ...     print("WARNING: Budget exceeded!")
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# PRICING CONFIGURATION
# =============================================================================


@dataclass
class RailwayPricing:
    """Railway pricing configuration (2026 rates).

    Based on: https://railway.app/pricing

    Attributes:
        base_monthly_cost: Fixed monthly cost for plan
        vcpu_per_minute: Cost per vCPU-minute
        memory_per_gb_minute: Cost per GB-minute of RAM
        egress_per_gb: Cost per GB of outbound traffic
        plan_name: Name of the pricing plan
    """

    base_monthly_cost: float
    vcpu_per_minute: float
    memory_per_gb_minute: float
    egress_per_gb: float
    plan_name: str

    @classmethod
    def hobby(cls) -> "RailwayPricing":
        """Hobby plan pricing."""
        return cls(
            base_monthly_cost=5.0,
            vcpu_per_minute=0.000231,
            memory_per_gb_minute=0.000231,
            egress_per_gb=0.10,
            plan_name="Hobby",
        )

    @classmethod
    def pro(cls) -> "RailwayPricing":
        """Pro plan pricing."""
        return cls(
            base_monthly_cost=20.0,
            vcpu_per_minute=0.000231,
            memory_per_gb_minute=0.000231,
            egress_per_gb=0.10,
            plan_name="Pro",
        )


@dataclass
class CostEstimate:
    """Cost estimate for a time period.

    Attributes:
        period_start: Start of the measurement period
        period_end: End of the measurement period
        vcpu_minutes: Total vCPU-minutes used
        memory_gb_minutes: Total GB-minutes of RAM used
        egress_gb: Total outbound traffic in GB
        vcpu_cost: Cost from vCPU usage
        memory_cost: Cost from memory usage
        egress_cost: Cost from egress traffic
        base_cost: Fixed plan cost (prorated for period)
        total_cost: Sum of all costs
        currency: Currency code (USD)
    """

    period_start: datetime
    period_end: datetime
    vcpu_minutes: float
    memory_gb_minutes: float
    egress_gb: float
    vcpu_cost: float
    memory_cost: float
    egress_cost: float
    base_cost: float
    total_cost: float
    currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "usage": {
                "vcpu_minutes": round(self.vcpu_minutes, 2),
                "memory_gb_minutes": round(self.memory_gb_minutes, 2),
                "egress_gb": round(self.egress_gb, 4),
            },
            "costs": {
                "vcpu": round(self.vcpu_cost, 4),
                "memory": round(self.memory_cost, 4),
                "egress": round(self.egress_cost, 4),
                "base": round(self.base_cost, 2),
                "total": round(self.total_cost, 2),
            },
            "currency": self.currency,
        }


@dataclass
class UsageSnapshot:
    """Point-in-time usage snapshot.

    Attributes:
        timestamp: When the snapshot was taken
        service_name: Name of the Railway service
        cpu_percent: Current CPU utilization (0-100)
        memory_mb: Current memory usage in MB
        request_count: Total requests since deployment
    """

    timestamp: datetime
    service_name: str
    cpu_percent: float
    memory_mb: float
    request_count: int


# =============================================================================
# COST MONITOR
# =============================================================================


class CostMonitor:
    """Railway cost monitoring and alerting.

    Tracks resource usage and estimates costs based on Railway's
    pricing model. Supports budget alerts and cost optimization
    recommendations.

    Example:
        >>> monitor = CostMonitor(
        ...     railway_client=client,
        ...     pricing=RailwayPricing.hobby()
        ... )
        >>> cost = await monitor.get_current_month_cost()
        >>> print(f"Month-to-date: ${cost.total_cost:.2f}")
    """

    def __init__(
        self,
        railway_client: Any,
        pricing: RailwayPricing | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
    ):
        """Initialize cost monitor.

        Args:
            railway_client: RailwayClient instance for API calls
            pricing: Pricing configuration (defaults to Hobby)
            project_id: Railway project ID (optional, uses env var)
            environment_id: Railway environment ID (optional, uses env var)
        """
        self.client = railway_client
        self.pricing = pricing or RailwayPricing.hobby()
        self.project_id = project_id
        self.environment_id = environment_id

        # Usage history for trend analysis
        self._usage_history: list[UsageSnapshot] = []
        self._max_history_size = 1440  # 24 hours at 1-minute intervals

    async def get_current_usage(self, deployment_id: str) -> UsageSnapshot:
        """Get current resource usage for a deployment.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            UsageSnapshot with current CPU, memory, request stats
        """
        metrics = await self.client.get_deployment_metrics(deployment_id)

        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            service_name=deployment_id,
            cpu_percent=metrics.get("cpuUsage", 0) or 0,
            memory_mb=metrics.get("memoryUsage", 0) or 0,
            request_count=metrics.get("requestCount", 0) or 0,
        )

        # Store in history
        self._usage_history.append(snapshot)
        if len(self._usage_history) > self._max_history_size:
            self._usage_history.pop(0)

        return snapshot

    def estimate_cost(
        self,
        vcpu_minutes: float,
        memory_gb_minutes: float,
        egress_gb: float = 0.0,
        period_days: float = 30.0,
    ) -> CostEstimate:
        """Estimate cost for given usage.

        Args:
            vcpu_minutes: Total vCPU-minutes consumed
            memory_gb_minutes: Total GB-minutes of memory
            egress_gb: Total outbound traffic in GB
            period_days: Number of days in the period (for base cost proration)

        Returns:
            CostEstimate with detailed cost breakdown
        """
        now = datetime.now(UTC)

        # Calculate component costs
        vcpu_cost = vcpu_minutes * self.pricing.vcpu_per_minute
        memory_cost = memory_gb_minutes * self.pricing.memory_per_gb_minute
        egress_cost = egress_gb * self.pricing.egress_per_gb

        # Prorate base cost for the period
        base_cost = self.pricing.base_monthly_cost * (period_days / 30.0)

        total_cost = base_cost + vcpu_cost + memory_cost + egress_cost

        return CostEstimate(
            period_start=now - timedelta(days=period_days),
            period_end=now,
            vcpu_minutes=vcpu_minutes,
            memory_gb_minutes=memory_gb_minutes,
            egress_gb=egress_gb,
            vcpu_cost=vcpu_cost,
            memory_cost=memory_cost,
            egress_cost=egress_cost,
            base_cost=base_cost,
            total_cost=total_cost,
        )

    async def get_current_month_cost(self, deployment_id: str) -> CostEstimate:
        """Estimate cost for current month based on usage patterns.

        Uses current resource usage to project monthly cost. This is
        an estimate based on current consumption rate.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            CostEstimate projected for the full month

        Note:
            This is an estimate. Actual billing may differ based on
            usage fluctuations throughout the month.
        """
        # Get current usage
        current = await self.get_current_usage(deployment_id)

        # Calculate days elapsed this month
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        days_elapsed = (now - month_start).days + 1
        days_in_month = 30.0  # Approximation

        # Project usage for full month
        # Assuming current usage rate continues
        hours_running = days_elapsed * 24
        minutes_running = hours_running * 60

        # Estimate vCPU-minutes (assuming 1 vCPU at current utilization)
        avg_vcpu = current.cpu_percent / 100.0  # Convert to vCPU fraction
        vcpu_minutes_used = avg_vcpu * minutes_running
        vcpu_minutes_projected = vcpu_minutes_used * (days_in_month / days_elapsed)

        # Estimate memory GB-minutes
        memory_gb = current.memory_mb / 1024.0
        memory_gb_minutes_used = memory_gb * minutes_running
        memory_gb_minutes_projected = memory_gb_minutes_used * (days_in_month / days_elapsed)

        # Egress estimate (conservative: 1GB/day based on typical usage)
        egress_gb_projected = days_in_month * 1.0

        return self.estimate_cost(
            vcpu_minutes=vcpu_minutes_projected,
            memory_gb_minutes=memory_gb_minutes_projected,
            egress_gb=egress_gb_projected,
            period_days=days_in_month,
        )

    async def is_budget_exceeded(self, deployment_id: str, budget: float) -> tuple[bool, float]:
        """Check if projected cost exceeds budget.

        Args:
            deployment_id: Railway deployment ID
            budget: Monthly budget in USD

        Returns:
            Tuple of (exceeded: bool, projected_cost: float)
        """
        estimate = await self.get_current_month_cost(deployment_id)
        exceeded = estimate.total_cost > budget
        return exceeded, estimate.total_cost

    def get_cost_optimization_recommendations(
        self, current_usage: UsageSnapshot
    ) -> list[dict[str, str]]:
        """Generate cost optimization recommendations.

        Analyzes current usage and provides actionable recommendations
        to reduce costs.

        Args:
            current_usage: Current resource usage snapshot

        Returns:
            List of recommendations with priority and description
        """
        recommendations = []

        # Check CPU utilization
        if current_usage.cpu_percent < 10:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "cpu",
                    "title": "Consider reducing vCPU allocation",
                    "description": (
                        f"CPU usage is only {current_usage.cpu_percent:.1f}%. "
                        "Consider reducing allocated vCPUs or using a smaller instance."
                    ),
                    "potential_savings": "20-40%",
                }
            )
        elif current_usage.cpu_percent > 80:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "cpu",
                    "title": "Consider scaling up to prevent throttling",
                    "description": (
                        f"CPU usage is {current_usage.cpu_percent:.1f}%. "
                        "High utilization may cause performance issues."
                    ),
                    "potential_savings": "N/A (performance)",
                }
            )

        # Check memory utilization
        if current_usage.memory_mb < 256:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "memory",
                    "title": "Consider reducing memory allocation",
                    "description": (
                        f"Memory usage is only {current_usage.memory_mb:.0f}MB. "
                        "Consider reducing allocated memory."
                    ),
                    "potential_savings": "10-30%",
                }
            )

        # General recommendations
        if not recommendations:
            recommendations.append(
                {
                    "priority": "low",
                    "category": "general",
                    "title": "Resource usage is optimized",
                    "description": (
                        "Current resource allocation appears well-matched to usage. "
                        "Continue monitoring for changes."
                    ),
                    "potential_savings": "0%",
                }
            )

        return recommendations

    def get_usage_trend(self, metric: str = "cpu", hours: int = 1) -> dict[str, float]:
        """Analyze usage trends from history.

        Args:
            metric: Metric to analyze ('cpu' or 'memory')
            hours: Number of hours to analyze

        Returns:
            Dictionary with min, max, avg, and trend direction
        """
        if not self._usage_history:
            return {"min": 0, "max": 0, "avg": 0, "trend": "stable"}

        # Filter to requested time window
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        recent = [s for s in self._usage_history if s.timestamp >= cutoff]

        if not recent:
            return {"min": 0, "max": 0, "avg": 0, "trend": "stable"}

        # Get values for the metric
        if metric == "cpu":
            values = [s.cpu_percent for s in recent]
        else:
            values = [s.memory_mb for s in recent]

        # Calculate statistics
        avg_value = sum(values) / len(values)

        # Determine trend (compare first half to second half)
        midpoint = len(values) // 2
        if midpoint > 0:
            first_half_avg = sum(values[:midpoint]) / midpoint
            second_half_avg = sum(values[midpoint:]) / (len(values) - midpoint)

            if second_half_avg > first_half_avg * 1.1:
                trend = "increasing"
            elif second_half_avg < first_half_avg * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "min": min(values),
            "max": max(values),
            "avg": avg_value,
            "trend": trend,
        }

    def generate_cost_report(
        self, estimate: CostEstimate, include_recommendations: bool = True
    ) -> dict[str, Any]:
        """Generate a comprehensive cost report.

        Args:
            estimate: Cost estimate to report on
            include_recommendations: Whether to include optimization tips

        Returns:
            Dictionary containing full cost report
        """
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "pricing_plan": self.pricing.plan_name,
            "estimate": estimate.to_dict(),
            "budget_status": {
                "warning_threshold": 40.0,  # 80% of $50 default budget
                "alert_threshold": 50.0,
                "current_projected": estimate.total_cost,
                "status": (
                    "ok"
                    if estimate.total_cost < 40
                    else "warning"
                    if estimate.total_cost < 50
                    else "alert"
                ),
            },
        }

        if include_recommendations and self._usage_history:
            latest = self._usage_history[-1] if self._usage_history else None
            if latest:
                report["recommendations"] = self.get_cost_optimization_recommendations(latest)
                report["trends"] = {
                    "cpu": self.get_usage_trend("cpu"),
                    "memory": self.get_usage_trend("memory"),
                }

        return report


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def format_cost(amount: float, currency: str = "USD") -> str:
    """Format cost as currency string.

    Args:
        amount: Cost amount
        currency: Currency code

    Returns:
        Formatted string (e.g., "$12.34")
    """
    if currency == "USD":
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency}"


def estimate_monthly_from_daily(daily_cost: float, days_elapsed: int = 1) -> float:
    """Project monthly cost from daily usage.

    Args:
        daily_cost: Cost for the observed period
        days_elapsed: Number of days observed

    Returns:
        Projected monthly cost
    """
    daily_average = daily_cost / days_elapsed
    return daily_average * 30.0
