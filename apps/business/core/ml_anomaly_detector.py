"""ML-based Anomaly Detection Module.

Advanced anomaly detection using multiple algorithms with ensemble voting.
Goes beyond simple Z-score to detect complex patterns and seasonal anomalies.

Month 3 Goal: ML-based anomaly detection for proactive issue identification.

Algorithms Implemented:
1. Adaptive Z-Score - Dynamic thresholds based on recent data
2. Moving Average (EMA) - Exponential smoothing for trend detection
3. Interquartile Range (IQR) - Robust outlier detection
4. Seasonal Decomposition - Detect seasonal pattern deviations
5. Ensemble Voting - Combine multiple methods for higher accuracy

Architecture:
    ┌─────────────────────────────────────────────────┐
    │           MLAnomalyDetector                      │
    │  ┌───────────────────────────────────────────┐  │
    │  │  Detection Algorithms                     │  │
    │  │  - Adaptive Z-Score                       │  │
    │  │  - EMA Deviation                          │  │
    │  │  - IQR Outliers                          │  │
    │  │  - Seasonal Decomposition                │  │
    │  │  - Rolling Statistics                    │  │
    │  └───────────────────────────────────────────┘  │
    │  ┌───────────────────────────────────────────┐  │
    │  │  Ensemble Engine                          │  │
    │  │  - Weighted Voting                        │  │
    │  │  - Confidence Scoring                     │  │
    │  │  - Multi-Algorithm Consensus             │  │
    │  └───────────────────────────────────────────┘  │
    │  ┌───────────────────────────────────────────┐  │
    │  │  Learning Engine                          │  │
    │  │  - Adaptive Thresholds                    │  │
    │  │  - Pattern Memory                         │  │
    │  │  - False Positive Reduction               │  │
    │  └───────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────┘

Example:
    >>> from apps.business.core.ml_anomaly_detector import MLAnomalyDetector
    >>> detector = MLAnomalyDetector(sensitivity=0.8)
    >>>
    >>> # Add historical data
    >>> for point in historical_data:
    ...     detector.add_data_point("latency", point.latency_ms, point.timestamp)
    >>>
    >>> # Detect anomalies
    >>> anomalies = detector.detect_all_anomalies()
    >>> for anomaly in anomalies:
    ...     print(f"{anomaly.metric}: {anomaly.severity} - {anomaly.message}")
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================
class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DetectionMethod(str, Enum):
    """Available detection algorithms."""

    ADAPTIVE_ZSCORE = "adaptive_zscore"
    EMA_DEVIATION = "ema_deviation"
    IQR_OUTLIER = "iqr_outlier"
    SEASONAL = "seasonal"
    ROLLING_STATS = "rolling_stats"


# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class DataPoint:
    """Single data point for a metric."""

    value: float
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MLAnomaly:
    """Detected anomaly with ML-specific metadata.

    Attributes:
        metric: Name of the metric with anomaly
        timestamp: When the anomaly was detected
        value: Observed value
        expected: Expected value from model
        deviation: How far from expected (in model-specific units)
        severity: Severity level
        confidence: Confidence score (0.0-1.0)
        methods_triggered: Which detection methods flagged this
        message: Human-readable description
    """

    metric: str
    timestamp: datetime
    value: float
    expected: float
    deviation: float
    severity: AnomalySeverity
    confidence: float
    methods_triggered: list[DetectionMethod]
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metric": self.metric,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "expected": self.expected,
            "deviation": self.deviation,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "methods_triggered": [m.value for m in self.methods_triggered],
            "message": self.message,
        }


@dataclass
class MetricStats:
    """Statistical summary for a metric."""

    mean: float
    median: float
    stddev: float
    min_val: float
    max_val: float
    p25: float
    p75: float
    p95: float
    p99: float
    count: int
    ema: float  # Exponential Moving Average
    ema_stddev: float  # EMA of standard deviation


@dataclass
class SeasonalPattern:
    """Detected seasonal pattern for a metric."""

    metric: str
    period_hours: int  # e.g., 24 for daily, 168 for weekly
    hourly_baselines: dict[int, float]  # hour -> expected value
    hourly_stddev: dict[int, float]  # hour -> expected stddev


# ============================================================================
# ML ANOMALY DETECTOR
# ============================================================================
class MLAnomalyDetector:
    """ML-based anomaly detector with ensemble voting.

    Uses multiple detection algorithms and combines results for higher accuracy.
    Learns from historical data to adapt thresholds and reduce false positives.

    Attributes:
        sensitivity: Detection sensitivity (0.0-1.0, higher = more sensitive)
        min_data_points: Minimum data points before detection starts
        window_size: Rolling window size for statistics
        ema_alpha: EMA smoothing factor (0.0-1.0)
    """

    def __init__(
        self,
        sensitivity: float = 0.7,
        min_data_points: int = 30,
        window_size: int = 100,
        ema_alpha: float = 0.3,
        enable_seasonal: bool = True,
    ):
        """Initialize the ML anomaly detector.

        Args:
            sensitivity: Detection sensitivity (0.0-1.0)
            min_data_points: Minimum data points before detection
            window_size: Size of rolling window for statistics
            ema_alpha: Smoothing factor for EMA (higher = more reactive)
            enable_seasonal: Whether to enable seasonal pattern detection
        """
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self.min_data_points = min_data_points
        self.window_size = window_size
        self.ema_alpha = ema_alpha
        self.enable_seasonal = enable_seasonal

        # Data storage
        self.data: dict[str, list[DataPoint]] = defaultdict(list)
        self.stats: dict[str, MetricStats] = {}
        self.seasonal_patterns: dict[str, SeasonalPattern] = {}

        # Learning state
        self.false_positive_counts: dict[str, int] = defaultdict(int)
        self.confirmed_anomaly_counts: dict[str, int] = defaultdict(int)

        # Thresholds (adaptive)
        self.zscore_threshold = 3.0 - (self.sensitivity * 1.5)  # 1.5 to 3.0
        self.iqr_multiplier = 1.5 + (1.0 - self.sensitivity)  # 1.5 to 2.5
        self.ema_deviation_threshold = 2.0 - (self.sensitivity * 0.5)  # 1.5 to 2.0

        self.logger = logging.getLogger(__name__)

    # ========================================================================
    # DATA MANAGEMENT
    # ========================================================================

    def add_data_point(
        self,
        metric: str,
        value: float,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a data point for a metric.

        Args:
            metric: Metric name
            value: Metric value
            timestamp: When the value was recorded (default: now)
            metadata: Optional metadata
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        point = DataPoint(
            value=value,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        self.data[metric].append(point)

        # Trim to window size
        if len(self.data[metric]) > self.window_size * 2:
            self.data[metric] = self.data[metric][-self.window_size :]

        # Update statistics incrementally
        self._update_stats(metric)

    def add_batch(self, metric: str, values: list[tuple[float, datetime]]) -> None:
        """Add multiple data points at once.

        Args:
            metric: Metric name
            values: List of (value, timestamp) tuples
        """
        for value, timestamp in values:
            self.add_data_point(metric, value, timestamp)

    def clear_data(self, metric: str | None = None) -> None:
        """Clear stored data.

        Args:
            metric: Specific metric to clear, or None for all
        """
        if metric:
            self.data[metric] = []
            if metric in self.stats:
                del self.stats[metric]
        else:
            self.data.clear()
            self.stats.clear()

    def _update_stats(self, metric: str) -> None:
        """Update statistics for a metric incrementally."""
        points = self.data[metric]
        if len(points) < 2:
            return

        values = [p.value for p in points[-self.window_size :]]

        # Basic statistics
        mean = sum(values) / len(values)
        sorted_vals = sorted(values)
        n = len(sorted_vals)

        if n % 2:
            median = sorted_vals[n // 2]
        else:
            median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2

        variance = sum((x - mean) ** 2 for x in values) / len(values)
        stddev = math.sqrt(variance) if variance > 0 else 0.001

        # Percentiles
        p25 = sorted_vals[int(n * 0.25)]
        p75 = sorted_vals[int(n * 0.75)]
        p95 = sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1]
        p99 = sorted_vals[int(n * 0.99)] if n >= 100 else sorted_vals[-1]

        # EMA calculation
        if metric in self.stats:
            old_ema = self.stats[metric].ema
            old_ema_std = self.stats[metric].ema_stddev
            new_ema = self.ema_alpha * values[-1] + (1 - self.ema_alpha) * old_ema
            ema_diff = abs(values[-1] - old_ema)
            new_ema_std = self.ema_alpha * ema_diff + (1 - self.ema_alpha) * old_ema_std
        else:
            new_ema = mean
            new_ema_std = stddev

        self.stats[metric] = MetricStats(
            mean=mean,
            median=median,
            stddev=stddev,
            min_val=min(values),
            max_val=max(values),
            p25=p25,
            p75=p75,
            p95=p95,
            p99=p99,
            count=len(values),
            ema=new_ema,
            ema_stddev=new_ema_std,
        )

    # ========================================================================
    # DETECTION ALGORITHMS
    # ========================================================================

    def _detect_adaptive_zscore(self, metric: str, value: float) -> tuple[bool, float, str]:
        """Detect anomaly using adaptive Z-score.

        Adapts threshold based on recent data stability.

        Args:
            metric: Metric name
            value: Value to check

        Returns:
            Tuple of (is_anomaly, deviation, reason)
        """
        if metric not in self.stats:
            return False, 0.0, ""

        stats = self.stats[metric]
        if stats.stddev < 0.001:
            return False, 0.0, "Insufficient variance"

        # Calculate Z-score
        zscore = abs(value - stats.mean) / stats.stddev

        # Adaptive threshold based on data stability
        recent_values = [p.value for p in self.data[metric][-10:]]
        if len(recent_values) >= 5:
            recent_std = self._calculate_stddev(recent_values)
            stability_factor = min(1.5, stats.stddev / (recent_std + 0.001))
            adaptive_threshold = self.zscore_threshold * stability_factor
        else:
            adaptive_threshold = self.zscore_threshold

        is_anomaly = zscore > adaptive_threshold
        reason = f"Z-score {zscore:.2f} > threshold {adaptive_threshold:.2f}" if is_anomaly else ""

        return is_anomaly, zscore, reason

    def _detect_ema_deviation(self, metric: str, value: float) -> tuple[bool, float, str]:
        """Detect anomaly using EMA deviation.

        Compares current value to exponential moving average.

        Args:
            metric: Metric name
            value: Value to check

        Returns:
            Tuple of (is_anomaly, deviation, reason)
        """
        if metric not in self.stats:
            return False, 0.0, ""

        stats = self.stats[metric]
        if stats.ema_stddev < 0.001:
            return False, 0.0, "Insufficient EMA variance"

        deviation = abs(value - stats.ema) / stats.ema_stddev
        is_anomaly = deviation > self.ema_deviation_threshold

        if is_anomaly:
            threshold = self.ema_deviation_threshold
            reason = f"EMA deviation {deviation:.2f} > threshold {threshold:.2f}"
        else:
            reason = ""

        return is_anomaly, deviation, reason

    def _detect_iqr_outlier(self, metric: str, value: float) -> tuple[bool, float, str]:
        """Detect outlier using Interquartile Range method.

        More robust to existing outliers in the data.

        Args:
            metric: Metric name
            value: Value to check

        Returns:
            Tuple of (is_anomaly, deviation, reason)
        """
        if metric not in self.stats:
            return False, 0.0, ""

        stats = self.stats[metric]
        iqr = stats.p75 - stats.p25

        if iqr < 0.001:
            return False, 0.0, "Insufficient IQR"

        lower_bound = stats.p25 - (self.iqr_multiplier * iqr)
        upper_bound = stats.p75 + (self.iqr_multiplier * iqr)

        is_anomaly = value < lower_bound or value > upper_bound

        if is_anomaly:
            if value < lower_bound:
                deviation = (lower_bound - value) / iqr
                reason = f"Below IQR lower bound ({value:.2f} < {lower_bound:.2f})"
            else:
                deviation = (value - upper_bound) / iqr
                reason = f"Above IQR upper bound ({value:.2f} > {upper_bound:.2f})"
        else:
            deviation = 0.0
            reason = ""

        return is_anomaly, deviation, reason

    def _detect_seasonal_anomaly(
        self, metric: str, value: float, timestamp: datetime
    ) -> tuple[bool, float, str]:
        """Detect anomaly based on seasonal patterns.

        Compares to expected value for this hour of day/week.

        Args:
            metric: Metric name
            value: Value to check
            timestamp: When the value was recorded

        Returns:
            Tuple of (is_anomaly, deviation, reason)
        """
        if not self.enable_seasonal:
            return False, 0.0, ""

        if metric not in self.seasonal_patterns:
            self._learn_seasonal_pattern(metric)

        if metric not in self.seasonal_patterns:
            return False, 0.0, "Insufficient data for seasonal pattern"

        pattern = self.seasonal_patterns[metric]
        hour = timestamp.hour

        if hour not in pattern.hourly_baselines:
            return False, 0.0, ""

        expected = pattern.hourly_baselines[hour]
        stddev = pattern.hourly_stddev.get(hour, 1.0)

        if stddev < 0.001:
            return False, 0.0, "Insufficient hourly variance"

        deviation = abs(value - expected) / stddev
        is_anomaly = deviation > self.zscore_threshold

        if is_anomaly:
            reason = f"Seasonal deviation {deviation:.2f} (expected ~{expected:.2f} at hour {hour})"
        else:
            reason = ""

        return is_anomaly, deviation, reason

    def _detect_rolling_stats(self, metric: str, value: float) -> tuple[bool, float, str]:
        """Detect anomaly using rolling window statistics.

        Focuses on recent data trends rather than full history.

        Args:
            metric: Metric name
            value: Value to check

        Returns:
            Tuple of (is_anomaly, deviation, reason)
        """
        points = self.data.get(metric, [])
        if len(points) < 10:
            return False, 0.0, "Insufficient rolling data"

        # Use last 20 points for rolling stats
        recent_values = [p.value for p in points[-20:]]
        rolling_mean = sum(recent_values) / len(recent_values)
        rolling_std = self._calculate_stddev(recent_values)

        if rolling_std < 0.001:
            return False, 0.0, "Insufficient rolling variance"

        deviation = abs(value - rolling_mean) / rolling_std
        is_anomaly = deviation > self.zscore_threshold

        if is_anomaly:
            reason = f"Rolling deviation {deviation:.2f} from mean {rolling_mean:.2f}"
        else:
            reason = ""

        return is_anomaly, deviation, reason

    # ========================================================================
    # ENSEMBLE DETECTION
    # ========================================================================

    def detect_anomaly(
        self, metric: str, value: float, timestamp: datetime | None = None
    ) -> MLAnomaly | None:
        """Detect anomaly using ensemble of methods.

        Combines multiple detection algorithms with weighted voting.

        Args:
            metric: Metric name
            value: Value to check
            timestamp: When the value was recorded (default: now)

        Returns:
            MLAnomaly if detected, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        # Check minimum data requirement
        if len(self.data.get(metric, [])) < self.min_data_points:
            return None

        # Run all detection methods
        methods_triggered: list[DetectionMethod] = []
        deviations: list[float] = []
        reasons: list[str] = []

        # Adaptive Z-Score
        is_anom, dev, reason = self._detect_adaptive_zscore(metric, value)
        if is_anom:
            methods_triggered.append(DetectionMethod.ADAPTIVE_ZSCORE)
            deviations.append(dev)
            reasons.append(reason)

        # EMA Deviation
        is_anom, dev, reason = self._detect_ema_deviation(metric, value)
        if is_anom:
            methods_triggered.append(DetectionMethod.EMA_DEVIATION)
            deviations.append(dev)
            reasons.append(reason)

        # IQR Outlier
        is_anom, dev, reason = self._detect_iqr_outlier(metric, value)
        if is_anom:
            methods_triggered.append(DetectionMethod.IQR_OUTLIER)
            deviations.append(dev)
            reasons.append(reason)

        # Seasonal
        is_anom, dev, reason = self._detect_seasonal_anomaly(metric, value, timestamp)
        if is_anom:
            methods_triggered.append(DetectionMethod.SEASONAL)
            deviations.append(dev)
            reasons.append(reason)

        # Rolling Stats
        is_anom, dev, reason = self._detect_rolling_stats(metric, value)
        if is_anom:
            methods_triggered.append(DetectionMethod.ROLLING_STATS)
            deviations.append(dev)
            reasons.append(reason)

        # Ensemble voting - need at least 2 methods to agree
        # (adjusted by sensitivity)
        min_votes = max(1, int(2 - self.sensitivity))

        if len(methods_triggered) < min_votes:
            return None

        # Calculate confidence based on method agreement
        confidence = len(methods_triggered) / 5.0  # 5 methods total
        confidence = min(1.0, confidence * (1 + self.sensitivity * 0.5))

        # Calculate average deviation
        avg_deviation = sum(deviations) / len(deviations) if deviations else 0.0

        # Determine severity
        severity = self._determine_severity(avg_deviation, confidence)

        # Get expected value from stats
        expected = self.stats[metric].mean if metric in self.stats else value

        # Create message
        message = self._create_anomaly_message(metric, value, expected, methods_triggered, reasons)

        return MLAnomaly(
            metric=metric,
            timestamp=timestamp,
            value=value,
            expected=expected,
            deviation=avg_deviation,
            severity=severity,
            confidence=confidence,
            methods_triggered=methods_triggered,
            message=message,
        )

    def detect_all_anomalies(
        self, current_values: dict[str, float] | None = None
    ) -> list[MLAnomaly]:
        """Detect anomalies across all metrics.

        Args:
            current_values: Dict of metric -> current value.
                          If None, uses latest data point for each metric.

        Returns:
            List of detected anomalies
        """
        anomalies: list[MLAnomaly] = []
        timestamp = datetime.now(UTC)

        if current_values:
            for metric, value in current_values.items():
                anomaly = self.detect_anomaly(metric, value, timestamp)
                if anomaly:
                    anomalies.append(anomaly)
        else:
            for metric, points in self.data.items():
                if points:
                    latest = points[-1]
                    anomaly = self.detect_anomaly(metric, latest.value, latest.timestamp)
                    if anomaly:
                        anomalies.append(anomaly)

        return anomalies

    # ========================================================================
    # LEARNING AND ADAPTATION
    # ========================================================================

    def _learn_seasonal_pattern(self, metric: str) -> None:
        """Learn seasonal pattern from historical data.

        Groups data by hour of day and calculates expected values.
        """
        points = self.data.get(metric, [])
        if len(points) < 48:  # Need at least 2 days of data
            return

        # Group by hour
        hourly_values: dict[int, list[float]] = defaultdict(list)
        for point in points:
            hour = point.timestamp.hour
            hourly_values[hour].append(point.value)

        # Calculate baselines per hour
        hourly_baselines: dict[int, float] = {}
        hourly_stddev: dict[int, float] = {}

        for hour, values in hourly_values.items():
            if len(values) >= 2:
                hourly_baselines[hour] = sum(values) / len(values)
                hourly_stddev[hour] = self._calculate_stddev(values)

        if len(hourly_baselines) >= 12:  # Need at least half the hours
            self.seasonal_patterns[metric] = SeasonalPattern(
                metric=metric,
                period_hours=24,
                hourly_baselines=hourly_baselines,
                hourly_stddev=hourly_stddev,
            )

    def report_false_positive(self, metric: str) -> None:
        """Report a false positive for learning.

        Increases threshold for this metric to reduce future false positives.

        Args:
            metric: Metric that had false positive
        """
        self.false_positive_counts[metric] += 1

        # Adapt threshold after multiple false positives
        if self.false_positive_counts[metric] >= 3:
            self.logger.info(f"Adapting threshold for {metric} due to false positives")
            # Increase threshold (make less sensitive)
            self.zscore_threshold = min(4.0, self.zscore_threshold + 0.2)

    def confirm_anomaly(self, metric: str) -> None:
        """Confirm an anomaly was real.

        Args:
            metric: Metric with confirmed anomaly
        """
        self.confirmed_anomaly_counts[metric] += 1

    def get_accuracy_stats(self) -> dict[str, Any]:
        """Get accuracy statistics for the detector.

        Returns:
            Dictionary with accuracy metrics
        """
        total_fp = sum(self.false_positive_counts.values())
        total_confirmed = sum(self.confirmed_anomaly_counts.values())
        total = total_fp + total_confirmed

        accuracy = total_confirmed / total if total > 0 else 0.0

        return {
            "false_positives": total_fp,
            "confirmed_anomalies": total_confirmed,
            "accuracy": accuracy,
            "per_metric_fp": dict(self.false_positive_counts),
            "per_metric_confirmed": dict(self.confirmed_anomaly_counts),
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _calculate_stddev(self, values: list[float]) -> float:
        """Calculate standard deviation of a list of values."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

    def _determine_severity(self, deviation: float, confidence: float) -> AnomalySeverity:
        """Determine anomaly severity based on deviation and confidence."""
        score = deviation * confidence

        if score > 4.0:
            return AnomalySeverity.CRITICAL
        elif score > 2.0:
            return AnomalySeverity.WARNING
        else:
            return AnomalySeverity.INFO

    def _create_anomaly_message(
        self,
        metric: str,
        value: float,
        expected: float,
        methods: list[DetectionMethod],
        reasons: list[str],
    ) -> str:
        """Create human-readable anomaly message."""
        method_names = [m.value for m in methods]
        pct_diff = ((value - expected) / expected * 100) if expected != 0 else 0

        direction = "above" if value > expected else "below"

        msg = (
            f"{metric}: {value:.2f} is {abs(pct_diff):.1f}% {direction} "
            f"expected ({expected:.2f}). "
            f"Detected by {len(methods)} method(s): {', '.join(method_names)}"
        )

        return msg

    # ========================================================================
    # STATUS AND REPORTING
    # ========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get current detector status.

        Returns:
            Status dictionary
        """
        return {
            "sensitivity": self.sensitivity,
            "min_data_points": self.min_data_points,
            "window_size": self.window_size,
            "metrics_tracked": list(self.data.keys()),
            "data_points_per_metric": {k: len(v) for k, v in self.data.items()},
            "seasonal_patterns_learned": list(self.seasonal_patterns.keys()),
            "thresholds": {
                "zscore": self.zscore_threshold,
                "iqr_multiplier": self.iqr_multiplier,
                "ema_deviation": self.ema_deviation_threshold,
            },
            "accuracy": self.get_accuracy_stats(),
        }

    def get_metric_summary(self, metric: str) -> dict[str, Any] | None:
        """Get summary for a specific metric.

        Args:
            metric: Metric name

        Returns:
            Summary dictionary or None if metric not found
        """
        if metric not in self.stats:
            return None

        stats = self.stats[metric]
        has_seasonal = metric in self.seasonal_patterns

        return {
            "metric": metric,
            "data_points": len(self.data.get(metric, [])),
            "statistics": {
                "mean": stats.mean,
                "median": stats.median,
                "stddev": stats.stddev,
                "min": stats.min_val,
                "max": stats.max_val,
                "p95": stats.p95,
                "p99": stats.p99,
                "ema": stats.ema,
            },
            "has_seasonal_pattern": has_seasonal,
            "false_positives": self.false_positive_counts.get(metric, 0),
            "confirmed_anomalies": self.confirmed_anomaly_counts.get(metric, 0),
        }
