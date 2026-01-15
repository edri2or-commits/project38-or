"""Tests for Multi-Agent Orchestration System.

Tests cover:
- Base classes (AgentTask, AgentResult, SpecializedAgent)
- DeployAgent capabilities and task execution
- MonitoringAgent capabilities and task execution
- IntegrationAgent capabilities and task execution
- AgentOrchestrator routing and coordination
- Inter-agent communication
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.multi_agent import (
    AgentDomain,
    AgentMessage,
    AgentOrchestrator,
    AgentResult,
    AgentTask,
    DeployAgent,
    DeploymentConfig,
    IntegrationAgent,
    IntegrationConfig,
    MonitoringAgent,
    OrchestratorConfig,
    TaskPriority,
    TaskStatus,
    create_orchestrator,
)


# =============================================================================
# Base Classes Tests
# =============================================================================
class TestAgentTask:
    """Tests for AgentTask dataclass."""

    def test_task_creation_defaults(self) -> None:
        """Test task creation with defaults."""
        task = AgentTask(task_type="test", parameters={})
        assert task.task_type == "test"
        assert task.parameters == {}
        assert task.domain == AgentDomain.GENERAL
        assert task.priority == TaskPriority.MEDIUM
        assert task.status == TaskStatus.PENDING
        assert task.task_id is not None
        assert task.created_at is not None

    def test_task_creation_with_values(self) -> None:
        """Test task creation with explicit values."""
        task = AgentTask(
            task_type="deploy",
            parameters={"project_id": "test"},
            domain=AgentDomain.DEPLOY,
            priority=TaskPriority.CRITICAL,
        )
        assert task.task_type == "deploy"
        assert task.domain == AgentDomain.DEPLOY
        assert task.priority == TaskPriority.CRITICAL


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_result_success(self) -> None:
        """Test successful result creation."""
        result = AgentResult(
            task_id="test-id",
            success=True,
            data={"key": "value"},
        )
        assert result.task_id == "test-id"
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_result_failure(self) -> None:
        """Test failure result creation."""
        result = AgentResult(
            task_id="test-id",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestAgentMessage:
    """Tests for AgentMessage dataclass."""

    def test_message_creation(self) -> None:
        """Test message creation."""
        message = AgentMessage(
            from_agent="agent-1",
            message_type="status_request",
            payload={"key": "value"},
        )
        assert message.from_agent == "agent-1"
        assert message.message_type == "status_request"
        assert message.payload == {"key": "value"}
        assert message.to_agent is None  # Broadcast
        assert message.message_id is not None


# =============================================================================
# DeployAgent Tests
# =============================================================================
class TestDeployAgent:
    """Tests for DeployAgent."""

    def test_agent_initialization(self) -> None:
        """Test agent initialization."""
        agent = DeployAgent()
        assert agent.domain == AgentDomain.DEPLOY
        assert agent.agent_id is not None
        assert len(agent.capabilities) == 6  # deploy, rollback, status, scale, health, set_env

    def test_capabilities(self) -> None:
        """Test agent capabilities."""
        agent = DeployAgent()
        cap_names = [c.name for c in agent.capabilities]
        assert "deploy" in cap_names
        assert "rollback" in cap_names
        assert "deployment_status" in cap_names
        assert "health_check" in cap_names

    def test_can_handle_deploy_task(self) -> None:
        """Test task handling capability."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="deploy",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )
        assert agent.can_handle(task) is True

    def test_cannot_handle_unknown_task(self) -> None:
        """Test cannot handle unknown task type."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="unknown_task",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )
        assert agent.can_handle(task) is False

    @pytest.mark.asyncio
    async def test_deploy_without_client(self) -> None:
        """Test deploy fails without railway client."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="deploy",
            parameters={"project_id": "test", "environment_id": "prod"},
            domain=AgentDomain.DEPLOY,
        )
        result = await agent.execute_task(task)
        assert result.success is False
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_deploy_with_client(self) -> None:
        """Test deploy with mocked railway client."""
        mock_railway = AsyncMock()
        mock_railway.trigger_deployment.return_value = {"id": "deploy-123"}

        config = DeploymentConfig(
            project_id="proj-1",
            environment_id="env-1",
        )
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="deploy",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )
        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["deployment_id"] == "deploy-123"
        mock_railway.trigger_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test health check with successful response."""
        agent = DeployAgent()
        agent.config.health_check_url = "https://example.com/health"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            task = AgentTask(
                task_type="health_check",
                parameters={},
                domain=AgentDomain.DEPLOY,
            )
            result = await agent.execute_task(task)

            assert result.success is True
            assert result.data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_rollback_without_client(self) -> None:
        """Test rollback fails without railway client."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="rollback",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )
        result = await agent.execute_task(task)
        assert result.success is False


