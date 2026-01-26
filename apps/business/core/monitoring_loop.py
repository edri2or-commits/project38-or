"""
Monitoring Loop - Continuous health monitoring with anomaly detection.

This module provides a scheduler-based monitoring loop that:
1. Collects metrics from Railway health endpoints
2. Feeds metrics to MLAnomalyDetector for analysis
3. Routes detected anomalies to AnomalyResponseIntegrator
4. Triggers self-healing actions via AutonomousController

Architecture:
    Railway /health → MetricsCollector → MLAnomalyDetector
                                              ↓
                                    AnomalyResponseIntegrator
                                              ↓
                                    AutonomousController
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

from apps.business.core.ml_anomaly_detector import DetectionMethod, MLAnomalyDetector

if TYPE_CHECKING:
    from apps.business.core.anomaly_response_integrator import AnomalyResponseIntegrator
    from apps.business.core.autonomous_controller import AutonomousController

logger = logging.getLogger(__name__)


class MonitoringState(Enum):
    """States of the monitoring loop."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class MetricsEndpoint:
    """Configuration for a metrics endpoint."""

    url: str
    name: str
    timeout: float = 10.0
    enabled: bool = True
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CollectedMetrics:
    """Container for collected metrics from an endpoint."""

    endpoint_name: str
    timestamp: datetime
    latency_ms: float
    status_code: int
    is_healthy: bool
    metrics: dict[str, float]
    error: str | None = None


@dataclass
class MonitoringConfig:
    """Configuration for the monitoring loop."""

    # Collection interval in seconds
    collection_interval: float = 30.0

    # Minimum interval between collections (rate limiting)
    min_interval: float = 5.0

    # Maximum consecutive errors before pausing
    max_consecutive_errors: int = 5

    # Pause duration after max errors (seconds)
    error_pause_duration: float = 60.0

    # Enable anomaly detection
    anomaly_detection_enabled: bool = True

    # Enable self-healing responses
    self_healing_enabled: bool = True

    # Metrics history size (for trend analysis)
    history_size: int = 1000


