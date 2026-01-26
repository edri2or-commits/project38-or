"""Performance Baseline Establishment Module.

Collects performance metrics over time and establishes baseline thresholds
for anomaly detection and alerting.

Based on Week 4 requirements from implementation-roadmap.md.

Features:
- Automatic baseline establishment from historical data
- Anomaly detection (deviation from baseline)
- Trend analysis (improving/degrading/stable)
- Alert generation for significant deviations
- P50, P95, P99 percentile calculations

Example:
    >>> from apps.business.core.performance_baseline import PerformanceBaseline
    >>> baseline = PerformanceBaseline(
    ...     database_url="postgresql://...",
    ...     collection_interval_minutes=5,
    ...     baseline_window_hours=24,
    ... )
    >>> await baseline.collect_metrics()
    >>> stats = await baseline.get_baseline_stats()
    >>> print(f"P95 latency: {stats['latency_ms']['p95']:.2f}ms")
    >>> anomalies = await baseline.detect_anomalies()
    >>> if anomalies:
    ...     print(f"Detected {len(anomalies)} anomalies")
"""

import logging
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class MetricSnapshot:
    """Single metrics snapshot at a point in time.

    Attributes:
        timestamp: When the snapshot was taken
        latency_ms: Average latency in milliseconds
        p95_latency_ms: P95 latency in milliseconds
        error_rate_pct: Error rate percentage (0-100)
        throughput_rph: Requests per hour
        active_agents: Number of active agents
        total_tokens_1h: Total tokens consumed in last hour
        cpu_percent: CPU usage percentage
        memory_percent: Memory usage percentage
    """

    timestamp: datetime
    latency_ms: float
    p95_latency_ms: float
    error_rate_pct: float
    throughput_rph: int
    active_agents: int
    total_tokens_1h: int
    cpu_percent: float
    memory_percent: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "error_rate_pct": self.error_rate_pct,
            "throughput_rph": self.throughput_rph,
            "active_agents": self.active_agents,
            "total_tokens_1h": self.total_tokens_1h,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
        }


@dataclass
class BaselineStats:
    """Statistical baseline for a metric.

    Attributes:
        metric_name: Name of the metric
        mean: Mean value
        median: Median (P50) value
        p95: 95th percentile value
        p99: 99th percentile value
        stddev: Standard deviation
        min_value: Minimum observed value
        max_value: Maximum observed value
        sample_count: Number of samples used to calculate baseline
        calculated_at: When the baseline was calculated
    """

    metric_name: str
    mean: float
    median: float
    p95: float
    p99: float
    stddev: float
    min_value: float
    max_value: float
    sample_count: int
    calculated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metric_name": self.metric_name,
            "mean": self.mean,
            "median": self.median,
            "p95": self.p95,
            "p99": self.p99,
            "stddev": self.stddev,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "sample_count": self.sample_count,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass
class Anomaly:
    """Detected performance anomaly.

    Attributes:
        metric_name: Name of the metric with anomaly
        timestamp: When the anomaly was detected
        current_value: Current observed value
        expected_value: Expected value based on baseline
        deviation_stddev: Deviation in standard deviations (Z-score)
        severity: Severity level (info, warning, critical)
        message: Human-readable description
    """

    metric_name: str
    timestamp: datetime
    current_value: float
    expected_value: float
    deviation_stddev: float
    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metric_name": self.metric_name,
            "timestamp": self.timestamp.isoformat(),
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "deviation_stddev": self.deviation_stddev,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class TrendAnalysis:
    """Trend analysis result.

    Attributes:
        metric_name: Name of the metric
        trend: Trend direction (improving, degrading, stable)
        change_pct: Percentage change from baseline
        recent_mean: Mean of recent samples
        baseline_mean: Mean of baseline samples
        confidence: Confidence level (low, medium, high)
    """

    metric_name: str
    trend: str  # "improving", "degrading", "stable"
    change_pct: float
    recent_mean: float
    baseline_mean: float
    confidence: str  # "low", "medium", "high"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metric_name": self.metric_name,
            "trend": self.trend,
            "change_pct": self.change_pct,
            "recent_mean": self.recent_mean,
            "baseline_mean": self.baseline_mean,
            "confidence": self.confidence,
        }