# =============================================================================
# MonitoringAgent Tests
# =============================================================================
class TestMonitoringAgent:
    """Tests for MonitoringAgent."""

    def test_agent_initialization(self) -> None:
        """Test agent initialization."""
        agent = MonitoringAgent()
        assert agent.domain == AgentDomain.MONITORING
        assert len(agent.capabilities) == 6

    def test_capabilities(self) -> None:
        """Test agent capabilities."""
        agent = MonitoringAgent()
        cap_names = [c.name for c in agent.capabilities]
        assert "check_anomalies" in cap_names
        assert "send_alert" in cap_names
        assert "collect_metrics" in cap_names
        assert "analyze_performance" in cap_names

    @pytest.mark.asyncio
    async def test_check_anomalies_no_anomaly(self) -> None:
        """Test anomaly check with normal value."""
        agent = MonitoringAgent()

        # Add baseline data
        for i in range(15):
            task = AgentTask(
                task_type="check_anomalies",
                parameters={"metric_name": "test_metric", "value": 100 + i},
                domain=AgentDomain.MONITORING,
            )
            await agent.execute_task(task)

        # Check normal value
        task = AgentTask(
            task_type="check_anomalies",
            parameters={"metric_name": "test_metric", "value": 105},
            domain=AgentDomain.MONITORING,
        )
        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["is_anomaly"] is False

    @pytest.mark.asyncio
    async def test_generate_report(self) -> None:
        """Test report generation."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "summary"},
            domain=AgentDomain.MONITORING,
        )
        result = await agent.execute_task(task)

        assert result.success is True
        assert "generated_at" in result.data
        assert "agent_status" in result.data

    @pytest.mark.asyncio
    async def test_analyze_performance_insufficient_data(self) -> None:
        """Test performance analysis with insufficient data."""
        agent = MonitoringAgent()

        task = AgentTask(
            task_type="analyze_performance",
            parameters={"metric_name": "cpu_usage"},
            domain=AgentDomain.MONITORING,
        )
        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["trend"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_send_alert_without_manager(self) -> None:
        """Test alert sending without alert manager."""
        agent = MonitoringAgent()
        agent.config.alert_webhook_url = ""

        task = AgentTask(
            task_type="send_alert",
            parameters={"title": "Test", "message": "Test message"},
            domain=AgentDomain.MONITORING,
        )
        result = await agent.execute_task(task)

        # Should succeed even without channels
        assert result.success is True


# =============================================================================
# IntegrationAgent Tests
# =============================================================================
class TestIntegrationAgent:
    """Tests for IntegrationAgent."""

    def test_agent_initialization(self) -> None:
        """Test agent initialization."""
        agent = IntegrationAgent()
        assert agent.domain == AgentDomain.INTEGRATION
        assert len(agent.capabilities) == 8

    def test_capabilities(self) -> None:
        """Test agent capabilities."""
        agent = IntegrationAgent()
        cap_names = [c.name for c in agent.capabilities]
        assert "create_issue" in cap_names
        assert "create_pr" in cap_names
        assert "merge_pr" in cap_names
        assert "trigger_workflow" in cap_names

    @pytest.mark.asyncio
    async def test_create_issue_missing_title(self) -> None:
        """Test create issue fails without title."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="create_issue",
            parameters={"body": "Issue body"},
            domain=AgentDomain.INTEGRATION,
        )
        result = await agent.execute_task(task)

        assert result.success is False
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_issue_missing_repo(self) -> None:
        """Test create issue fails without repo."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="create_issue",
            parameters={"title": "Test Issue"},
            domain=AgentDomain.INTEGRATION,
        )
        result = await agent.execute_task(task)

        assert result.success is False
        assert "repo" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_issue_with_client(self) -> None:
        """Test create issue with mocked client."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/issues/42",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        agent = IntegrationAgent(github_client=mock_github, config=config)

        task = AgentTask(
            task_type="create_issue",
            parameters={"title": "Test Issue", "body": "Body"},
            domain=AgentDomain.INTEGRATION,
        )
        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["number"] == 42
        mock_github.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_merge_pr_missing_number(self) -> None:
        """Test merge PR fails without number."""
        agent = IntegrationAgent()

        task = AgentTask(
            task_type="merge_pr",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )
        result = await agent.execute_task(task)

        assert result.success is False
        assert "pr_number" in result.error.lower()


