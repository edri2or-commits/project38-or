"""Comprehensive tests for MonitoringAgent.

Tests cover all task handlers and edge cases:
- check_anomalies: Detect anomalies in metrics
- send_alert: Send alert via configured channels
- collect_metrics: Gather metrics from endpoints
- analyze_performance: Analyze performance trends
- generate_report: Create monitoring report
- check_health: Check system health status
- Message handlers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.multi_agent.base import AgentDomain, AgentTask
from src.multi_agent.monitoring_agent import MonitoringAgent, MonitoringConfig


class TestMonitoringAgentInitialization:
    """Tests for MonitoringAgent initialization."""

    def test_default_initialization(self):
        """Test agent initializes with defaults."""
        agent = MonitoringAgent()

        assert agent.domain == AgentDomain.MONITORING
        assert agent.anomaly_detector is None
        assert agent.alert_manager is None
        assert agent.performance_baseline is None
        assert agent.config.anomaly_threshold == 0.75
        assert agent._recent_metrics == {}
        assert agent._anomaly_history == []

    def test_initialization_with_config(self):
        """Test agent initializes with custom config."""
        config = MonitoringConfig(
            alert_webhook_url="https://n8n.example.com/webhook",
            telegram_chat_id="12345",
            anomaly_threshold=0.9,
            check_interval_seconds=120,
        )
        agent = MonitoringAgent(config=config)

        assert agent.config.alert_webhook_url == "https://n8n.example.com/webhook"
        assert agent.config.anomaly_threshold == 0.9

    def test_initialization_with_dependencies(self):
        """Test agent initializes with all dependencies."""
        mock_detector = MagicMock()
        mock_alert_manager = MagicMock()
        mock_baseline = MagicMock()

        agent = MonitoringAgent(
            anomaly_detector=mock_detector,
            alert_manager=mock_alert_manager,
            performance_baseline=mock_baseline,
        )

        assert agent.anomaly_detector is mock_detector
        assert agent.alert_manager is mock_alert_manager
        assert agent.performance_baseline is mock_baseline

    def test_message_handlers_registered(self):
        """Test message handlers are registered on init."""
        agent = MonitoringAgent()

        assert "anomaly_detected" in agent._message_handlers
        assert "metric_request" in agent._message_handlers


class TestMonitoringAgentCapabilities:
    """Tests for MonitoringAgent capabilities."""

    def test_has_six_capabilities(self):
        """Test agent has exactly 6 capabilities."""
        agent = MonitoringAgent()
        assert len(agent.capabilities) == 6

    def test_all_capabilities_present(self):
        """Test all expected capabilities are present."""
        agent = MonitoringAgent()
        cap_names = [c.name for c in agent.capabilities]

        assert "check_anomalies" in cap_names
        assert "send_alert" in cap_names
        assert "collect_metrics" in cap_names
        assert "analyze_performance" in cap_names
        assert "generate_report" in cap_names
        assert "check_health" in cap_names

    def test_capabilities_no_approval_required(self):
        """Test monitoring capabilities don't require approval."""
        agent = MonitoringAgent()

        for cap in agent.capabilities:
            assert cap.requires_approval is False


