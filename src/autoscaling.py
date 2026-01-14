"""Auto-Scaling Recommendations Module.

Provides intelligent scaling recommendations based on resource usage patterns.
Analyzes CPU, memory, and request metrics to suggest optimal resource allocation.

Example:
    >>> from src.autoscaling import AutoScalingAdvisor
    >>> from src.cost_monitor import CostMonitor
    >>>
    >>> advisor = AutoScalingAdvisor(cost_monitor=monitor)
    >>> recommendations = await advisor.analyze_and_recommend("deployment-id")
    >>> for rec in recommendations:
    ...     print(f"{rec.priority}: {rec.action}")
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================


class ScalingDirection(Enum):
    """Scaling direction options."""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


class ResourceType(Enum):
    """Types of resources that can be scaled."""

    CPU = "cpu"
    MEMORY = "memory"
    INSTANCES = "instances"


class RecommendationPriority(Enum):
    """Priority levels for recommendations."""

    CRITICAL = "critical"  # Immediate action needed
    HIGH = "high"  # Should act soon
    MEDIUM = "medium"  # Consider acting
    LOW = "low"  # Optional optimization
    INFO = "info"  # Informational only


@dataclass
class ResourceMetrics:
    """Current resource utilization metrics.

    Attributes:
        cpu_percent: Current CPU utilization (0-100)
        memory_mb: Current memory usage in MB
        memory_percent: Memory usage as percentage
        request_rate: Requests per second
        response_time_ms: Average response time in ms
        error_rate: Error rate percentage
        timestamp: When metrics were collected
    """

    cpu_percent: float
    memory_mb: float
    memory_percent: float
    request_rate: float
    response_time_ms: float
    error_rate: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_mb, 2),
            "memory_percent": round(self.memory_percent, 2),
            "request_rate": round(self.request_rate, 2),
            "response_time_ms": round(self.response_time_ms, 2),
            "error_rate": round(self.error_rate, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ScalingRecommendation:
    """A scaling recommendation.

    Attributes:
        resource: Type of resource to scale
        direction: Scale up, down, or no change
        priority: Recommendation priority
        current_value: Current resource allocation
        recommended_value: Recommended allocation
        reason: Why this change is recommended
        impact: Expected impact of the change
        estimated_savings: Estimated cost savings (if scaling down)
    """

    resource: ResourceType
    direction: ScalingDirection
    priority: RecommendationPriority
    current_value: float
    recommended_value: float
    reason: str
    impact: str
    estimated_savings: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource": self.resource.value,
            "direction": self.direction.value,
            "priority": self.priority.value,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "reason": self.reason,
            "impact": self.impact,
            "estimated_savings": round(self.estimated_savings, 2),
        }


@dataclass
class ScalingReport:
    """Complete auto-scaling analysis report.

    Attributes:
        generated_at: Report generation timestamp
        deployment_id: Railway deployment ID
        current_metrics: Current resource metrics
        recommendations: List of scaling recommendations
        overall_status: Overall health status
        estimated_monthly_savings: Total potential savings
    """

    generated_at: datetime
    deployment_id: str
    current_metrics: ResourceMetrics
    recommendations: list[ScalingRecommendation] = field(default_factory=list)
    overall_status: str = "healthy"
    estimated_monthly_savings: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "deployment_id": self.deployment_id,
            "current_metrics": self.current_metrics.to_dict(),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "overall_status": self.overall_status,
            "estimated_monthly_savings": round(self.estimated_monthly_savings, 2),
            "recommendation_count": len(self.recommendations),
        }


# =============================================================================
# SCALING THRESHOLDS
# =============================================================================


@dataclass
class ScalingThresholds:
    """Configurable thresholds for scaling decisions.

    Attributes:
        cpu_scale_up: CPU % above which to scale up
        cpu_scale_down: CPU % below which to scale down
        memory_scale_up: Memory % above which to scale up
        memory_scale_down: Memory % below which to scale down
        response_time_critical: Response time (ms) considered critical
        response_time_warning: Response time (ms) considered warning
        error_rate_critical: Error rate % considered critical
        error_rate_warning: Error rate % considered warning
    """

    cpu_scale_up: float = 80.0
    cpu_scale_down: float = 20.0
    memory_scale_up: float = 85.0
    memory_scale_down: float = 30.0
    response_time_critical: float = 2000.0  # 2 seconds
    response_time_warning: float = 1000.0  # 1 second
    error_rate_critical: float = 5.0
    error_rate_warning: float = 1.0


# =============================================================================
# AUTO-SCALING ADVISOR
# =============================================================================


class AutoScalingAdvisor:
    """Provides intelligent auto-scaling recommendations.

    Analyzes resource usage patterns and provides actionable
    recommendations for optimal resource allocation.

    Features:
    - CPU utilization analysis
    - Memory usage optimization
    - Response time monitoring
    - Error rate detection
    - Cost-aware recommendations

    Example:
        >>> advisor = AutoScalingAdvisor(cost_monitor=monitor)
        >>> report = await advisor.generate_report("deployment-id")
        >>> print(f"Potential savings: ${report.estimated_monthly_savings}")
    """

    def __init__(
        self,
        cost_monitor: Any | None = None,
        thresholds: ScalingThresholds | None = None,
    ):
        """Initialize auto-scaling advisor.

        Args:
            cost_monitor: Optional CostMonitor for usage data
            thresholds: Custom scaling thresholds
        """
        self.cost_monitor = cost_monitor
        self.thresholds = thresholds or ScalingThresholds()

        # Pricing for savings calculations (Railway 2026)
        self.vcpu_cost_per_hour = 0.000231 * 60  # Per vCPU-hour
        self.memory_cost_per_gb_hour = 0.000231 * 60  # Per GB-hour

    async def get_current_metrics(self, deployment_id: str) -> ResourceMetrics:
        """Get current resource metrics for deployment.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            ResourceMetrics with current utilization
        """
        if self.cost_monitor:
            try:
                usage = await self.cost_monitor.get_current_usage(deployment_id)
                return ResourceMetrics(
                    cpu_percent=usage.cpu_percent,
                    memory_mb=usage.memory_mb,
                    memory_percent=(usage.memory_mb / 512) * 100,  # Assume 512MB default
                    request_rate=0,  # Would come from metrics endpoint
                    response_time_ms=0,
                    error_rate=0,
                    timestamp=datetime.now(UTC),
                )
            except Exception as e:
                logger.warning(f"Failed to get metrics: {e}")

        # Return mock metrics if no monitor available
        return ResourceMetrics(
            cpu_percent=45.0,
            memory_mb=256.0,
            memory_percent=50.0,
            request_rate=10.0,
            response_time_ms=150.0,
            error_rate=0.1,
            timestamp=datetime.now(UTC),
        )

    def analyze_cpu(self, metrics: ResourceMetrics) -> ScalingRecommendation | None:
        """Analyze CPU utilization and generate recommendation.

        Args:
            metrics: Current resource metrics

        Returns:
            ScalingRecommendation or None if no change needed
        """
        cpu = metrics.cpu_percent

        if cpu >= self.thresholds.cpu_scale_up:
            # High CPU - recommend scale up
            priority = (
                RecommendationPriority.CRITICAL
                if cpu >= 95
                else RecommendationPriority.HIGH
            )
            return ScalingRecommendation(
                resource=ResourceType.CPU,
                direction=ScalingDirection.SCALE_UP,
                priority=priority,
                current_value=1.0,  # vCPU
                recommended_value=2.0,
                reason=(
                    f"CPU utilization at {cpu:.1f}% exceeds "
                    f"{self.thresholds.cpu_scale_up}% threshold"
                ),
                impact="Increase capacity to handle load and prevent throttling",
                estimated_savings=-self.vcpu_cost_per_hour * 24 * 30,  # Additional cost
            )

        elif cpu <= self.thresholds.cpu_scale_down:
            # Low CPU - recommend scale down
            savings = self.vcpu_cost_per_hour * 0.5 * 24 * 30  # Save 0.5 vCPU
            return ScalingRecommendation(
                resource=ResourceType.CPU,
                direction=ScalingDirection.SCALE_DOWN,
                priority=RecommendationPriority.MEDIUM,
                current_value=1.0,
                recommended_value=0.5,
                reason=(
                    f"CPU utilization at {cpu:.1f}% is below "
                    f"{self.thresholds.cpu_scale_down}% threshold"
                ),
                impact="Reduce costs without impacting performance",
                estimated_savings=savings,
            )

        return None

    def analyze_memory(self, metrics: ResourceMetrics) -> ScalingRecommendation | None:
        """Analyze memory utilization and generate recommendation.

        Args:
            metrics: Current resource metrics

        Returns:
            ScalingRecommendation or None if no change needed
        """
        mem_pct = metrics.memory_percent
        mem_mb = metrics.memory_mb

        if mem_pct >= self.thresholds.memory_scale_up:
            # High memory - recommend scale up
            priority = (
                RecommendationPriority.CRITICAL
                if mem_pct >= 95
                else RecommendationPriority.HIGH
            )
            return ScalingRecommendation(
                resource=ResourceType.MEMORY,
                direction=ScalingDirection.SCALE_UP,
                priority=priority,
                current_value=512,  # MB
                recommended_value=1024,
                reason=(
                    f"Memory utilization at {mem_pct:.1f}% exceeds "
                    f"{self.thresholds.memory_scale_up}% threshold"
                ),
                impact="Prevent OOM errors and improve stability",
                estimated_savings=-self.memory_cost_per_gb_hour * 0.5 * 24 * 30,
            )

        elif mem_pct <= self.thresholds.memory_scale_down:
            # Low memory - recommend scale down
            savings = self.memory_cost_per_gb_hour * 0.25 * 24 * 30  # Save 256MB
            return ScalingRecommendation(
                resource=ResourceType.MEMORY,
                direction=ScalingDirection.SCALE_DOWN,
                priority=RecommendationPriority.LOW,
                current_value=512,
                recommended_value=256,
                reason=(
                    f"Memory utilization at {mem_pct:.1f}% ({mem_mb:.0f}MB) is below "
                    f"{self.thresholds.memory_scale_down}% threshold"
                ),
                impact="Reduce costs with minimal risk",
                estimated_savings=savings,
            )

        return None

    def analyze_response_time(
        self, metrics: ResourceMetrics
    ) -> ScalingRecommendation | None:
        """Analyze response time and generate recommendation.

        Args:
            metrics: Current resource metrics

        Returns:
            ScalingRecommendation or None if acceptable
        """
        rt = metrics.response_time_ms

        if rt >= self.thresholds.response_time_critical:
            return ScalingRecommendation(
                resource=ResourceType.INSTANCES,
                direction=ScalingDirection.SCALE_UP,
                priority=RecommendationPriority.CRITICAL,
                current_value=1,
                recommended_value=2,
                reason=(
                    f"Response time at {rt:.0f}ms exceeds critical threshold of "
                    f"{self.thresholds.response_time_critical:.0f}ms"
                ),
                impact="Reduce latency and improve user experience",
                estimated_savings=0,
            )

        elif rt >= self.thresholds.response_time_warning:
            return ScalingRecommendation(
                resource=ResourceType.CPU,
                direction=ScalingDirection.SCALE_UP,
                priority=RecommendationPriority.MEDIUM,
                current_value=1.0,
                recommended_value=1.5,
                reason=(
                    f"Response time at {rt:.0f}ms exceeds warning threshold of "
                    f"{self.thresholds.response_time_warning:.0f}ms"
                ),
                impact="Improve response times before they become critical",
                estimated_savings=0,
            )

        return None

    def analyze_error_rate(
        self, metrics: ResourceMetrics
    ) -> ScalingRecommendation | None:
        """Analyze error rate and generate recommendation.

        Args:
            metrics: Current resource metrics

        Returns:
            ScalingRecommendation or None if acceptable
        """
        err = metrics.error_rate

        if err >= self.thresholds.error_rate_critical:
            return ScalingRecommendation(
                resource=ResourceType.INSTANCES,
                direction=ScalingDirection.SCALE_UP,
                priority=RecommendationPriority.CRITICAL,
                current_value=1,
                recommended_value=2,
                reason=(
                    f"Error rate at {err:.2f}% exceeds critical threshold of "
                    f"{self.thresholds.error_rate_critical}%"
                ),
                impact="Add redundancy to reduce errors and improve reliability",
                estimated_savings=0,
            )

        elif err >= self.thresholds.error_rate_warning:
            return ScalingRecommendation(
                resource=ResourceType.CPU,
                direction=ScalingDirection.SCALE_UP,
                priority=RecommendationPriority.HIGH,
                current_value=1.0,
                recommended_value=1.5,
                reason=(
                    f"Error rate at {err:.2f}% exceeds warning threshold of "
                    f"{self.thresholds.error_rate_warning}%"
                ),
                impact="Increase resources to handle load better",
                estimated_savings=0,
            )

        return None

    async def analyze_and_recommend(
        self, deployment_id: str
    ) -> list[ScalingRecommendation]:
        """Analyze deployment and generate all recommendations.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            List of ScalingRecommendation objects
        """
        metrics = await self.get_current_metrics(deployment_id)
        recommendations = []

        # Analyze each dimension
        cpu_rec = self.analyze_cpu(metrics)
        if cpu_rec:
            recommendations.append(cpu_rec)

        mem_rec = self.analyze_memory(metrics)
        if mem_rec:
            recommendations.append(mem_rec)

        rt_rec = self.analyze_response_time(metrics)
        if rt_rec:
            recommendations.append(rt_rec)

        err_rec = self.analyze_error_rate(metrics)
        if err_rec:
            recommendations.append(err_rec)

        # Sort by priority
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
            RecommendationPriority.INFO: 4,
        }
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

        return recommendations

    async def generate_report(self, deployment_id: str) -> ScalingReport:
        """Generate comprehensive scaling report.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            ScalingReport with metrics and recommendations
        """
        metrics = await self.get_current_metrics(deployment_id)
        recommendations = await self.analyze_and_recommend(deployment_id)

        # Calculate total potential savings
        total_savings = sum(
            r.estimated_savings for r in recommendations if r.estimated_savings > 0
        )

        # Determine overall status
        has_critical = any(
            r.priority == RecommendationPriority.CRITICAL for r in recommendations
        )
        has_high = any(
            r.priority == RecommendationPriority.HIGH for r in recommendations
        )

        if has_critical:
            status = "critical"
        elif has_high:
            status = "warning"
        elif recommendations:
            status = "optimizable"
        else:
            status = "optimal"

        return ScalingReport(
            generated_at=datetime.now(UTC),
            deployment_id=deployment_id,
            current_metrics=metrics,
            recommendations=recommendations,
            overall_status=status,
            estimated_monthly_savings=total_savings,
        )

    def get_scaling_summary(
        self, recommendations: list[ScalingRecommendation]
    ) -> dict[str, Any]:
        """Get summary of scaling recommendations.

        Args:
            recommendations: List of recommendations

        Returns:
            Summary dictionary
        """
        scale_up = [r for r in recommendations if r.direction == ScalingDirection.SCALE_UP]
        scale_down = [
            r for r in recommendations if r.direction == ScalingDirection.SCALE_DOWN
        ]

        return {
            "total_recommendations": len(recommendations),
            "scale_up_count": len(scale_up),
            "scale_down_count": len(scale_down),
            "critical_count": len(
                [r for r in recommendations if r.priority == RecommendationPriority.CRITICAL]
            ),
            "high_count": len(
                [r for r in recommendations if r.priority == RecommendationPriority.HIGH]
            ),
            "potential_savings": sum(
                r.estimated_savings for r in recommendations if r.estimated_savings > 0
            ),
            "additional_costs": abs(
                sum(r.estimated_savings for r in recommendations if r.estimated_savings < 0)
            ),
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def get_scaling_recommendations(
    deployment_id: str,
    cost_monitor: Any | None = None,
) -> list[dict[str, Any]]:
    """Get scaling recommendations as dictionaries.

    Args:
        deployment_id: Railway deployment ID
        cost_monitor: Optional CostMonitor instance

    Returns:
        List of recommendation dictionaries
    """
    advisor = AutoScalingAdvisor(cost_monitor=cost_monitor)
    recommendations = await advisor.analyze_and_recommend(deployment_id)
    return [r.to_dict() for r in recommendations]


async def generate_scaling_report(
    deployment_id: str,
    cost_monitor: Any | None = None,
) -> dict[str, Any]:
    """Generate scaling report as dictionary.

    Args:
        deployment_id: Railway deployment ID
        cost_monitor: Optional CostMonitor instance

    Returns:
        Report dictionary
    """
    advisor = AutoScalingAdvisor(cost_monitor=cost_monitor)
    report = await advisor.generate_report(deployment_id)
    return report.to_dict()


def format_recommendation(rec: ScalingRecommendation) -> str:
    """Format recommendation as human-readable string.

    Args:
        rec: ScalingRecommendation object

    Returns:
        Formatted string
    """
    direction_emoji = {
        ScalingDirection.SCALE_UP: "⬆️",
        ScalingDirection.SCALE_DOWN: "⬇️",
        ScalingDirection.NO_CHANGE: "➡️",
    }

    priority_emoji = {
        RecommendationPriority.CRITICAL: "🚨",
        RecommendationPriority.HIGH: "⚠️",
        RecommendationPriority.MEDIUM: "💡",
        RecommendationPriority.LOW: "ℹ️",
        RecommendationPriority.INFO: "📝",
    }

    emoji = direction_emoji.get(rec.direction, "•")
    priority = priority_emoji.get(rec.priority, "•")

    savings_str = ""
    if rec.estimated_savings > 0:
        savings_str = f" (saves ~${rec.estimated_savings:.2f}/month)"
    elif rec.estimated_savings < 0:
        savings_str = f" (costs ~${abs(rec.estimated_savings):.2f}/month)"

    return (
        f"{priority} {emoji} {rec.resource.value.upper()}: "
        f"{rec.current_value} → {rec.recommended_value}{savings_str}\n"
        f"   Reason: {rec.reason}\n"
        f"   Impact: {rec.impact}"
    )
