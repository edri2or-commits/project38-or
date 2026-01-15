"""MonitoringAgent - Specialized Agent for Observability.

Handles all monitoring and alerting operations:
- Collect metrics from various sources
- Detect anomalies using ML
- Send alerts via multiple channels
- Track performance baselines
- Generate reports

Integrates with:
- MLAnomalyDetector for anomaly detection
- AlertManager for notifications
- PerformanceBaseline for trend analysis
- MetricsCollector for data gathering

Example:
    >>> from src.multi_agent.monitoring_agent import MonitoringAgent
    >>>
    >>> agent = MonitoringAgent()
    >>> result = await agent.execute_task(AgentTask(
    ...     task_type="check_anomalies",
    ...     parameters={"metric": "response_time"}
    ... ))
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.multi_agent.base import (
    AgentCapability,
    AgentDomain,
    AgentResult,
    AgentTask,
    SpecializedAgent,
)

if TYPE_CHECKING:
    from src.alert_manager import AlertManager
    from src.ml_anomaly_detector import MLAnomalyDetector
    from src.performance_baseline import PerformanceBaseline


@dataclass
class MonitoringConfig:
    """Configuration for monitoring operations.

    Attributes:
        alert_webhook_url: URL for n8n alerts
        telegram_chat_id: Telegram chat for notifications
        anomaly_threshold: Confidence threshold for anomaly alerts
        check_interval_seconds: How often to check metrics
    """

    alert_webhook_url: str = ""
    telegram_chat_id: str = ""
    anomaly_threshold: float = 0.75
    check_interval_seconds: int = 60


class MonitoringAgent(SpecializedAgent):
    """Specialized agent for observability and alerting.

    Capabilities:
    - check_anomalies: Detect anomalies in metrics
    - send_alert: Send alert via configured channels
    - collect_metrics: Gather metrics from endpoints
    - analyze_performance: Analyze performance trends
    - generate_report: Create monitoring report

    Attributes:
        anomaly_detector: MLAnomalyDetector for anomaly detection
        alert_manager: AlertManager for notifications
        performance_baseline: PerformanceBaseline for trends
        config: Monitoring configuration
    """

    def __init__(
        self,
        anomaly_detector: "MLAnomalyDetector | None" = None,
        alert_manager: "AlertManager | None" = None,
        performance_baseline: "PerformanceBaseline | None" = None,
        config: MonitoringConfig | None = None,
        agent_id: str | None = None,
    ):
        """Initialize MonitoringAgent.

        Args:
            anomaly_detector: MLAnomalyDetector for anomaly detection
            alert_manager: AlertManager for notifications
            performance_baseline: PerformanceBaseline for trends
            config: Monitoring configuration
            agent_id: Unique agent identifier
        """
        super().__init__(agent_id=agent_id, domain=AgentDomain.MONITORING)
        self.anomaly_detector = anomaly_detector
        self.alert_manager = alert_manager
        self.performance_baseline = performance_baseline
        self.config = config or MonitoringConfig()
        self.logger = logging.getLogger(f"agent.monitoring.{self.agent_id}")

        # Metrics storage
        self._recent_metrics: dict[str, list[dict[str, Any]]] = {}
        self._anomaly_history: list[dict[str, Any]] = []

        # Register message handlers
        self.register_message_handler("anomaly_detected", self._handle_anomaly_notification)
        self.register_message_handler("metric_request", self._handle_metric_request)

    @property
    def capabilities(self) -> list[AgentCapability]:
        """List of monitoring capabilities."""
        return [
            AgentCapability(
                name="check_anomalies",
                domain=AgentDomain.MONITORING,
                description="Detect anomalies in metrics using ML",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=0,
            ),
            AgentCapability(
                name="send_alert",
                domain=AgentDomain.MONITORING,
                description="Send alert via configured channels",
                requires_approval=False,
                max_concurrent=10,
                cooldown_seconds=5,
            ),
            AgentCapability(
                name="collect_metrics",
                domain=AgentDomain.MONITORING,
                description="Gather metrics from endpoints",
                requires_approval=False,
                max_concurrent=3,
                cooldown_seconds=10,
            ),
            AgentCapability(
                name="analyze_performance",
                domain=AgentDomain.MONITORING,
                description="Analyze performance trends",
                requires_approval=False,
                max_concurrent=2,
                cooldown_seconds=30,
            ),
            AgentCapability(
                name="generate_report",
                domain=AgentDomain.MONITORING,
                description="Generate monitoring report",
                requires_approval=False,
                max_concurrent=1,
                cooldown_seconds=60,
            ),
            AgentCapability(
                name="check_health",
                domain=AgentDomain.MONITORING,
                description="Check system health status",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=0,
            ),
        ]

    async def _execute_task_internal(self, task: AgentTask) -> AgentResult:
        """Execute monitoring task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """
        task_handlers = {
            "check_anomalies": self._handle_check_anomalies,
            "send_alert": self._handle_send_alert,
            "collect_metrics": self._handle_collect_metrics,
            "analyze_performance": self._handle_analyze_performance,
            "generate_report": self._handle_generate_report,
            "check_health": self._handle_check_health,
        }

        handler = task_handlers.get(task.task_type)
        if not handler:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Unknown task type: {task.task_type}",
            )

        return await handler(task)

    async def _handle_check_anomalies(self, task: AgentTask) -> AgentResult:
        """Check for anomalies in metrics.

        Args:
            task: Task with parameters:
                - metric_name: Name of metric to check
                - value: Current metric value
                - sensitivity: Detection sensitivity (0.0-1.0)

        Returns:
            AgentResult with anomaly info
        """
        metric_name = task.parameters.get("metric_name", "default")
        value = task.parameters.get("value")

        if value is None:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="metric value is required",
            )

        try:
            anomalies = []
            confidence = 0.0
            severity = "INFO"

            # Use ML detector if available
            if self.anomaly_detector:
                from src.ml_anomaly_detector import DataPoint

                data_point = DataPoint(
                    timestamp=datetime.now(UTC),
                    value=float(value),
                    metric_name=metric_name,
                )
                self.anomaly_detector.add_data_point(data_point)

                detected = self.anomaly_detector.detect_anomalies()
                if detected:
                    anomalies = [
                        {
                            "metric": a.metric_name,
                            "value": a.value,
                            "confidence": a.confidence,
                            "severity": a.severity.value,
                            "algorithms": a.triggered_algorithms,
                        }
                        for a in detected
                    ]
                    confidence = detected[0].confidence
                    severity = detected[0].severity.value
            else:
                # Simple threshold-based detection
                self._store_metric(metric_name, value)
                recent = self._recent_metrics.get(metric_name, [])
                if len(recent) >= 10:
                    avg = sum(m["value"] for m in recent[-10:]) / 10
                    std_dev = (
                        sum((m["value"] - avg) ** 2 for m in recent[-10:]) / 10
                    ) ** 0.5
                    if std_dev > 0 and abs(value - avg) > 3 * std_dev:
                        anomalies = [{
                            "metric": metric_name,
                            "value": value,
                            "confidence": 0.8,
                            "severity": "WARNING",
                            "algorithms": ["z_score"],
                        }]
                        confidence = 0.8
                        severity = "WARNING"

            is_anomaly = len(anomalies) > 0 and confidence >= self.config.anomaly_threshold

            if is_anomaly:
                self._anomaly_history.append({
                    "timestamp": datetime.now(UTC).isoformat(),
                    "metric": metric_name,
                    "value": value,
                    "confidence": confidence,
                    "severity": severity,
                })

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "is_anomaly": is_anomaly,
                    "anomalies": anomalies,
                    "confidence": confidence,
                    "severity": severity,
                },
                recommendations=(
                    [
                        f"Investigate {metric_name} - anomaly detected "
                        f"with {confidence:.0%} confidence",
                        "Consider triggering self-healing if pattern persists",
                    ]
                    if is_anomaly
                    else []
                ),
            )

        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_send_alert(self, task: AgentTask) -> AgentResult:
        """Send alert via configured channels.

        Args:
            task: Task with parameters:
                - title: Alert title
                - message: Alert message
                - severity: Alert severity (info, warning, critical)
                - channel: Target channel (telegram, n8n, all)

        Returns:
            AgentResult with send status
        """
        title = task.parameters.get("title", "Alert")
        message = task.parameters.get("message", "")
        severity = task.parameters.get("severity", "info")
        channel = task.parameters.get("channel", "all")

        if not message:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="message is required",
            )

        try:
            results = []

            if self.alert_manager:
                from src.alert_manager import Alert, AlertSeverity

                severity_map = {
                    "info": AlertSeverity.INFO,
                    "warning": AlertSeverity.WARNING,
                    "critical": AlertSeverity.CRITICAL,
                }
                alert = Alert(
                    title=title,
                    message=message,
                    severity=severity_map.get(severity, AlertSeverity.INFO),
                )
                result = await self.alert_manager.send(alert)
                results.append({
                    "channel": "alert_manager",
                    "success": result.success,
                    "suppressed": result.suppressed,
                })
            else:
                # Direct HTTP notification if no alert manager
                import httpx

                if channel in ("n8n", "all") and self.config.alert_webhook_url:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            self.config.alert_webhook_url,
                            json={
                                "title": title,
                                "message": message,
                                "severity": severity,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                            timeout=10,
                        )
                        results.append({
                            "channel": "n8n",
                            "success": response.status_code < 400,
                            "status_code": response.status_code,
                        })

            return AgentResult(
                task_id=task.task_id,
                success=all(r.get("success", False) for r in results) if results else True,
                data={
                    "results": results,
                    "channels_notified": len(results),
                },
            )

        except Exception as e:
            self.logger.error(f"Alert send failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_collect_metrics(self, task: AgentTask) -> AgentResult:
        """Collect metrics from endpoints.

        Args:
            task: Task with parameters:
                - url: Metrics endpoint URL
                - metric_names: List of metric names to collect

        Returns:
            AgentResult with collected metrics
        """
        url = task.parameters.get("url")
        metric_names = task.parameters.get("metric_names", [])

        if not url:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="url is required",
            )

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                response.raise_for_status()

                data = response.json()
                collected = {}

                # Extract requested metrics
                if metric_names:
                    for name in metric_names:
                        if name in data:
                            collected[name] = data[name]
                            self._store_metric(name, data[name])
                else:
                    # Collect all numeric values
                    for key, value in data.items():
                        if isinstance(value, (int, float)):
                            collected[key] = value
                            self._store_metric(key, value)

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "metrics": collected,
                        "source": url,
                        "collected_at": datetime.now(UTC).isoformat(),
                    },
                )

        except Exception as e:
            self.logger.error(f"Metrics collection failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_analyze_performance(self, task: AgentTask) -> AgentResult:
        """Analyze performance trends.

        Args:
            task: Task with parameters:
                - metric_name: Metric to analyze
                - window_hours: Analysis window in hours

        Returns:
            AgentResult with performance analysis
        """
        metric_name = task.parameters.get("metric_name")
        window_hours = task.parameters.get("window_hours", 24)

        if not metric_name:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="metric_name is required",
            )

        try:
            if self.performance_baseline:
                analysis = self.performance_baseline.analyze_trends(
                    metric_name=metric_name,
                    window_hours=window_hours,
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "metric": metric_name,
                        "trend": analysis.get("trend", "stable"),
                        "baseline": analysis.get("baseline", {}),
                        "current": analysis.get("current", {}),
                    },
                )
            else:
                # Simple trend analysis from stored metrics
                recent = self._recent_metrics.get(metric_name, [])
                if len(recent) < 5:
                    return AgentResult(
                        task_id=task.task_id,
                        success=True,
                        data={
                            "metric": metric_name,
                            "trend": "insufficient_data",
                            "data_points": len(recent),
                        },
                    )

                values = [m["value"] for m in recent]
                first_half = sum(values[: len(values) // 2]) / (len(values) // 2)
                second_half = sum(values[len(values) // 2 :]) / (
                    len(values) - len(values) // 2
                )

                if second_half > first_half * 1.1:
                    trend = "increasing"
                elif second_half < first_half * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "metric": metric_name,
                        "trend": trend,
                        "first_half_avg": first_half,
                        "second_half_avg": second_half,
                        "data_points": len(values),
                    },
                )

        except Exception as e:
            self.logger.error(f"Performance analysis failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_generate_report(self, task: AgentTask) -> AgentResult:
        """Generate monitoring report.

        Args:
            task: Task with parameters:
                - report_type: Type of report (summary, detailed, anomalies)
                - time_range_hours: Report time range

        Returns:
            AgentResult with report data
        """
        report_type = task.parameters.get("report_type", "summary")
        time_range_hours = task.parameters.get("time_range_hours", 24)

        try:
            report = {
                "generated_at": datetime.now(UTC).isoformat(),
                "report_type": report_type,
                "time_range_hours": time_range_hours,
                "agent_status": self.get_status(),
            }

            if report_type in ("summary", "detailed"):
                report["metrics_tracked"] = list(self._recent_metrics.keys())
                report["total_data_points"] = sum(
                    len(v) for v in self._recent_metrics.values()
                )

            if report_type in ("anomalies", "detailed"):
                report["anomaly_count"] = len(self._anomaly_history)
                report["recent_anomalies"] = self._anomaly_history[-10:]

            if report_type == "detailed":
                report["metric_summaries"] = {}
                for name, values in self._recent_metrics.items():
                    if values:
                        nums = [v["value"] for v in values]
                        report["metric_summaries"][name] = {
                            "count": len(nums),
                            "min": min(nums),
                            "max": max(nums),
                            "avg": sum(nums) / len(nums),
                        }

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data=report,
            )

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_check_health(self, task: AgentTask) -> AgentResult:
        """Check overall system health.

        Args:
            task: Task with parameters:
                - endpoints: List of endpoints to check

        Returns:
            AgentResult with health status
        """
        endpoints = task.parameters.get("endpoints", [])

        if not endpoints:
            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "status": "unknown",
                    "message": "No endpoints configured",
                },
            )

        try:
            import httpx

            results = []
            async with httpx.AsyncClient() as client:
                for endpoint in endpoints:
                    try:
                        response = await client.get(endpoint, timeout=5)
                        results.append({
                            "endpoint": endpoint,
                            "status": "healthy" if response.status_code == 200 else "unhealthy",
                            "status_code": response.status_code,
                            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                        })
                    except Exception as e:
                        results.append({
                            "endpoint": endpoint,
                            "status": "unreachable",
                            "error": str(e),
                        })

            healthy_count = sum(1 for r in results if r.get("status") == "healthy")
            overall_status = (
                "healthy"
                if healthy_count == len(results)
                else "degraded"
                if healthy_count > 0
                else "unhealthy"
            )

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "overall_status": overall_status,
                    "healthy_count": healthy_count,
                    "total_endpoints": len(results),
                    "endpoint_results": results,
                },
            )

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    def _store_metric(self, name: str, value: Any) -> None:
        """Store a metric value.

        Args:
            name: Metric name
            value: Metric value
        """
        if name not in self._recent_metrics:
            self._recent_metrics[name] = []

        self._recent_metrics[name].append({
            "value": float(value) if isinstance(value, (int, float)) else value,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # Keep only last 1000 values per metric
        if len(self._recent_metrics[name]) > 1000:
            self._recent_metrics[name] = self._recent_metrics[name][-1000:]

    async def _handle_anomaly_notification(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle anomaly notification from other agents.

        Args:
            payload: Anomaly details

        Returns:
            Acknowledgment
        """
        self._anomaly_history.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "source": payload.get("source", "unknown"),
            "metric": payload.get("metric"),
            "value": payload.get("value"),
            "severity": payload.get("severity"),
        })
        return {"acknowledged": True}

    async def _handle_metric_request(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle metric request from other agents.

        Args:
            payload: Request with metric_name

        Returns:
            Metric data
        """
        metric_name = payload.get("metric_name")
        if metric_name and metric_name in self._recent_metrics:
            return {
                "metric_name": metric_name,
                "values": self._recent_metrics[metric_name][-100:],
            }
        return {"available_metrics": list(self._recent_metrics.keys())}

    def get_anomaly_history(self) -> list[dict[str, Any]]:
        """Get recent anomaly history.

        Returns:
            List of recent anomalies
        """
        return self._anomaly_history.copy()