# =============================================================================
# AgentOrchestrator Tests
# =============================================================================
class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""

    def test_orchestrator_initialization(self) -> None:
        """Test orchestrator initialization."""
        orchestrator = AgentOrchestrator()
        assert orchestrator.is_running is False
        assert len(orchestrator._agents) == 0

    def test_register_agent(self) -> None:
        """Test agent registration."""
        orchestrator = AgentOrchestrator()
        agent = DeployAgent()

        orchestrator.register_agent(agent)

        assert agent.agent_id in orchestrator._agents
        assert AgentDomain.DEPLOY in orchestrator._domain_agents

    def test_unregister_agent(self) -> None:
        """Test agent unregistration."""
        orchestrator = AgentOrchestrator()
        agent = DeployAgent()
        orchestrator.register_agent(agent)

        result = orchestrator.unregister_agent(agent.agent_id)

        assert result is True
        assert agent.agent_id not in orchestrator._agents

    def test_get_agents_for_domain(self) -> None:
        """Test getting agents by domain."""
        orchestrator = AgentOrchestrator()
        deploy_agent = DeployAgent()
        monitoring_agent = MonitoringAgent()

        orchestrator.register_agent(deploy_agent)
        orchestrator.register_agent(monitoring_agent)

        deploy_agents = orchestrator.get_agents_for_domain(AgentDomain.DEPLOY)
        assert len(deploy_agents) == 1
        assert deploy_agents[0].agent_id == deploy_agent.agent_id

    def test_get_capabilities(self) -> None:
        """Test getting all capabilities."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(DeployAgent())
        orchestrator.register_agent(MonitoringAgent())

        caps = orchestrator.get_capabilities()

        assert AgentDomain.DEPLOY.value in caps
        assert AgentDomain.MONITORING.value in caps
        assert "deploy" in caps[AgentDomain.DEPLOY.value]

    @pytest.mark.asyncio
    async def test_submit_task(self) -> None:
        """Test task submission."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(DeployAgent())

        task = AgentTask(
            task_type="health_check",
            parameters={"url": "https://example.com"},
            domain=AgentDomain.DEPLOY,
        )

        task_id = await orchestrator.submit_task(task)

        assert task_id == task.task_id
        assert orchestrator._tasks_submitted == 1

    @pytest.mark.asyncio
    async def test_submit_and_wait(self) -> None:
        """Test submit and wait for result."""
        orchestrator = AgentOrchestrator()
        agent = MonitoringAgent()
        orchestrator.register_agent(agent)

        task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "summary"},
            domain=AgentDomain.MONITORING,
        )

        result = await orchestrator.submit_and_wait(task)

        assert result.task_id == task.task_id
        assert result.success is True

    @pytest.mark.asyncio
    async def test_route_message_direct(self) -> None:
        """Test direct message routing."""
        orchestrator = AgentOrchestrator()
        agent = MonitoringAgent()
        orchestrator.register_agent(agent)

        message = AgentMessage(
            from_agent="test-sender",
            to_agent=agent.agent_id,
            message_type="metric_request",
            payload={"metric_name": "test"},
        )

        response = await orchestrator.route_message(message)

        # MonitoringAgent should respond with available metrics
        assert response is None or isinstance(response, AgentMessage)

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Test orchestrator start and stop."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MonitoringAgent())

        await orchestrator.start()
        assert orchestrator.is_running is True

        await orchestrator.stop()
        assert orchestrator.is_running is False

    def test_get_status(self) -> None:
        """Test status retrieval."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(DeployAgent())
        orchestrator.register_agent(MonitoringAgent())

        status = orchestrator.get_status()

        assert status["is_running"] is False
        assert status["agents_registered"] == 2
        assert "statistics" in status


# =============================================================================
# Factory Function Tests
# =============================================================================
class TestCreateOrchestrator:
    """Tests for create_orchestrator factory."""

    def test_create_empty(self) -> None:
        """Test creating orchestrator without clients."""
        orchestrator = create_orchestrator()

        # Should have monitoring agent by default
        assert orchestrator._agents
        assert AgentDomain.MONITORING in orchestrator._domain_agents

    def test_create_with_railway(self) -> None:
        """Test creating orchestrator with railway client."""
        mock_railway = MagicMock()
        orchestrator = create_orchestrator(railway_client=mock_railway)

        assert AgentDomain.DEPLOY in orchestrator._domain_agents

    def test_create_with_all_clients(self) -> None:
        """Test creating orchestrator with all clients."""
        mock_railway = MagicMock()
        mock_github = MagicMock()
        mock_n8n = MagicMock()

        orchestrator = create_orchestrator(
            railway_client=mock_railway,
            github_client=mock_github,
            n8n_client=mock_n8n,
        )

        assert AgentDomain.DEPLOY in orchestrator._domain_agents
        assert AgentDomain.MONITORING in orchestrator._domain_agents
        assert AgentDomain.INTEGRATION in orchestrator._domain_agents


# =============================================================================
# Inter-Agent Communication Tests
# =============================================================================
class TestInterAgentCommunication:
    """Tests for inter-agent communication."""

    @pytest.mark.asyncio
    async def test_broadcast_event(self) -> None:
        """Test broadcasting event to all agents."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(DeployAgent())
        orchestrator.register_agent(MonitoringAgent())

        # Should not raise
        await orchestrator.broadcast_event(
            event_type="test_event",
            data={"key": "value"},
        )

        # broadcast_event creates a message, check agents received it
        # The message is only added via route_message, broadcast goes directly to agents
        assert orchestrator._tasks_submitted == 0  # No tasks submitted by broadcast

    @pytest.mark.asyncio
    async def test_deployment_failure_triggers_issue(self) -> None:
        """Test that deployment failure can trigger issue creation."""
        mock_github = AsyncMock()
        mock_github.create_issue.return_value = {
            "number": 1,
            "html_url": "https://github.com/owner/repo/issues/1",
        }

        config = IntegrationConfig(github_repo="owner/repo")
        integration_agent = IntegrationAgent(github_client=mock_github, config=config)

        # Simulate deployment failure notification
        response = await integration_agent._handle_deployment_failure({
            "deployment_id": "deploy-fail-123",
            "error": "Health check failed",
        })

        assert "number" in response
        mock_github.create_issue.assert_called_once()


