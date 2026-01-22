"""Comprehensive tests for DeployAgent.

Tests cover all task handlers and edge cases:
- deploy: Trigger deployment
- rollback: Rollback to previous deployment
- deployment_status: Get deployment status
- scale: Scale service resources
- health_check: Check deployment health
- set_env: Set environment variable
- Message handlers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.multi_agent.base import AgentDomain, AgentResult, AgentTask, TaskPriority
from src.multi_agent.deploy_agent import DeployAgent, DeploymentConfig


class TestDeployAgentInitialization:
    """Tests for DeployAgent initialization."""

    def test_default_initialization(self):
        """Test agent initializes with defaults."""
        agent = DeployAgent()

        assert agent.domain == AgentDomain.DEPLOY
        assert agent.railway is None
        assert agent.config.project_id == ""
        assert agent.config.environment_id == ""
        assert agent._active_deployments == {}

    def test_initialization_with_config(self):
        """Test agent initializes with custom config."""
        config = DeploymentConfig(
            project_id="proj-123",
            environment_id="env-456",
            max_wait_seconds=600,
            health_check_url="https://example.com/health",
            rollback_on_failure=False,
        )
        agent = DeployAgent(config=config)

        assert agent.config.project_id == "proj-123"
        assert agent.config.environment_id == "env-456"
        assert agent.config.max_wait_seconds == 600
        assert agent.config.rollback_on_failure is False

    def test_initialization_with_client(self):
        """Test agent initializes with railway client."""
        mock_railway = MagicMock()
        agent = DeployAgent(railway_client=mock_railway)

        assert agent.railway is mock_railway

    def test_custom_agent_id(self):
        """Test agent uses custom agent_id."""
        agent = DeployAgent(agent_id="custom-deploy-agent")

        assert agent.agent_id == "custom-deploy-agent"

    def test_message_handlers_registered(self):
        """Test message handlers are registered on init."""
        agent = DeployAgent()

        assert "deployment_status_request" in agent._message_handlers
        assert "health_check_request" in agent._message_handlers


class TestDeployAgentCapabilities:
    """Tests for DeployAgent capabilities."""

    def test_has_six_capabilities(self):
        """Test agent has exactly 6 capabilities."""
        agent = DeployAgent()
        assert len(agent.capabilities) == 6

    def test_deploy_capability(self):
        """Test deploy capability properties."""
        agent = DeployAgent()
        cap = agent.get_capability("deploy")

        assert cap is not None
        assert cap.name == "deploy"
        assert cap.domain == AgentDomain.DEPLOY
        assert cap.requires_approval is False
        assert cap.max_concurrent == 2
        assert cap.cooldown_seconds == 30

    def test_rollback_capability(self):
        """Test rollback capability properties."""
        agent = DeployAgent()
        cap = agent.get_capability("rollback")

        assert cap is not None
        assert cap.requires_approval is False
        assert cap.max_concurrent == 1
        assert cap.cooldown_seconds == 60

    def test_scale_requires_approval(self):
        """Test scale capability requires approval."""
        agent = DeployAgent()
        cap = agent.get_capability("scale")

        assert cap is not None
        assert cap.requires_approval is True

    def test_set_env_requires_approval(self):
        """Test set_env capability requires approval."""
        agent = DeployAgent()
        cap = agent.get_capability("set_env")

        assert cap is not None
        assert cap.requires_approval is True


class TestDeployHandler:
    """Tests for _handle_deploy."""

    @pytest.mark.asyncio
    async def test_deploy_without_client_fails(self):
        """Test deploy fails when railway client not configured."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="deploy",
            parameters={"project_id": "test", "environment_id": "prod"},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "RailwayClient not configured" in result.error

    @pytest.mark.asyncio
    async def test_deploy_missing_project_id_fails(self):
        """Test deploy fails when project_id missing."""
        mock_railway = AsyncMock()
        agent = DeployAgent(railway_client=mock_railway)

        task = AgentTask(
            task_type="deploy",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "project_id and environment_id are required" in result.error

    @pytest.mark.asyncio
    async def test_deploy_success(self):
        """Test successful deployment."""
        mock_railway = AsyncMock()
        mock_railway.trigger_deployment.return_value = {"id": "deploy-abc123"}

        config = DeploymentConfig(project_id="proj-1", environment_id="env-1")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="deploy",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["deployment_id"] == "deploy-abc123"
        assert result.data["status"] == "BUILDING"
        assert "deploy-abc123" in agent._active_deployments

    @pytest.mark.asyncio
    async def test_deploy_uses_task_parameters_over_config(self):
        """Test task parameters override config."""
        mock_railway = AsyncMock()
        mock_railway.trigger_deployment.return_value = {"id": "deploy-xyz"}

        config = DeploymentConfig(project_id="default-proj", environment_id="default-env")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="deploy",
            parameters={"project_id": "custom-proj", "environment_id": "custom-env"},
            domain=AgentDomain.DEPLOY,
        )

        await agent.execute_task(task)

        mock_railway.trigger_deployment.assert_called_once_with(
            project_id="custom-proj",
            environment_id="custom-env",
        )

    @pytest.mark.asyncio
    async def test_deploy_exception_returns_recommendations(self):
        """Test deploy exception includes recommendations."""
        mock_railway = AsyncMock()
        mock_railway.trigger_deployment.side_effect = Exception("API error")

        config = DeploymentConfig(project_id="proj-1", environment_id="env-1")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="deploy",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "API error" in result.error
        assert len(result.recommendations) > 0


