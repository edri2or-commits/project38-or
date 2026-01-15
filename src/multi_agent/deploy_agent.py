"""DeployAgent - Specialized Agent for Railway Deployments.

Handles all Railway-related operations:
- Trigger deployments
- Monitor deployment status
- Execute rollbacks
- Scale services
- Manage environment variables

Integrates with:
- RailwayClient for API operations
- AutonomousController for safety guardrails
- n8n for deployment notifications

Example:
    >>> from src.multi_agent.deploy_agent import DeployAgent
    >>> from src.railway_client import RailwayClient
    >>>
    >>> railway = RailwayClient(api_token="...")
    >>> agent = DeployAgent(railway_client=railway)
    >>> result = await agent.execute_task(AgentTask(
    ...     task_type="deploy",
    ...     parameters={"project_id": "...", "environment_id": "..."}
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
    TaskPriority,
)

if TYPE_CHECKING:
    from src.railway_client import RailwayClient


@dataclass
class DeploymentConfig:
    """Configuration for deployment operations.

    Attributes:
        project_id: Railway project ID
        environment_id: Railway environment ID
        max_wait_seconds: Maximum time to wait for deployment
        health_check_url: URL to verify deployment health
        rollback_on_failure: Whether to auto-rollback on health check failure
    """

    project_id: str
    environment_id: str
    max_wait_seconds: int = 300
    health_check_url: str = ""
    rollback_on_failure: bool = True


class DeployAgent(SpecializedAgent):
    """Specialized agent for Railway deployment operations.

    Capabilities:
    - deploy: Trigger new deployment
    - rollback: Rollback to previous deployment
    - status: Get deployment status
    - scale: Scale service resources
    - health_check: Check deployment health
    - set_env: Set environment variable

    Attributes:
        railway: RailwayClient for API operations
        config: Deployment configuration
    """

    def __init__(
        self,
        railway_client: "RailwayClient | None" = None,
        config: DeploymentConfig | None = None,
        agent_id: str | None = None,
    ):
        """Initialize DeployAgent.

        Args:
            railway_client: RailwayClient for Railway API operations
            config: Deployment configuration
            agent_id: Unique agent identifier
        """
        super().__init__(agent_id=agent_id, domain=AgentDomain.DEPLOY)
        self.railway = railway_client
        self.config = config or DeploymentConfig(
            project_id="",
            environment_id="",
        )
        self.logger = logging.getLogger(f"agent.deploy.{self.agent_id}")

        # Track active deployments
        self._active_deployments: dict[str, dict[str, Any]] = {}

        # Register message handlers
        self.register_message_handler("deployment_status_request", self._handle_status_request)
        self.register_message_handler("health_check_request", self._handle_health_check)

    @property
    def capabilities(self) -> list[AgentCapability]:
        """List of deployment capabilities."""
        return [
            AgentCapability(
                name="deploy",
                domain=AgentDomain.DEPLOY,
                description="Trigger new Railway deployment",
                requires_approval=False,
                max_concurrent=2,
                cooldown_seconds=30,
            ),
            AgentCapability(
                name="rollback",
                domain=AgentDomain.DEPLOY,
                description="Rollback to previous successful deployment",
                requires_approval=False,
                max_concurrent=1,
                cooldown_seconds=60,
            ),
            AgentCapability(
                name="deployment_status",
                domain=AgentDomain.DEPLOY,
                description="Get current deployment status",
                requires_approval=False,
                max_concurrent=5,
                cooldown_seconds=0,
            ),
            AgentCapability(
                name="scale",
                domain=AgentDomain.DEPLOY,
                description="Scale service resources",
                requires_approval=True,  # Scaling can affect costs
                max_concurrent=1,
                cooldown_seconds=120,
            ),
            AgentCapability(
                name="health_check",
                domain=AgentDomain.DEPLOY,
                description="Check deployment health",
                requires_approval=False,
                max_concurrent=10,
                cooldown_seconds=0,
            ),
            AgentCapability(
                name="set_env",
                domain=AgentDomain.DEPLOY,
                description="Set environment variable",
                requires_approval=True,  # Environment changes are sensitive
                max_concurrent=1,
                cooldown_seconds=10,
            ),
        ]

    async def _execute_task_internal(self, task: AgentTask) -> AgentResult:
        """Execute deployment task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """
        task_handlers = {
            "deploy": self._handle_deploy,
            "rollback": self._handle_rollback,
            "deployment_status": self._handle_deployment_status,
            "scale": self._handle_scale,
            "health_check": self._handle_health_check_task,
            "set_env": self._handle_set_env,
        }

        handler = task_handlers.get(task.task_type)
        if not handler:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Unknown task type: {task.task_type}",
            )

        return await handler(task)

    async def _handle_deploy(self, task: AgentTask) -> AgentResult:
        """Handle deployment trigger.

        Args:
            task: Deployment task with parameters:
                - project_id: Optional, uses config default
                - environment_id: Optional, uses config default
                - service_id: Optional, for specific service

        Returns:
            AgentResult with deployment info
        """
        if not self.railway:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="RailwayClient not configured",
            )

        project_id = task.parameters.get("project_id") or self.config.project_id
        environment_id = task.parameters.get("environment_id") or self.config.environment_id

        if not project_id or not environment_id:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="project_id and environment_id are required",
            )

        try:
            self.logger.info(f"Triggering deployment for project {project_id}")

            deployment = await self.railway.trigger_deployment(
                project_id=project_id,
                environment_id=environment_id,
            )

            deployment_id = deployment.get("id", "unknown")
            self._active_deployments[deployment_id] = {
                "triggered_at": datetime.now(UTC).isoformat(),
                "project_id": project_id,
                "environment_id": environment_id,
                "status": "BUILDING",
            }

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "deployment_id": deployment_id,
                    "project_id": project_id,
                    "environment_id": environment_id,
                    "status": "BUILDING",
                },
                recommendations=[
                    f"Monitor deployment status with deployment_id: {deployment_id}",
                    "Set up health check after deployment completes",
                ],
            )

        except Exception as e:
            self.logger.error(f"Deployment trigger failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                recommendations=[
                    "Check Railway API token validity",
                    "Verify project and environment IDs",
                    "Consider rollback if previous deployment was working",
                ],
            )

    async def _handle_rollback(self, task: AgentTask) -> AgentResult:
        """Handle rollback to previous deployment.

        Args:
            task: Rollback task with parameters:
                - project_id: Optional, uses config default
                - environment_id: Optional, uses config default
                - target_deployment_id: Optional, specific deployment to rollback to

        Returns:
            AgentResult with rollback info
        """
        if not self.railway:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="RailwayClient not configured",
            )

        project_id = task.parameters.get("project_id") or self.config.project_id
        environment_id = task.parameters.get("environment_id") or self.config.environment_id

        try:
            self.logger.info(f"Initiating rollback for project {project_id}")

            # Find last successful deployment
            last_active = await self.railway.get_last_active_deployment(
                project_id=project_id,
                environment_id=environment_id,
            )

            if not last_active:
                return AgentResult(
                    task_id=task.task_id,
                    success=False,
                    error="No previous successful deployment found",
                )

            # Trigger rollback
            rollback = await self.railway.rollback_deployment(
                project_id=project_id,
                environment_id=environment_id,
                deployment_id=last_active.get("id", ""),
            )

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "rollback_id": rollback.get("id"),
                    "rolled_back_to": last_active.get("id"),
                    "status": "ROLLING_BACK",
                },
                recommendations=[
                    "Monitor rollback completion",
                    "Investigate root cause of original failure",
                    "Create GitHub issue for tracking",
                ],
            )

        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                recommendations=[
                    "Manual intervention may be required",
                    "Check Railway dashboard for status",
                ],
            )

    async def _handle_deployment_status(self, task: AgentTask) -> AgentResult:
        """Get deployment status.

        Args:
            task: Status task with parameters:
                - deployment_id: Deployment to check
                - project_id: Optional

        Returns:
            AgentResult with status info
        """
        if not self.railway:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="RailwayClient not configured",
            )

        deployment_id = task.parameters.get("deployment_id")
        if not deployment_id:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="deployment_id is required",
            )

        try:
            status = await self.railway.get_deployment_status(deployment_id)

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "deployment_id": deployment_id,
                    "status": status.get("status", "UNKNOWN"),
                    "created_at": status.get("createdAt"),
                    "meta": status.get("meta", {}),
                },
            )

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_scale(self, task: AgentTask) -> AgentResult:
        """Handle service scaling.

        Args:
            task: Scale task with parameters:
                - service_id: Service to scale
                - replicas: Target replica count
                - cpu: CPU allocation
                - memory: Memory allocation

        Returns:
            AgentResult with scaling info
        """
        # Scaling would require Railway service API
        # This is a placeholder for the capability
        return AgentResult(
            task_id=task.task_id,
            success=False,
            error="Scaling not yet implemented - requires Railway service API",
            recommendations=[
                "Use Railway dashboard for manual scaling",
                "Consider auto-scaling recommendations from AutoScalingAdvisor",
            ],
        )

    async def _handle_health_check_task(self, task: AgentTask) -> AgentResult:
        """Handle health check.

        Args:
            task: Health check task with parameters:
                - url: Health check URL
                - timeout: Request timeout in seconds

        Returns:
            AgentResult with health info
        """
        import httpx

        url = task.parameters.get("url") or self.config.health_check_url
        timeout = task.parameters.get("timeout", 10)

        if not url:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="Health check URL not configured",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=timeout)

                is_healthy = response.status_code == 200
                data = {"status_code": response.status_code, "url": url}

                try:
                    data["response"] = response.json()
                except Exception:
                    data["response"] = response.text[:500]

                return AgentResult(
                    task_id=task.task_id,
                    success=is_healthy,
                    data=data,
                    recommendations=(
                        []
                        if is_healthy
                        else ["Consider rollback if health check consistently fails"]
                    ),
                )

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Health check failed: {e}",
                recommendations=[
                    "Check if service is running",
                    "Verify network connectivity",
                    "Consider triggering a new deployment",
                ],
            )

    async def _handle_set_env(self, task: AgentTask) -> AgentResult:
        """Handle environment variable update.

        Args:
            task: Set env task with parameters:
                - service_id: Target service
                - key: Variable name
                - value: Variable value

        Returns:
            AgentResult with operation status
        """
        if not self.railway:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="RailwayClient not configured",
            )

        service_id = task.parameters.get("service_id")
        key = task.parameters.get("key")
        value = task.parameters.get("value")

        if not all([service_id, key]):
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error="service_id and key are required",
            )

        try:
            await self.railway.set_environment_variable(
                service_id=service_id,
                key=key,
                value=value or "",
            )

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={
                    "service_id": service_id,
                    "key": key,
                    "action": "set",
                },
                recommendations=[
                    "Deployment may be required for changes to take effect",
                ],
            )

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _handle_status_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle status request message from other agents.

        Args:
            payload: Request payload with optional deployment_id

        Returns:
            Status information
        """
        deployment_id = payload.get("deployment_id")
        if deployment_id and deployment_id in self._active_deployments:
            return self._active_deployments[deployment_id]

        return {
            "active_deployments": len(self._active_deployments),
            "agent_status": self.get_status(),
        }

    async def _handle_health_check(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle health check message from other agents.

        Args:
            payload: Request payload with url

        Returns:
            Health check result
        """
        task = AgentTask(
            task_type="health_check",
            parameters=payload,
            priority=TaskPriority.HIGH,
        )
        result = await self._handle_health_check_task(task)
        return result.data

    def get_active_deployments(self) -> dict[str, dict[str, Any]]:
        """Get currently tracked deployments.

        Returns:
            Dictionary of active deployments
        """
        return self._active_deployments.copy()