# =============================================================================
# PERFORMANCE BASELINE
# =============================================================================


class PerformanceBaseline:
    """Performance baseline establishment and anomaly detection.

    Collects metrics over time, calculates baseline statistics,
    and detects anomalies for alerting.

    Features:
    - Automatic metric collection from /metrics/summary endpoint
    - Baseline calculation (mean, percentiles, stddev)
    - Anomaly detection with severity levels
    - Trend analysis (improving/degrading/stable)
    - Configurable sensitivity (Z-score thresholds)

    Attributes:
        database_url: PostgreSQL connection URL
        baseline_window_hours: Hours of data for baseline calculation
        collection_interval_minutes: Minutes between metric collections
        anomaly_threshold_stddev: Z-score threshold for anomaly detection
    """

    def __init__(
        self,
        database_url: str,
        baseline_window_hours: int = 24,
        collection_interval_minutes: int = 5,
        anomaly_threshold_stddev: float = 3.0,
    ):
        """Initialize performance baseline tracker.

        Args:
            database_url: PostgreSQL connection URL
            baseline_window_hours: Hours of historical data for baseline
            collection_interval_minutes: Collection frequency in minutes
            anomaly_threshold_stddev: Z-score threshold for anomalies
        """
        self.database_url = database_url
        self.baseline_window_hours = baseline_window_hours
        self.collection_interval_minutes = collection_interval_minutes
        self.anomaly_threshold_stddev = anomaly_threshold_stddev

    async def collect_metrics(self) -> MetricSnapshot:
        """Collect current metrics snapshot.

        Queries the database for current metrics and system resources,
        then stores the snapshot in the performance_baselines table.

        Returns:
            MetricSnapshot with current values

        Raises:
            asyncpg.PostgreSQLError: If database query fails

        Example:
            >>> snapshot = await baseline.collect_metrics()
            >>> print(f"Latency: {snapshot.latency_ms:.2f}ms")
        """
        conn = await asyncpg.connect(self.database_url)
        try:
            # Get metrics from agent_metrics table
            now = datetime.now(UTC)

            # Average latency
            latency_ms = await conn.fetchval(
                """
                SELECT COALESCE(AVG(value), 0)
                FROM agent_metrics
                WHERE metric_name = 'latency_ms'
                  AND time >= NOW() - INTERVAL '1 hour'
                """
            )

            # P95 latency
            p95_latency_ms = await conn.fetchval(
                """
                SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value), 0)
                FROM agent_metrics
                WHERE metric_name = 'latency_ms'
                  AND time >= NOW() - INTERVAL '1 hour'
                """
            )

            # Error rate
            errors = await conn.fetchval(
                """
                SELECT COALESCE(SUM(value), 0)
                FROM agent_metrics
                WHERE metric_name = 'error_count'
                  AND time >= NOW() - INTERVAL '1 hour'
                """
            )

            total_requests = await conn.fetchval(
                """
                SELECT COALESCE(SUM(value), 0)
                FROM agent_metrics
                WHERE metric_name IN ('success_count', 'error_count')
                  AND time >= NOW() - INTERVAL '1 hour'
                """
            )

            error_rate_pct = (
                round((errors / total_requests) * 100, 2) if total_requests > 0 else 0.0
            )

            # Active agents
            active_agents = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT agent_id)
                FROM agent_metrics
                WHERE time >= NOW() - INTERVAL '1 hour'
                """
            )

            # Total tokens
            total_tokens = await conn.fetchval(
                """
                SELECT COALESCE(SUM(value), 0)::INT
                FROM agent_metrics
                WHERE metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
                  AND time >= NOW() - INTERVAL '1 hour'
                """
            )

            # System resources (mock values for now - will be populated via /metrics/system)
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            snapshot = MetricSnapshot(
                timestamp=now,
                latency_ms=round(latency_ms or 0, 2),
                p95_latency_ms=round(p95_latency_ms or 0, 2),
                error_rate_pct=error_rate_pct,
                throughput_rph=int(total_requests or 0),
                active_agents=int(active_agents or 0),
                total_tokens_1h=int(total_tokens or 0),
                cpu_percent=round(cpu_percent, 2),
                memory_percent=round(memory_percent, 2),
            )

            # Store snapshot in database
            await conn.execute(
                """
                INSERT INTO performance_snapshots
                (timestamp, latency_ms, p95_latency_ms, error_rate_pct,
                 throughput_rph, active_agents, total_tokens_1h,
                 cpu_percent, memory_percent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                snapshot.timestamp,
                snapshot.latency_ms,
                snapshot.p95_latency_ms,
                snapshot.error_rate_pct,
                snapshot.throughput_rph,
                snapshot.active_agents,
                snapshot.total_tokens_1h,
                snapshot.cpu_percent,
                snapshot.memory_percent,
            )

            logger.info(
                "Metrics snapshot collected",
                extra={
                    "latency_ms": snapshot.latency_ms,
                    "error_rate_pct": snapshot.error_rate_pct,
                    "throughput_rph": snapshot.throughput_rph,
                },
            )

            return snapshot

        finally:
            await conn.close()

    async def get_baseline_stats(
        self,
        metric_name: str | None = None,
    ) -> dict[str, BaselineStats]:
        """Calculate baseline statistics from historical data.

        Args:
            metric_name: Optional specific metric name (e.g., "latency_ms")
                        If None, calculates baselines for all metrics

        Returns:
            Dictionary mapping metric names to BaselineStats

        Example:
            >>> stats = await baseline.get_baseline_stats()
            >>> latency_stats = stats["latency_ms"]
            >>> print(f"P95: {latency_stats.p95:.2f}ms")
        """
        conn = await asyncpg.connect(self.database_url)
        try:
            cutoff = datetime.now(UTC) - timedelta(hours=self.baseline_window_hours)

            # Get historical snapshots
            rows = await conn.fetch(
                """
                SELECT *
                FROM performance_snapshots
                WHERE timestamp >= $1
                ORDER BY timestamp DESC
                """,
                cutoff,
            )

            if not rows:
                logger.warning("No historical data for baseline calculation")
                return {}

            # Extract metric columns
            metric_columns = [
                "latency_ms",
                "p95_latency_ms",
                "error_rate_pct",
                "throughput_rph",
                "cpu_percent",
                "memory_percent",
            ]

            if metric_name and metric_name not in metric_columns:
                raise ValueError(f"Unknown metric: {metric_name}")

            metrics_to_process = [metric_name] if metric_name else metric_columns

            baselines = {}
            now = datetime.now(UTC)

            for metric in metrics_to_process:
                values = [float(row[metric]) for row in rows if row[metric] is not None]

                if not values:
                    continue

                baselines[metric] = BaselineStats(
                    metric_name=metric,
                    mean=round(statistics.mean(values), 2),
                    median=round(statistics.median(values), 2),
                    p95=round(statistics.quantiles(values, n=20)[18], 2),  # 19th of 20 quantiles
                    p99=(
                        round(statistics.quantiles(values, n=100)[98], 2)
                        if len(values) >= 100
                        else max(values)
                    ),
                    stddev=round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
                    min_value=round(min(values), 2),
                    max_value=round(max(values), 2),
                    sample_count=len(values),
                    calculated_at=now,
                )

            logger.info(
                f"Calculated baseline stats for {len(baselines)} metrics",
                extra={"sample_count": len(rows), "window_hours": self.baseline_window_hours},
            )

            return baselines

        finally:
            await conn.close()

    async def detect_anomalies(
        self,
        current_snapshot: MetricSnapshot | None = None,
    ) -> list[Anomaly]:
        """Detect anomalies by comparing current metrics to baseline.

        Args:
            current_snapshot: Optional current snapshot. If None, collects new snapshot.

        Returns:
            List of detected anomalies with severity levels

        Example:
            >>> anomalies = await baseline.detect_anomalies()
            >>> for anomaly in anomalies:
            ...     print(f"{anomaly.severity}: {anomaly.message}")
        """
        if current_snapshot is None:
            current_snapshot = await self.collect_metrics()

        baselines = await self.get_baseline_stats()

        if not baselines:
            logger.warning("No baseline data available for anomaly detection")
            return []

        anomalies = []

        # Check each metric against baseline
        metric_mapping = {
            "latency_ms": current_snapshot.latency_ms,
            "p95_latency_ms": current_snapshot.p95_latency_ms,
            "error_rate_pct": current_snapshot.error_rate_pct,
            "throughput_rph": current_snapshot.throughput_rph,
            "cpu_percent": current_snapshot.cpu_percent,
            "memory_percent": current_snapshot.memory_percent,
        }

        for metric_name, current_value in metric_mapping.items():
            if metric_name not in baselines:
                continue

            baseline = baselines[metric_name]

            # Calculate Z-score (standard deviations from mean)
            if baseline.stddev > 0:
                z_score = abs((current_value - baseline.mean) / baseline.stddev)
            else:
                z_score = 0.0

            # Determine severity based on Z-score
            if z_score >= self.anomaly_threshold_stddev:
                if z_score >= 5.0:
                    severity = "critical"
                elif z_score >= 4.0:
                    severity = "warning"
                else:
                    severity = "info"

                # Direction of anomaly
                direction = "above" if current_value > baseline.mean else "below"

                anomalies.append(
                    Anomaly(
                        metric_name=metric_name,
                        timestamp=current_snapshot.timestamp,
                        current_value=current_value,
                        expected_value=baseline.mean,
                        deviation_stddev=round(z_score, 2),
                        severity=severity,
                        message=(
                            f"{metric_name} is {z_score:.1f}σ {direction} baseline "
                            f"(current: {current_value:.2f}, "
                            f"expected: {baseline.mean:.2f}±{baseline.stddev:.2f})"
                        ),
                    )
                )

        if anomalies:
            logger.warning(
                f"Detected {len(anomalies)} anomalies",
                extra={
                    "anomalies": [a.to_dict() for a in anomalies],
                },
            )

        return anomalies

    async def analyze_trends(
        self,
        recent_window_hours: int = 6,
    ) -> list[TrendAnalysis]:
        """Analyze performance trends.

        Compares recent metrics to baseline to identify improving or degrading trends.

        Args:
            recent_window_hours: Hours of recent data for trend analysis

        Returns:
            List of trend analysis results

        Example:
            >>> trends = await baseline.analyze_trends()
            >>> for trend in trends:
            ...     print(f"{trend.metric_name}: {trend.trend} ({trend.change_pct:+.1f}%)")
        """
        conn = await asyncpg.connect(self.database_url)
        try:
            baseline_cutoff = datetime.now(UTC) - timedelta(hours=self.baseline_window_hours)
            recent_cutoff = datetime.now(UTC) - timedelta(hours=recent_window_hours)

            # Get baseline metrics
            baseline_rows = await conn.fetch(
                """
                SELECT *
                FROM performance_snapshots
                WHERE timestamp >= $1 AND timestamp < $2
                ORDER BY timestamp DESC
                """,
                baseline_cutoff,
                recent_cutoff,
            )

            # Get recent metrics
            recent_rows = await conn.fetch(
                """
                SELECT *
                FROM performance_snapshots
                WHERE timestamp >= $1
                ORDER BY timestamp DESC
                """,
                recent_cutoff,
            )

            if not baseline_rows or not recent_rows:
                logger.warning("Insufficient data for trend analysis")
                return []

            metric_columns = [
                "latency_ms",
                "error_rate_pct",
                "throughput_rph",
                "cpu_percent",
                "memory_percent",
            ]

            trends = []

            for metric in metric_columns:
                baseline_values = [
                    float(row[metric]) for row in baseline_rows if row[metric] is not None
                ]
                recent_values = [
                    float(row[metric]) for row in recent_rows if row[metric] is not None
                ]

                if not baseline_values or not recent_values:
                    continue

                baseline_mean = statistics.mean(baseline_values)
                recent_mean = statistics.mean(recent_values)

                # Calculate change percentage
                if baseline_mean > 0:
                    change_pct = ((recent_mean - baseline_mean) / baseline_mean) * 100
                else:
                    change_pct = 0.0

                # Determine trend direction (for latency/error rate, lower is better)
                if metric in ["latency_ms", "error_rate_pct", "cpu_percent", "memory_percent"]:
                    if change_pct < -5:
                        trend = "improving"
                    elif change_pct > 5:
                        trend = "degrading"
                    else:
                        trend = "stable"
                else:  # throughput - higher is better
                    if change_pct > 5:
                        trend = "improving"
                    elif change_pct < -5:
                        trend = "degrading"
                    else:
                        trend = "stable"

                # Confidence based on sample size and consistency
                if len(recent_values) >= 10 and len(baseline_values) >= 20:
                    confidence = "high"
                elif len(recent_values) >= 5 and len(baseline_values) >= 10:
                    confidence = "medium"
                else:
                    confidence = "low"

                trends.append(
                    TrendAnalysis(
                        metric_name=metric,
                        trend=trend,
                        change_pct=round(change_pct, 2),
                        recent_mean=round(recent_mean, 2),
                        baseline_mean=round(baseline_mean, 2),
                        confidence=confidence,
                    )
                )

            logger.info(
                f"Analyzed trends for {len(trends)} metrics",
                extra={"trends": [t.to_dict() for t in trends]},
            )

            return trends

        finally:
            await conn.close()

    async def get_dashboard_data(self) -> dict[str, Any]:
        """Get comprehensive dashboard data.

        Combines current metrics, baseline stats, anomalies, and trends
        for display in performance dashboard.

        Returns:
            Dictionary with dashboard data

        Example:
            >>> data = await baseline.get_dashboard_data()
            >>> print(f"Active anomalies: {len(data['anomalies'])}")
            >>> degrading = sum(1 for t in data['trends'] if t['trend'] == 'degrading')
            >>> print(f"Degrading metrics: {degrading}")
        """
        current_snapshot = await self.collect_metrics()
        baselines = await self.get_baseline_stats()
        anomalies = await self.detect_anomalies(current_snapshot)
        trends = await self.analyze_trends()

        return {
            "current_metrics": current_snapshot.to_dict(),
            "baselines": {k: v.to_dict() for k, v in baselines.items()},
            "anomalies": [a.to_dict() for a in anomalies],
            "trends": [t.to_dict() for t in trends],
            "summary": {
                "total_anomalies": len(anomalies),
                "critical_anomalies": sum(1 for a in anomalies if a.severity == "critical"),
                "degrading_trends": sum(1 for t in trends if t.trend == "degrading"),
                "improving_trends": sum(1 for t in trends if t.trend == "improving"),
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }


# =============================================================================
# DATABASE SCHEMA (for reference - should be created via migration)
# =============================================================================

CREATE_PERFORMANCE_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL,
    p95_latency_ms DOUBLE PRECISION NOT NULL,
    error_rate_pct DOUBLE PRECISION NOT NULL,
    throughput_rph INTEGER NOT NULL,
    active_agents INTEGER NOT NULL,
    total_tokens_1h INTEGER NOT NULL,
    cpu_percent DOUBLE PRECISION NOT NULL,
    memory_percent DOUBLE PRECISION NOT NULL,
    UNIQUE(timestamp)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp
    ON performance_snapshots(timestamp DESC);
"""