class TestRollbackHandler:
    """Tests for _handle_rollback."""

    @pytest.mark.asyncio
    async def test_rollback_without_client_fails(self):
        """Test rollback fails when railway client not configured."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="rollback",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "RailwayClient not configured" in result.error

    @pytest.mark.asyncio
    async def test_rollback_no_previous_deployment(self):
        """Test rollback fails when no previous successful deployment."""
        mock_railway = AsyncMock()
        mock_railway.get_last_active_deployment.return_value = None

        config = DeploymentConfig(project_id="proj-1", environment_id="env-1")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="rollback",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "No previous successful deployment" in result.error

    @pytest.mark.asyncio
    async def test_rollback_success(self):
        """Test successful rollback."""
        mock_railway = AsyncMock()
        mock_railway.get_last_active_deployment.return_value = {"id": "deploy-old"}
        mock_railway.rollback_deployment.return_value = {"id": "deploy-new"}

        config = DeploymentConfig(project_id="proj-1", environment_id="env-1")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="rollback",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["rollback_id"] == "deploy-new"
        assert result.data["rolled_back_to"] == "deploy-old"
        assert result.data["status"] == "ROLLING_BACK"

    @pytest.mark.asyncio
    async def test_rollback_includes_recommendations(self):
        """Test successful rollback includes recommendations."""
        mock_railway = AsyncMock()
        mock_railway.get_last_active_deployment.return_value = {"id": "deploy-old"}
        mock_railway.rollback_deployment.return_value = {"id": "deploy-new"}

        config = DeploymentConfig(project_id="proj-1", environment_id="env-1")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="rollback",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert len(result.recommendations) > 0
        assert any("Monitor" in r for r in result.recommendations)


class TestDeploymentStatusHandler:
    """Tests for _handle_deployment_status."""

    @pytest.mark.asyncio
    async def test_status_without_client_fails(self):
        """Test status fails when railway client not configured."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="deployment_status",
            parameters={"deployment_id": "deploy-123"},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "RailwayClient not configured" in result.error

    @pytest.mark.asyncio
    async def test_status_missing_deployment_id_fails(self):
        """Test status fails when deployment_id missing."""
        mock_railway = AsyncMock()
        agent = DeployAgent(railway_client=mock_railway)

        task = AgentTask(
            task_type="deployment_status",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "deployment_id is required" in result.error

    @pytest.mark.asyncio
    async def test_status_success(self):
        """Test successful status retrieval."""
        mock_railway = AsyncMock()
        mock_railway.get_deployment_status.return_value = {
            "status": "SUCCESS",
            "createdAt": "2026-01-22T10:00:00Z",
            "meta": {"build_time": 120},
        }

        agent = DeployAgent(railway_client=mock_railway)

        task = AgentTask(
            task_type="deployment_status",
            parameters={"deployment_id": "deploy-123"},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["deployment_id"] == "deploy-123"
        assert result.data["status"] == "SUCCESS"
        assert result.data["created_at"] == "2026-01-22T10:00:00Z"


class TestScaleHandler:
    """Tests for _handle_scale."""

    @pytest.mark.asyncio
    async def test_scale_not_implemented(self):
        """Test scale returns not implemented error."""
        agent = DeployAgent()

        task = AgentTask(
            task_type="scale",
            parameters={"service_id": "svc-123", "replicas": 3},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "not yet implemented" in result.error.lower()
        assert len(result.recommendations) > 0


class TestHealthCheckHandler:
    """Tests for _handle_health_check_task."""

    @pytest.mark.asyncio
    async def test_health_check_no_url_fails(self):
        """Test health check fails when no URL configured."""
        agent = DeployAgent()

        task = AgentTask(
            task_type="health_check",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "URL not configured" in result.error

    @pytest.mark.asyncio
    async def test_health_check_success_200(self):
        """Test health check with 200 response."""
        agent = DeployAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="health_check",
                parameters={"url": "https://example.com/health"},
                domain=AgentDomain.DEPLOY,
            )

            result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_health_check_failure_500(self):
        """Test health check with 500 response."""
        agent = DeployAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.side_effect = Exception("Not JSON")
            mock_response.text = "Internal Server Error"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            task = AgentTask(
                task_type="health_check",
                parameters={"url": "https://example.com/health"},
                domain=AgentDomain.DEPLOY,
            )

            result = await agent.execute_task(task)

        assert result.success is False
        assert result.data["status_code"] == 500

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Test health check with connection error."""
        agent = DeployAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection refused")
            )

            task = AgentTask(
                task_type="health_check",
                parameters={"url": "https://example.com/health"},
                domain=AgentDomain.DEPLOY,
            )

            result = await agent.execute_task(task)

        assert result.success is False
        assert "Connection refused" in result.error
        assert len(result.recommendations) > 0


class TestSetEnvHandler:
    """Tests for _handle_set_env."""

    @pytest.mark.asyncio
    async def test_set_env_without_client_fails(self):
        """Test set_env fails when railway client not configured."""
        agent = DeployAgent()
        task = AgentTask(
            task_type="set_env",
            parameters={"service_id": "svc-123", "key": "API_KEY", "value": "secret"},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "RailwayClient not configured" in result.error

    @pytest.mark.asyncio
    async def test_set_env_missing_required_params(self):
        """Test set_env fails when required params missing."""
        mock_railway = AsyncMock()
        agent = DeployAgent(railway_client=mock_railway)

        task = AgentTask(
            task_type="set_env",
            parameters={"key": "API_KEY"},  # Missing service_id
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "service_id and key are required" in result.error

    @pytest.mark.asyncio
    async def test_set_env_success(self):
        """Test successful environment variable setting."""
        mock_railway = AsyncMock()
        mock_railway.set_environment_variable.return_value = None

        agent = DeployAgent(railway_client=mock_railway)

        task = AgentTask(
            task_type="set_env",
            parameters={"service_id": "svc-123", "key": "API_KEY", "value": "secret123"},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data["service_id"] == "svc-123"
        assert result.data["key"] == "API_KEY"
        assert result.data["action"] == "set"
        mock_railway.set_environment_variable.assert_called_once_with(
            service_id="svc-123",
            key="API_KEY",
            value="secret123",
        )

    @pytest.mark.asyncio
    async def test_set_env_empty_value(self):
        """Test set_env with empty value (to clear)."""
        mock_railway = AsyncMock()
        agent = DeployAgent(railway_client=mock_railway)

        task = AgentTask(
            task_type="set_env",
            parameters={"service_id": "svc-123", "key": "OLD_KEY"},  # No value
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is True
        mock_railway.set_environment_variable.assert_called_once_with(
            service_id="svc-123",
            key="OLD_KEY",
            value="",
        )


class TestMessageHandlers:
    """Tests for message handlers."""

    @pytest.mark.asyncio
    async def test_handle_status_request_with_deployment_id(self):
        """Test status request with known deployment_id."""
        agent = DeployAgent()
        agent._active_deployments["deploy-123"] = {
            "status": "BUILDING",
            "project_id": "proj-1",
        }

        response = await agent._handle_status_request({"deployment_id": "deploy-123"})

        assert response["status"] == "BUILDING"
        assert response["project_id"] == "proj-1"

    @pytest.mark.asyncio
    async def test_handle_status_request_without_deployment_id(self):
        """Test status request without deployment_id returns summary."""
        agent = DeployAgent()
        agent._active_deployments["deploy-1"] = {}
        agent._active_deployments["deploy-2"] = {}

        response = await agent._handle_status_request({})

        assert response["active_deployments"] == 2
        assert "agent_status" in response

    @pytest.mark.asyncio
    async def test_handle_health_check_message(self):
        """Test health check message handler."""
        agent = DeployAgent()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            response = await agent._handle_health_check({"url": "https://example.com/health"})

        assert response["status_code"] == 200


class TestUnknownTaskType:
    """Tests for unknown task types."""

    @pytest.mark.asyncio
    async def test_unknown_task_type_fails(self):
        """Test unknown task type returns error."""
        agent = DeployAgent()

        task = AgentTask(
            task_type="unknown_task",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        result = await agent.execute_task(task)

        assert result.success is False
        assert "cannot handle task type" in result.error.lower()


class TestActiveDeploymentsTracking:
    """Tests for active deployments tracking."""

    @pytest.mark.asyncio
    async def test_get_active_deployments(self):
        """Test get_active_deployments returns copy."""
        agent = DeployAgent()
        agent._active_deployments["deploy-1"] = {"status": "BUILDING"}

        active = agent.get_active_deployments()

        assert active == {"deploy-1": {"status": "BUILDING"}}
        # Verify it's a copy
        active["deploy-2"] = {}
        assert "deploy-2" not in agent._active_deployments

    @pytest.mark.asyncio
    async def test_deployment_tracked_after_trigger(self):
        """Test deployment is tracked after successful trigger."""
        mock_railway = AsyncMock()
        mock_railway.trigger_deployment.return_value = {"id": "deploy-tracked"}

        config = DeploymentConfig(project_id="proj-1", environment_id="env-1")
        agent = DeployAgent(railway_client=mock_railway, config=config)

        task = AgentTask(
            task_type="deploy",
            parameters={},
            domain=AgentDomain.DEPLOY,
        )

        await agent.execute_task(task)

        assert "deploy-tracked" in agent._active_deployments
        assert agent._active_deployments["deploy-tracked"]["status"] == "BUILDING"
