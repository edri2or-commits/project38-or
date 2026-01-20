"""
Latency Metrics for Model Evaluation.

Provides metrics for measuring response latency:
- Average latency
- Percentiles (p50, p90, p95, p99)
- Min/Max latency
- Standard deviation

Architecture Decision: ADR-009
"""

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LatencyMetrics:
    """Latency metrics for model responses.

    Attributes:
        avg_ms: Average latency in milliseconds.
        min_ms: Minimum latency in milliseconds.
        max_ms: Maximum latency in milliseconds.
        p50_ms: 50th percentile (median) latency.
        p90_ms: 90th percentile latency.
        p95_ms: 95th percentile latency.
        p99_ms: 99th percentile latency.
        std_dev_ms: Standard deviation of latencies.
        sample_count: Number of latency samples.
    """

    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    std_dev_ms: float = 0.0
    sample_count: int = 0
    _samples: list[float] = field(default_factory=list, repr=False)

    @classmethod
    def calculate(cls, latencies: list[float]) -> "LatencyMetrics":
        """Calculate latency metrics from samples.

        Args:
            latencies: List of latency measurements in milliseconds.

        Returns:
            LatencyMetrics instance with calculated values.
        """
        if not latencies:
            return cls()

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        metrics = cls(
            avg_ms=sum(latencies) / n,
            min_ms=sorted_latencies[0],
            max_ms=sorted_latencies[-1],
            p50_ms=cls._percentile(sorted_latencies, 50),
            p90_ms=cls._percentile(sorted_latencies, 90),
            p95_ms=cls._percentile(sorted_latencies, 95),
            p99_ms=cls._percentile(sorted_latencies, 99),
            std_dev_ms=cls._std_dev(latencies),
            sample_count=n,
            _samples=latencies,
        )

        return metrics

    @staticmethod
    def _percentile(sorted_data: list[float], percentile: float) -> float:
        """Calculate percentile from sorted data.

        Args:
            sorted_data: Sorted list of values.
            percentile: Percentile to calculate (0-100).

        Returns:
            Percentile value.
        """
        if not sorted_data:
            return 0.0

        n = len(sorted_data)
        index = (percentile / 100) * (n - 1)
        lower = int(index)
        upper = min(lower + 1, n - 1)
        weight = index - lower

        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight

    @staticmethod
    def _std_dev(data: list[float]) -> float:
        """Calculate standard deviation.

        Args:
            data: List of values.

        Returns:
            Standard deviation.
        """
        if len(data) < 2:
            return 0.0

        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        return math.sqrt(variance)

    def is_acceptable(
        self,
        max_avg_ms: float = 2000,
        max_p99_ms: float = 5000,
    ) -> bool:
        """Check if latencies are within acceptable thresholds.

        Args:
            max_avg_ms: Maximum acceptable average latency.
            max_p99_ms: Maximum acceptable P99 latency.

        Returns:
            True if latencies are acceptable.
        """
        return self.avg_ms <= max_avg_ms and self.p99_ms <= max_p99_ms

    def compare(self, other: "LatencyMetrics") -> dict[str, float]:
        """Compare latencies to another set.

        Args:
            other: LatencyMetrics to compare against.

        Returns:
            Dictionary with percentage changes (positive = slower).
        """
        def pct_change(new: float, old: float) -> float:
            if old == 0:
                return 0.0
            return ((new - old) / old) * 100

        return {
            "avg_change_pct": pct_change(self.avg_ms, other.avg_ms),
            "p50_change_pct": pct_change(self.p50_ms, other.p50_ms),
            "p95_change_pct": pct_change(self.p95_ms, other.p95_ms),
            "p99_change_pct": pct_change(self.p99_ms, other.p99_ms),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p90_ms": round(self.p90_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
            "sample_count": self.sample_count,
        }

    def summary(self) -> str:
        """Get human-readable summary.

        Returns:
            Summary string.
        """
        return (
            f"Latency: avg={self.avg_ms:.0f}ms, "
            f"p50={self.p50_ms:.0f}ms, "
            f"p99={self.p99_ms:.0f}ms "
            f"(n={self.sample_count})"
        )