class MetricsCollector:
    """Collects metrics from configured endpoints."""

    def __init__(self, endpoints: list[MetricsEndpoint] | None = None) -> None:
        """
        Initialize the metrics collector.

        Args:
            endpoints: List of endpoints to collect metrics from
        """
        self.endpoints: list[MetricsEndpoint] = endpoints or []
        self._client: httpx.AsyncClient | None = None
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")

    def add_endpoint(self, endpoint: MetricsEndpoint) -> None:
        """Add an endpoint to collect metrics from."""
        self.endpoints.append(endpoint)
        self.logger.info(f"Added endpoint: {endpoint.name} ({endpoint.url})")

    def remove_endpoint(self, name: str) -> bool:
        """Remove an endpoint by name."""
        for i, ep in enumerate(self.endpoints):
            if ep.name == name:
                del self.endpoints[i]
                self.logger.info(f"Removed endpoint: {name}")
                return True
        return False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def collect_from_endpoint(self, endpoint: MetricsEndpoint) -> CollectedMetrics:
        """
        Collect metrics from a single endpoint.

        Args:
            endpoint: The endpoint configuration

        Returns:
            CollectedMetrics with the collected data
        """
        timestamp = datetime.now(UTC)
        start_time = time.perf_counter()

        try:
            client = await self._get_client()
            response = await client.get(
                endpoint.url,
                headers=endpoint.headers,
                timeout=endpoint.timeout,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Parse response
            is_healthy = response.status_code == 200
            metrics: dict[str, float] = {}

            if response.status_code == 200:
                try:
                    data = response.json()
                    metrics = self._extract_metrics(data)
                except Exception as e:
                    self.logger.warning(f"Failed to parse metrics JSON: {e}")

            # Always include latency as a metric
            metrics["response_latency_ms"] = latency_ms
            metrics["status_code"] = float(response.status_code)

            return CollectedMetrics(
                endpoint_name=endpoint.name,
                timestamp=timestamp,
                latency_ms=latency_ms,
                status_code=response.status_code,
                is_healthy=is_healthy,
                metrics=metrics,
            )

        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CollectedMetrics(
                endpoint_name=endpoint.name,
                timestamp=timestamp,
                latency_ms=latency_ms,
                status_code=0,
                is_healthy=False,
                metrics={"response_latency_ms": latency_ms, "timeout": 1.0},
                error="Request timeout",
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(f"Error collecting from {endpoint.name}: {e}")
            return CollectedMetrics(
                endpoint_name=endpoint.name,
                timestamp=timestamp,
                latency_ms=latency_ms,
                status_code=0,
                is_healthy=False,
                metrics={"response_latency_ms": latency_ms, "error": 1.0},
                error=str(e),
            )

    def _extract_metrics(self, data: dict[str, Any]) -> dict[str, float]:
        """
        Extract numeric metrics from response data.

        Args:
            data: JSON response data

        Returns:
            Dictionary of metric name to value
        """
        metrics: dict[str, float] = {}

        # Handle Railway health endpoint format
        if "status" in data:
            metrics["health_status"] = 1.0 if data["status"] == "healthy" else 0.0

        if "database" in data:
            metrics["database_connected"] = 1.0 if data["database"] == "connected" else 0.0

        # Extract any numeric values recursively
        self._extract_numeric_values(data, "", metrics)

        return metrics

    def _extract_numeric_values(
        self,
        data: Any,
        prefix: str,
        metrics: dict[str, float],
    ) -> None:
        """Recursively extract numeric values from nested data."""
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix}_{key}" if prefix else key
                self._extract_numeric_values(value, new_prefix, metrics)
        elif isinstance(data, (int, float)):
            if prefix and prefix not in metrics:
                metrics[prefix] = float(data)

    async def collect_all(self) -> list[CollectedMetrics]:
        """
        Collect metrics from all enabled endpoints.

        Returns:
            List of CollectedMetrics from all endpoints
        """
        enabled_endpoints = [ep for ep in self.endpoints if ep.enabled]

        if not enabled_endpoints:
            self.logger.warning("No enabled endpoints to collect from")
            return []

        tasks = [self.collect_from_endpoint(ep) for ep in enabled_endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        collected: list[CollectedMetrics] = []
        for result in results:
            if isinstance(result, CollectedMetrics):
                collected.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Collection task failed: {result}")

        return collected

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class MonitoringLoop:
    """
    Main monitoring loop that orchestrates metric collection and anomaly response.

    This class connects:
    - MetricsCollector: Gathers metrics from endpoints
    - MLAnomalyDetector: Detects anomalies in metrics
    - AnomalyResponseIntegrator: Determines responses to anomalies
    - AutonomousController: Executes self-healing actions
    """

    def __init__(
        self,
        config: MonitoringConfig | None = None,
        collector: MetricsCollector | None = None,
        detector: MLAnomalyDetector | None = None,
        integrator: AnomalyResponseIntegrator | None = None,
    ) -> None:
        """
        Initialize the monitoring loop.

        Args:
            config: Monitoring configuration
            collector: Metrics collector instance
            detector: ML anomaly detector instance
            integrator: Anomaly response integrator instance
        """
        self.config = config or MonitoringConfig()
        self.collector = collector or MetricsCollector()
        self.detector = detector or MLAnomalyDetector()
        self.integrator = integrator

        self.state = MonitoringState.STOPPED
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Statistics
        self.stats = {
            "collections_total": 0,
            "collections_successful": 0,
            "collections_failed": 0,
            "anomalies_detected": 0,
            "healing_actions_triggered": 0,
            "consecutive_errors": 0,
            "last_collection_time": None,
            "last_anomaly_time": None,
        }

        # Metrics history for analysis
        self._metrics_history: list[CollectedMetrics] = []

        self.logger = logging.getLogger(f"{__name__}.MonitoringLoop")

    @property
    def is_running(self) -> bool:
        """Check if the monitoring loop is running."""
        return self.state == MonitoringState.RUNNING

    def set_integrator(self, integrator: AnomalyResponseIntegrator) -> None:
        """Set the anomaly response integrator."""
        self.integrator = integrator
        self.logger.info("Anomaly response integrator set")

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self.state == MonitoringState.RUNNING:
            self.logger.warning("Monitoring loop is already running")
            return

        self.state = MonitoringState.STARTING
        self._stop_event.clear()

        self.logger.info(f"Starting monitoring loop (interval: {self.config.collection_interval}s)")

        self._task = asyncio.create_task(self._run_loop())
        self.state = MonitoringState.RUNNING

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        if self.state == MonitoringState.STOPPED:
            self.logger.warning("Monitoring loop is already stopped")
            return

        self.logger.info("Stopping monitoring loop...")
        self._stop_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        await self.collector.close()
        self.state = MonitoringState.STOPPED
        self.logger.info("Monitoring loop stopped")

    async def pause(self) -> None:
        """Pause the monitoring loop."""
        if self.state == MonitoringState.RUNNING:
            self.state = MonitoringState.PAUSED
            self.logger.info("Monitoring loop paused")

    async def resume(self) -> None:
        """Resume the monitoring loop."""
        if self.state == MonitoringState.PAUSED:
            self.state = MonitoringState.RUNNING
            self.logger.info("Monitoring loop resumed")

    async def _run_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            if self.state == MonitoringState.PAUSED:
                await asyncio.sleep(1.0)
                continue

            try:
                await self._run_collection_cycle()
                self.stats["consecutive_errors"] = 0
            except Exception as e:
                self.stats["consecutive_errors"] += 1
                self.logger.error(f"Collection cycle failed: {e}")

                if self.stats["consecutive_errors"] >= self.config.max_consecutive_errors:
                    self.logger.warning(
                        f"Max consecutive errors reached "
                        f"({self.config.max_consecutive_errors}), pausing..."
                    )
                    self.state = MonitoringState.ERROR
                    await asyncio.sleep(self.config.error_pause_duration)
                    self.state = MonitoringState.RUNNING
                    self.stats["consecutive_errors"] = 0

            # Wait for next collection interval
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.collection_interval,
                )
            except TimeoutError:
                pass  # Normal timeout, continue loop

    async def _run_collection_cycle(self) -> None:
        """Run a single collection cycle."""
        self.stats["collections_total"] += 1
        self.stats["last_collection_time"] = datetime.now(UTC).isoformat()

        # Collect metrics from all endpoints
        collected = await self.collector.collect_all()

        if not collected:
            self.stats["collections_failed"] += 1
            return

        # Track successful collections
        successful = [c for c in collected if c.error is None]
        if successful:
            self.stats["collections_successful"] += 1
        else:
            self.stats["collections_failed"] += 1

        # Store in history
        self._update_history(collected)

        # Skip anomaly detection if disabled
        if not self.config.anomaly_detection_enabled:
            return

        # Process each collected metric set
        for metrics_data in collected:
            await self._process_metrics(metrics_data)

    def _update_history(self, collected: list[CollectedMetrics]) -> None:
        """Update metrics history."""
        self._metrics_history.extend(collected)

        # Trim to configured size
        if len(self._metrics_history) > self.config.history_size:
            excess = len(self._metrics_history) - self.config.history_size
            self._metrics_history = self._metrics_history[excess:]

    async def _process_metrics(self, metrics_data: CollectedMetrics) -> None:
        """
        Process collected metrics through anomaly detection and response.

        Args:
            metrics_data: The collected metrics to process
        """
        # Feed each metric to the detector
        for metric_name, value in metrics_data.metrics.items():
            # Create a unique metric key combining endpoint and metric name
            full_metric_name = f"{metrics_data.endpoint_name}.{metric_name}"

            # Run anomaly detection
            detection_result = self.detector.detect_anomaly(
                metric=full_metric_name,
                value=value,
            )

            # detect_anomaly returns MLAnomaly | None
            if detection_result is not None:
                self.stats["anomalies_detected"] += 1
                self.stats["last_anomaly_time"] = datetime.now(UTC).isoformat()

                self.logger.warning(
                    f"Anomaly detected: {full_metric_name}={value} "
                    f"(confidence: {detection_result.confidence:.2f})"
                )

                # Route to integrator if available and enabled
                if self.integrator and self.config.self_healing_enabled:
                    await self._handle_anomaly(
                        metric_name=metric_name,
                        value=value,
                        detection_result=detection_result,
                    )

    async def _handle_anomaly(
        self,
        metric_name: str,
        value: float,
        detection_result: Any,
    ) -> None:
        """
        Handle a detected anomaly through the response integrator.

        Args:
            metric_name: Name of the metric with anomaly
            value: The anomalous value
            detection_result: Result from MLAnomalyDetector
        """
        if not self.integrator:
            return

        try:
            response = await self.integrator.handle_anomaly(
                metric_name=metric_name,
                value=value,
                detection_result=detection_result,
            )

            if response.action_taken:
                self.stats["healing_actions_triggered"] += 1
                self.logger.info(
                    f"Self-healing action executed for {metric_name}: {response.action_taken}"
                )

        except Exception as e:
            self.logger.error(f"Failed to handle anomaly for {metric_name}: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        return {
            **self.stats,
            "state": self.state.value,
            "endpoints_count": len(self.collector.endpoints),
            "enabled_endpoints": sum(1 for ep in self.collector.endpoints if ep.enabled),
            "history_size": len(self._metrics_history),
            "detector_algorithms": len(DetectionMethod),
        }

    def get_recent_metrics(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent metrics from history."""
        recent = self._metrics_history[-limit:] if self._metrics_history else []
        return [
            {
                "endpoint": m.endpoint_name,
                "timestamp": m.timestamp.isoformat(),
                "latency_ms": m.latency_ms,
                "is_healthy": m.is_healthy,
                "metrics": m.metrics,
                "error": m.error,
            }
            for m in recent
        ]


def create_railway_monitoring_loop(
    railway_url: str = "https://or-infra.com",
    controller: AutonomousController | None = None,
    config: MonitoringConfig | None = None,
) -> MonitoringLoop:
    """
    Create a monitoring loop configured for Railway deployment.

    Args:
        railway_url: Base URL of the Railway deployment
        controller: Optional AutonomousController for self-healing
        config: Optional monitoring configuration

    Returns:
        Configured MonitoringLoop instance
    """
    # Create collector with Railway endpoints
    collector = MetricsCollector()
    collector.add_endpoint(
        MetricsEndpoint(
            url=f"{railway_url}/api/health",
            name="railway_health",
            timeout=10.0,
        )
    )
    collector.add_endpoint(
        MetricsEndpoint(
            url=f"{railway_url}/api/metrics/summary",
            name="railway_metrics",
            timeout=15.0,
        )
    )

    # Create detector with appropriate sensitivity
    detector = MLAnomalyDetector(sensitivity=0.7)

    # Create the loop
    loop = MonitoringLoop(
        config=config or MonitoringConfig(),
        collector=collector,
        detector=detector,
    )

    # If controller provided, create and set integrator
    if controller:
        # Lazy import to avoid circular dependency issues
        from apps.business.core.anomaly_response_integrator import AnomalyResponseIntegrator

        integrator = AnomalyResponseIntegrator(
            detector=detector,
            controller=controller,
        )
        loop.set_integrator(integrator)

    return loop