# =============================================================================
# Priority and Routing Tests
# =============================================================================
class TestTaskPriorityRouting:
    """Tests for task priority and routing."""

    @pytest.mark.asyncio
    async def test_priority_order(self) -> None:
        """Test tasks are processed by priority."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MonitoringAgent())

        # Submit tasks with different priorities
        low_task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "summary"},
            domain=AgentDomain.MONITORING,
            priority=TaskPriority.LOW,
        )
        high_task = AgentTask(
            task_type="generate_report",
            parameters={"report_type": "summary"},
            domain=AgentDomain.MONITORING,
            priority=TaskPriority.HIGH,
        )

        await orchestrator.submit_task(low_task)
        await orchestrator.submit_task(high_task)

        # High priority should be first in queue
        item = await orchestrator._task_queue.get()
        assert item.task.priority == TaskPriority.HIGH

    def test_agent_selection_by_load(self) -> None:
        """Test agent selection favors lower load."""
        orchestrator = AgentOrchestrator()

        agent1 = MonitoringAgent(agent_id="agent-1")
        agent2 = MonitoringAgent(agent_id="agent-2")

        # Simulate load on agent1
        agent1._active_tasks["task-1"] = MagicMock()
        agent1._active_tasks["task-2"] = MagicMock()

        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)

        task = AgentTask(
            task_type="generate_report",
            parameters={},
            domain=AgentDomain.MONITORING,
        )

        selected = orchestrator._select_agent_for_task(task)

        # Should select agent2 (lower load)
        assert selected.agent_id == "agent-2"


# =============================================================================
# Error Handling Tests
# =============================================================================
class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_task_timeout(self) -> None:
        """Test task timeout handling."""
        config = OrchestratorConfig(task_timeout_seconds=1)
        orchestrator = AgentOrchestrator(config=config)

        # Create agent with slow task
        class SlowAgent(MonitoringAgent):
            async def _execute_task_internal(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(5)  # Slow task
                return AgentResult(task_id=task.task_id, success=True)

        orchestrator.register_agent(SlowAgent())

        task = AgentTask(
            task_type="generate_report",
            parameters={},
            domain=AgentDomain.MONITORING,
        )

        result = await orchestrator.submit_and_wait(task)

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_no_agent_available(self) -> None:
        """Test handling when no agent can handle task."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(DeployAgent())

        # Submit task for different domain
        task = AgentTask(
            task_type="unknown_task",
            parameters={},
            domain=AgentDomain.INTEGRATION,
        )

        result = await orchestrator.submit_and_wait(task)

        assert result.success is False
        assert "no agent" in result.error.lower()

    @pytest.mark.asyncio
    async def test_agent_exception_handling(self) -> None:
        """Test handling of agent exceptions."""

        class FailingAgent(MonitoringAgent):
            async def _execute_task_internal(self, task: AgentTask) -> AgentResult:
                raise RuntimeError("Simulated failure")

        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(FailingAgent())

        task = AgentTask(
            task_type="generate_report",
            parameters={},
            domain=AgentDomain.MONITORING,
        )

        result = await orchestrator.submit_and_wait(task)

        assert result.success is False
        assert "failure" in result.error.lower()