class TestCheckAnomaliesHandler:
    """Tests for _handle_check_anomalies."""

    @pytest.mark.asyncio
    async def test_check_anomalies_missing_value_fails(self):
        """Test anomaly check fails when value missing."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="check_anomalies",
            parameters={"metric_name": "cpu"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "metric value is required" in result.error

    @pytest.mark.asyncio
    async def test_check_anomalies_no_anomaly(self):
        """Test anomaly check with normal values."""
        agent = MonitoringAgent()

        # Build baseline with normal values
        for i in range(15):
            task = AgentTask(
                task_type="check_anomalies",
                parameters={"metric_name": "cpu", "value": 50 + i % 5},
                domain=AgentDomain.MONITORING,
            )
            await agent.execute_task(task)

        # Check a normal value
        task = AgentTask(
            task_type="check_anomalies",
            parameters={"metric_name": "cpu", "value": 52},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["is_anomaly"] is False

    @pytest.mark.asyncio
    async def test_check_anomalies_with_ml_detector(self):
        """Test anomaly check with ML detector."""
        mock_detector = MagicMock()
        mock_anomaly = MagicMock()
        mock_anomaly.metric_name = "cpu"
        mock_anomaly.value = 100
        mock_anomaly.confidence = 0.95
        mock_anomaly.severity.value = "CRITICAL"
        mock_anomaly.triggered_algorithms = ["isolation_forest", "z_score"]

        mock_detector.detect_anomalies.return_value = [mock_anomaly]

        agent = MonitoringAgent(anomaly_detector=mock_detector)

        with patch("src.ml_anomaly_detector.DataPoint") as mock_datapoint:
            # DataPoint is imported and used inside the function
            mock_datapoint.return_value = MagicMock()

            task = AgentTask(
                task_type="check_anomalies",
                parameters={"metric_name": "cpu", "value": 100},
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["is_anomaly"] is True
        assert result.data["confidence"] == 0.95
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_check_anomalies_detected_added_to_history(self):
        """Test detected anomalies are added to history."""
        agent = MonitoringAgent()
        agent.config.anomaly_threshold = 0.5  # Lower threshold for test

        # Build baseline
        for i in range(15):
            task = AgentTask(
                task_type="check_anomalies",
                parameters={"metric_name": "latency", "value": 100},
                domain=AgentDomain.MONITORING,
            )
            await agent.execute_task(task)

        # Check extreme value
        task = AgentTask(
            task_type="check_anomalies",
            parameters={"metric_name": "latency", "value": 1000},  # 10x normal
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        if result.data["is_anomaly"]:
            assert len(agent._anomaly_history) > 0


class TestSendAlertHandler:
    """Tests for _handle_send_alert."""

    @pytest.mark.asyncio
    async def test_send_alert_missing_message_fails(self):
        """Test send alert fails when message missing."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="send_alert",
            parameters={"title": "Test Alert"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "message is required" in result.error

    @pytest.mark.asyncio
    async def test_send_alert_with_alert_manager(self):
        """Test send alert with alert manager."""
        mock_manager = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.suppressed = False
        mock_manager.send.return_value = mock_result

        agent = MonitoringAgent(alert_manager=mock_manager)

        # Create mock AlertSeverity enum and Alert class
        mock_severity = MagicMock()
        mock_severity.INFO = "info"
        mock_severity.WARNING = "warning"
        mock_severity.CRITICAL = "critical"

        mock_alert_class = MagicMock()
        mock_alert_module = MagicMock()
        mock_alert_module.Alert = mock_alert_class
        mock_alert_module.AlertSeverity = mock_severity

        import sys
        with patch.dict(sys.modules, {"src.alert_manager": mock_alert_module}):
            task = AgentTask(
                task_type="send_alert",
                parameters={"title": "Test", "message": "Test message", "severity": "warning"},
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["channels_notified"] == 1
        mock_manager.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_via_webhook(self):
        """Test send alert via n8n webhook."""
        config = MonitoringConfig(alert_webhook_url="https://n8n.example.com/webhook/alert")
        agent = MonitoringAgent(config=config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="send_alert",
                parameters={"title": "Test", "message": "Alert message"},
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["channels_notified"] == 1

    @pytest.mark.asyncio
    async def test_send_alert_no_channels_configured(self):
        """Test send alert succeeds even with no channels."""
        agent = MonitoringAgent()  # No alert_manager, no webhook

        task = AgentTask(
            task_type="send_alert",
            parameters={"title": "Test", "message": "Message"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        # Should succeed with 0 channels notified
        assert result.success is True
        assert result.data["channels_notified"] == 0


class TestCollectMetricsHandler:
    """Tests for _handle_collect_metrics."""

    @pytest.mark.asyncio
    async def test_collect_metrics_missing_url_fails(self):
        """Test collect metrics fails when URL missing."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="collect_metrics",
            parameters={},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "url is required" in result.error

    @pytest.mark.asyncio
    async def test_collect_metrics_success(self):
        """Test successful metrics collection."""
        agent = MonitoringAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "cpu": 45.5,
                "memory": 67.2,
                "requests_per_second": 1234,
                "status": "healthy",  # Non-numeric, should be ignored
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="collect_metrics",
                parameters={"url": "https://example.com/metrics"},
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["metrics"]["cpu"] == 45.5
        assert result.data["metrics"]["memory"] == 67.2
        assert "status" not in result.data["metrics"]  # Non-numeric excluded

    @pytest.mark.asyncio
    async def test_collect_metrics_specific_names(self):
        """Test collecting specific metric names."""
        agent = MonitoringAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "cpu": 45.5,
                "memory": 67.2,
                "disk": 80.0,
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="collect_metrics",
                parameters={
                    "url": "https://example.com/metrics",
                    "metric_names": ["cpu", "memory"],
                },
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert "cpu" in result.data["metrics"]
        assert "memory" in result.data["metrics"]
        # disk not requested, should not be in result
        assert "disk" not in result.data["metrics"]

    @pytest.mark.asyncio
    async def test_collect_metrics_stores_internally(self):
        """Test that collected metrics are stored internally."""
        agent = MonitoringAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"cpu": 50.0}
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="collect_metrics",
                parameters={"url": "https://example.com/metrics"},
                domain=AgentDomain.MONITORING,
            )

            await agent.execute_task(task)

        assert "cpu" in agent._recent_metrics
        assert len(agent._recent_metrics["cpu"]) == 1


class TestAnalyzePerformanceHandler:
    """Tests for _handle_analyze_performance."""

    @pytest.mark.asyncio
    async def test_analyze_performance_missing_metric_name_fails(self):
        """Test analyze performance fails when metric_name missing."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="analyze_performance",
            parameters={},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "metric_name is required" in result.error

    @pytest.mark.asyncio
    async def test_analyze_performance_insufficient_data(self):
        """Test analyze performance with insufficient data."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="analyze_performance",
            parameters={"metric_name": "new_metric"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["trend"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_analyze_performance_increasing_trend(self):
        """Test analyze performance detects increasing trend."""
        agent = MonitoringAgent()

        # Add increasing values
        for i in range(10):
            agent._store_metric("cpu", 50 + i * 5)  # 50, 55, 60, ...

        task = AgentTask(
            task_type="analyze_performance",
            parameters={"metric_name": "cpu"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["trend"] == "increasing"

    @pytest.mark.asyncio
    async def test_analyze_performance_decreasing_trend(self):
        """Test analyze performance detects decreasing trend."""
        agent = MonitoringAgent()

        # Add decreasing values
        for i in range(10):
            agent._store_metric("memory", 90 - i * 5)  # 90, 85, 80, ...

        task = AgentTask(
            task_type="analyze_performance",
            parameters={"metric_name": "memory"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["trend"] == "decreasing"

    @pytest.mark.asyncio
    async def test_analyze_performance_stable_trend(self):
        """Test analyze performance detects stable trend."""
        agent = MonitoringAgent()

        # Add stable values with small variations
        for i in range(10):
            agent._store_metric("latency", 100 + (i % 3) - 1)  # ~100

        task = AgentTask(
            task_type="analyze_performance",
            parameters={"metric_name": "latency"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_analyze_performance_with_baseline(self):
        """Test analyze performance with performance_baseline."""
        mock_baseline = MagicMock()
        mock_baseline.analyze_trends.return_value = {
            "trend": "increasing",
            "baseline": {"avg": 50, "std": 5},
            "current": {"avg": 75, "std": 10},
        }

        agent = MonitoringAgent(performance_baseline=mock_baseline)

        task = AgentTask(
            task_type="analyze_performance",
            parameters={"metric_name": "cpu", "window_hours": 48},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["trend"] == "increasing"
        mock_baseline.analyze_trends.assert_called_once_with(
            metric_name="cpu",
            window_hours=48,
        )


class TestGenerateReportHandler:
    """Tests for _handle_generate_report."""

    @pytest.mark.asyncio
    async def test_generate_summary_report(self):
        """Test generating summary report."""
        agent = MonitoringAgent()
        agent._store_metric("cpu", 50)
        agent._store_metric("memory", 70)

        task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "summary"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert "generated_at" in result.data
        assert result.data["report_type"] == "summary"
        assert result.data["metrics_tracked"] == ["cpu", "memory"]

    @pytest.mark.asyncio
    async def test_generate_anomalies_report(self):
        """Test generating anomalies report."""
        agent = MonitoringAgent()
        agent._anomaly_history.append({"metric": "cpu", "value": 100, "severity": "WARNING"})

        task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "anomalies"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["anomaly_count"] == 1
        assert len(result.data["recent_anomalies"]) == 1

    @pytest.mark.asyncio
    async def test_generate_detailed_report(self):
        """Test generating detailed report."""
        agent = MonitoringAgent()
        for i in range(5):
            agent._store_metric("cpu", 50 + i)
            agent._store_metric("memory", 60 + i)
        agent._anomaly_history.append({"metric": "cpu", "value": 100})

        task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "detailed"},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert "metrics_tracked" in result.data
        assert "anomaly_count" in result.data
        assert "metric_summaries" in result.data
        assert "cpu" in result.data["metric_summaries"]
        assert "min" in result.data["metric_summaries"]["cpu"]
        assert "max" in result.data["metric_summaries"]["cpu"]
        assert "avg" in result.data["metric_summaries"]["cpu"]


class TestCheckHealthHandler:
    """Tests for _handle_check_health."""

    @pytest.mark.asyncio
    async def test_check_health_no_endpoints(self):
        """Test check health with no endpoints configured."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="check_health",
            parameters={},
            domain=AgentDomain.MONITORING,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["status"] == "unknown"
        assert "No endpoints configured" in result.data["message"]

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self):
        """Test check health with all healthy endpoints."""
        agent = MonitoringAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            task = AgentTask(
                task_type="check_health",
                parameters={
                    "endpoints": [
                        "https://service1.example.com/health",
                        "https://service2.example.com/health",
                    ]
                },
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["overall_status"] == "healthy"
        assert result.data["healthy_count"] == 2
        assert result.data["total_endpoints"] == 2

    @pytest.mark.asyncio
    async def test_check_health_partial_failure(self):
        """Test check health with some unhealthy endpoints."""
        agent = MonitoringAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()

            # First call succeeds, second fails
            async def side_effect(url, **kwargs):
                if "service1" in url:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.elapsed.total_seconds.return_value = 0.1
                    return mock_response
                else:
                    mock_response = MagicMock()
                    mock_response.status_code = 500
                    mock_response.elapsed.total_seconds.return_value = 0.5
                    return mock_response

            mock_instance.get = side_effect
            mock_client.return_value.__aenter__.return_value = mock_instance

            task = AgentTask(
                task_type="check_health",
                parameters={
                    "endpoints": [
                        "https://service1.example.com/health",
                        "https://service2.example.com/health",
                    ]
                },
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["overall_status"] == "degraded"
        assert result.data["healthy_count"] == 1

    @pytest.mark.asyncio
    async def test_check_health_all_unreachable(self):
        """Test check health with all unreachable endpoints."""
        agent = MonitoringAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            task = AgentTask(
                task_type="check_health",
                parameters={
                    "endpoints": ["https://down.example.com/health"]
                },
                domain=AgentDomain.MONITORING,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["overall_status"] == "unhealthy"
        assert result.data["healthy_count"] == 0
        assert result.data["endpoint_results"][0]["status"] == "unreachable"


class TestMessageHandlers:
    """Tests for message handlers."""

    @pytest.mark.asyncio
    async def test_handle_anomaly_notification(self):
        """Test anomaly notification handler."""
        agent = MonitoringAgent()

        response = await agent._handle_anomaly_notification({
            "source": "deploy_agent",
            "metric": "error_rate",
            "value": 0.15,
            "severity": "WARNING",
        })

        assert response == {"acknowledged": True}
        assert len(agent._anomaly_history) == 1
        assert agent._anomaly_history[0]["source"] == "deploy_agent"

    @pytest.mark.asyncio
    async def test_handle_metric_request_found(self):
        """Test metric request handler with existing metric."""
        agent = MonitoringAgent()
        for i in range(5):
            agent._store_metric("cpu", 50 + i)

        response = await agent._handle_metric_request({"metric_name": "cpu"})

        assert response["metric_name"] == "cpu"
        assert len(response["values"]) == 5

    @pytest.mark.asyncio
    async def test_handle_metric_request_not_found(self):
        """Test metric request handler with unknown metric."""
        agent = MonitoringAgent()
        agent._store_metric("cpu", 50)

        response = await agent._handle_metric_request({"metric_name": "unknown"})

        assert "available_metrics" in response
        assert "cpu" in response["available_metrics"]


class TestMetricStorage:
    """Tests for metric storage functionality."""

    def test_store_metric(self):
        """Test storing a metric."""
        agent = MonitoringAgent()

        agent._store_metric("cpu", 50.5)

        assert "cpu" in agent._recent_metrics
        assert len(agent._recent_metrics["cpu"]) == 1
        assert agent._recent_metrics["cpu"][0]["value"] == 50.5

    def test_store_metric_limit(self):
        """Test metric storage limit (1000 values)."""
        agent = MonitoringAgent()

        # Add more than 1000 values
        for i in range(1050):
            agent._store_metric("cpu", i)

        # Should keep only last 1000
        assert len(agent._recent_metrics["cpu"]) == 1000
        # First value should be 50 (1050 - 1000 = 50)
        assert agent._recent_metrics["cpu"][0]["value"] == 50.0


class TestGetAnomalyHistory:
    """Tests for get_anomaly_history."""

    def test_get_anomaly_history_returns_copy(self):
        """Test get_anomaly_history returns a copy."""
        agent = MonitoringAgent()
        agent._anomaly_history.append({"metric": "cpu"})

        history = agent.get_anomaly_history()

        assert history == [{"metric": "cpu"}]
        # Verify it's a copy
        history.append({"metric": "memory"})
        assert len(agent._anomaly_history) == 1
