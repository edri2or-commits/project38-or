"""Main Orchestrator for Autonomous Deployment Management.

Implements the OODA Loop (Observe-Orient-Decide-Act) pattern for autonomous
Railway deployment management with GitHub App integration and n8n orchestration.

Architecture:
- Observer: Collects data from Railway, GitHub, n8n
- Orienter: Analyzes context and builds world model
- Decider: Makes decisions based on policy engine
- Actor: Executes actions through worker agents

Example:
    >>> from src.orchestrator import MainOrchestrator
    >>> from src.railway_client import RailwayClient
    >>> from src.github_app_client import GitHubAppClient
    >>> from src.n8n_client import N8nClient
    >>> from src.secrets_manager import SecretManager
    >>>
    >>> # Initialize with all clients
    >>> manager = SecretManager()
    >>> orchestrator = MainOrchestrator(
    ...     railway=RailwayClient(api_key=manager.get_secret("RAILWAY-API")),
    ...     github=GitHubAppClient(
    ...         app_id=123456,
    ...         installation_id=789012,
    ...         private_key=manager.get_secret("github-app-private-key")
    ...     ),
    ...     n8n=N8nClient(
    ...         base_url="https://n8n.railway.app",
    ...         api_key=manager.get_secret("N8N-API")
    ...     )
    ... )
    >>>
    >>> # Handle deployment event
    >>> result = await orchestrator.handle_deployment_event({
    ...     "type": "push",
    ...     "commit": "abc123",
    ...     "author": "developer@example.com"
    ... })
"""

import asyncio
import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from src.github_app_client import GitHubAppClient
from src.n8n_client import N8nClient
from src.railway_client import RailwayClient


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================
class DeploymentState(str, Enum):
    """Deployment lifecycle states."""

    IDLE = "idle"
    OBSERVING = "observing"
    ORIENTING = "orienting"
    DECIDING = "deciding"
    ACTING = "acting"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ActionType(str, Enum):
    """Available action types."""

    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    SCALE = "scale"
    ALERT = "alert"
    CREATE_ISSUE = "create_issue"
    MERGE_PR = "merge_pr"
    EXECUTE_WORKFLOW = "execute_workflow"


# ============================================================================
# OBSERVATION DATA CLASSES
# ============================================================================
class Observation:
    """Represents a single observation from a data source."""

    def __init__(
        self,
        source: str,
        timestamp: datetime,
        data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize observation.

        Args:
            source: Source system (railway, github, n8n)
            timestamp: When observation was made
            data: Observation data
            metadata: Additional context
        """
        self.source = source
        self.timestamp = timestamp
        self.data = data
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        """String representation."""
        return f"Observation(source={self.source}, timestamp={self.timestamp}, data={self.data})"


class WorldModel:
    """Represents the agent's understanding of current system state."""

    def __init__(self):
        """Initialize world model."""
        self.railway_state: dict[str, Any] = {}
        self.github_state: dict[str, Any] = {}
        self.n8n_state: dict[str, Any] = {}
        self.observations: list[Observation] = []
        self.last_update: datetime = datetime.now(UTC)

    def update(self, observation: Observation) -> None:
        """Update world model with new observation.

        Args:
            observation: New observation to integrate
        """
        self.observations.append(observation)
        self.last_update = observation.timestamp

        # Update relevant state
        if observation.source == "railway":
            self.railway_state.update(observation.data)
        elif observation.source == "github":
            self.github_state.update(observation.data)
        elif observation.source == "n8n":
            self.n8n_state.update(observation.data)

    def get_recent_observations(self, limit: int = 10) -> list[Observation]:
        """Get recent observations.

        Args:
            limit: Max observations to return

        Returns:
            List of recent observations
        """
        return self.observations[-limit:]


class Decision:
    """Represents a decision made by the policy engine."""

    def __init__(
        self,
        action: ActionType,
        reasoning: str,
        parameters: dict[str, Any],
        priority: int = 5,
    ):
        """Initialize decision.

        Args:
            action: Action to take
            reasoning: Why this decision was made
            parameters: Action parameters
            priority: Decision priority (1-10, higher = more urgent)
        """
        self.action = action
        self.reasoning = reasoning
        self.parameters = parameters
        self.priority = priority
        self.timestamp = datetime.now(UTC)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Decision(action={self.action}, priority={self.priority}, reasoning={self.reasoning})"
        )


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================
class MainOrchestrator:
    """Main orchestrator implementing OODA loop for autonomous operations.

    Coordinates Railway, GitHub, and n8n clients to autonomously manage
    deployments, handle failures, and maintain system health.

    Attributes:
        railway: Railway GraphQL API client
        github: GitHub App REST API client
        n8n: n8n workflow orchestration client
        world_model: Current understanding of system state
        state: Current orchestrator state
    """

    def __init__(
        self,
        railway: RailwayClient,
        github: GitHubAppClient,
        n8n: N8nClient,
        project_id: str,
        environment_id: str,
        owner: str = "edri2or-commits",
        repo: str = "project38-or",
    ):
        """Initialize orchestrator with all clients.

        Args:
            railway: Railway client
            github: GitHub App client
            n8n: n8n client
            project_id: Railway project ID
            environment_id: Railway environment ID
            owner: GitHub repository owner
            repo: GitHub repository name
        """
        self.railway = railway
        self.github = github
        self.n8n = n8n
        self.project_id = project_id
        self.environment_id = environment_id
        self.owner = owner
        self.repo = repo

        self.world_model = WorldModel()
        self.state = DeploymentState.IDLE
        self.logger = logging.getLogger(__name__)

    # ========================================================================
    # OODA LOOP IMPLEMENTATION
    # ========================================================================

    async def observe(self) -> list[Observation]:
        """Phase 1: OBSERVE - Collect data from all sources.

        Returns:
            List of observations from Railway, GitHub, n8n

        Example:
            >>> observations = await orchestrator.observe()
            >>> for obs in observations:
            ...     print(f"{obs.source}: {obs.data}")
        """
        self.state = DeploymentState.OBSERVING
        observations = []

        # Observe Railway state
        try:
            services = await self.railway.list_services(
                project_id=self.project_id, environment_id=self.environment_id
            )
            observations.append(
                Observation(
                    source="railway",
                    timestamp=datetime.now(UTC),
                    data={"services": services, "project_id": self.project_id},
                )
            )
        except Exception as e:
            self.logger.error(f"Railway observation failed: {e}")

        # Observe GitHub state
        try:
            workflow_runs = await self.github.get_workflow_runs(
                owner=self.owner, repo=self.repo, per_page=5
            )
            observations.append(
                Observation(
                    source="github",
                    timestamp=datetime.now(UTC),
                    data={"workflow_runs": workflow_runs},
                )
            )
        except Exception as e:
            self.logger.error(f"GitHub observation failed: {e}")

        # Observe n8n state
        try:
            executions = await self.n8n.get_recent_executions(limit=5)
            observations.append(
                Observation(
                    source="n8n",
                    timestamp=datetime.now(UTC),
                    data={"recent_executions": executions},
                )
            )
        except Exception as e:
            self.logger.error(f"n8n observation failed: {e}")

        return observations

    async def orient(self, observations: list[Observation]) -> WorldModel:
        """Phase 2: ORIENT - Analyze observations and build world model.

        Args:
            observations: List of observations to analyze

        Returns:
            Updated world model with context

        Example:
            >>> observations = await orchestrator.observe()
            >>> world_model = await orchestrator.orient(observations)
            >>> print(f"Railway services: {len(world_model.railway_state.get('services', []))}")
        """
        self.state = DeploymentState.ORIENTING

        # Update world model with new observations
        for obs in observations:
            self.world_model.update(obs)

        # Analyze patterns and correlations
        # (In production, this would include ML/heuristics)
        self._analyze_deployment_health()
        self._analyze_ci_status()
        self._analyze_workflow_health()

        return self.world_model

    async def decide(self, world_model: WorldModel) -> Decision | None:
        """Phase 3: DECIDE - Make decision based on world model.

        Args:
            world_model: Current understanding of system state

        Returns:
            Decision to execute, or None if no action needed

        Example:
            >>> world_model = await orchestrator.orient(observations)
            >>> decision = await orchestrator.decide(world_model)
            >>> if decision:
            ...     print(f"Action: {decision.action}, Reason: {decision.reasoning}")
        """
        self.state = DeploymentState.DECIDING

        # Check for deployment failures
        railway_state = world_model.railway_state
        if railway_state.get("deployment_failed"):
            return Decision(
                action=ActionType.ROLLBACK,
                reasoning="Railway deployment failed, initiating rollback",
                parameters={"deployment_id": railway_state.get("failed_deployment_id")},
                priority=10,
            )

        # Check for CI failures
        github_state = world_model.github_state
        workflow_runs = github_state.get("workflow_runs", {}).get("data", [])
        if workflow_runs and workflow_runs[0].get("conclusion") == "failure":
            return Decision(
                action=ActionType.CREATE_ISSUE,
                reasoning="CI workflow failed, creating issue for investigation",
                parameters={
                    "title": f"CI Failure: {workflow_runs[0].get('name')}",
                    "body": f"Workflow run failed: {workflow_runs[0].get('html_url')}",
                },
                priority=7,
            )

        # Check for successful PR ready to merge
        if github_state.get("pr_ready_to_merge"):
            pr_number = github_state.get("pr_number")
            return Decision(
                action=ActionType.MERGE_PR,
                reasoning="PR checks passed, ready to merge",
                parameters={"pr_number": pr_number},
                priority=5,
            )

        # No action needed
        return None

    async def act(self, decision: Decision) -> dict[str, Any]:
        """Phase 4: ACT - Execute decision through worker agents.

        Args:
            decision: Decision to execute

        Returns:
            Result of action execution

        Raises:
            ValueError: If action type is not supported

        Example:
            >>> decision = Decision(
            ...     action=ActionType.ROLLBACK,
            ...     reasoning="Deployment failed",
            ...     parameters={"deployment_id": "abc123"}
            ... )
            >>> result = await orchestrator.act(decision)
            >>> print(f"Rollback result: {result}")
        """
        self.state = DeploymentState.ACTING
        self.logger.info(f"Executing action: {decision.action}, Reasoning: {decision.reasoning}")

        try:
            if decision.action == ActionType.DEPLOY:
                return await self._act_deploy(decision.parameters)
            elif decision.action == ActionType.ROLLBACK:
                return await self._act_rollback(decision.parameters)
            elif decision.action == ActionType.CREATE_ISSUE:
                return await self._act_create_issue(decision.parameters)
            elif decision.action == ActionType.MERGE_PR:
                return await self._act_merge_pr(decision.parameters)
            elif decision.action == ActionType.ALERT:
                return await self._act_alert(decision.parameters)
            elif decision.action == ActionType.EXECUTE_WORKFLOW:
                return await self._act_execute_workflow(decision.parameters)
            else:
                raise ValueError(f"Unsupported action type: {decision.action}")

        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
            self.state = DeploymentState.FAILED
            raise

    # ========================================================================
    # COMPLETE OODA CYCLE
    # ========================================================================

    async def run_cycle(self) -> Decision | None:
        """Run complete OODA cycle: Observe → Orient → Decide → Act.

        Returns:
            Decision executed, or None if no action needed

        Example:
            >>> decision = await orchestrator.run_cycle()
            >>> if decision:
            ...     print(f"Executed: {decision.action}")
        """
        # Observe
        observations = await self.observe()

        # Orient
        world_model = await self.orient(observations)

        # Decide
        decision = await self.decide(world_model)

        # Act (if decision was made)
        if decision:
            await self.act(decision)
            self.state = DeploymentState.SUCCESS
            return decision

        self.state = DeploymentState.IDLE
        return None

    async def run_continuous(self, interval_seconds: int = 60):
        """Run OODA loop continuously with specified interval.

        Args:
            interval_seconds: Seconds between cycles (default: 60)

        Example:
            >>> # Run orchestrator continuously
            >>> await orchestrator.run_continuous(interval_seconds=30)
        """
        while True:
            try:
                await self.run_cycle()
            except Exception as e:
                self.logger.error(f"OODA cycle failed: {e}")
                self.state = DeploymentState.FAILED

            await asyncio.sleep(interval_seconds)

    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================

    async def handle_deployment_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Handle deployment event from GitHub webhook.

        Args:
            event: GitHub webhook event data

        Returns:
            Result of deployment handling

        Example:
            >>> result = await orchestrator.handle_deployment_event({
            ...     "type": "push",
            ...     "commit": "abc123",
            ...     "ref": "refs/heads/main"
            ... })
        """
        commit_sha = event.get("commit", event.get("head_commit", {}).get("sha"))
        ref = event.get("ref", "")

        # Only deploy main branch
        if ref != "refs/heads/main":
            return {"status": "skipped", "reason": "Not main branch"}

        # Trigger deployment
        decision = Decision(
            action=ActionType.DEPLOY,
            reasoning=f"New commit to main: {commit_sha}",
            parameters={"commit": commit_sha},
            priority=8,
        )

        result = await self.act(decision)
        return result

    async def handle_deployment_failure(self, deployment_id: str) -> dict[str, Any] | None:
        """Handle deployment failure - rollback and alert.

        Args:
            deployment_id: Failed deployment ID

        Returns:
            Result of failure handling

        Example:
            >>> result = await orchestrator.handle_deployment_failure("deploy-123")
            >>> print(f"Rolled back to: {result.get('rollback_deployment_id')}")
        """
        # Get deployment history to find last successful deployment
        deployments = await self.railway.list_deployments(
            project_id=self.project_id, environment_id=self.environment_id, limit=10
        )

        # Find last successful deployment
        last_success = None
        for dep in deployments:
            if dep["status"] == "SUCCESS" and dep["id"] != deployment_id:
                last_success = dep
                break

        if not last_success:
            self.logger.error("No successful deployment found for rollback")
            return None

        # Execute rollback
        rollback_decision = Decision(
            action=ActionType.ROLLBACK,
            reasoning=f"Rolling back failed deployment {deployment_id}",
            parameters={"deployment_id": last_success["id"]},
            priority=10,
        )

        rollback_result = await self.act(rollback_decision)

        # Create issue for investigation
        issue_decision = Decision(
            action=ActionType.CREATE_ISSUE,
            reasoning="Deployment failure requires investigation",
            parameters={
                "title": f"Deployment Failure: {deployment_id}",
                "body": (
                    f"Deployment {deployment_id} failed and was rolled back to "
                    f"{last_success['id']}.\n\nInvestigate logs for root cause."
                ),
            },
            priority=9,
        )

        await self.act(issue_decision)

        # Send alert notification
        alert_decision = Decision(
            action=ActionType.ALERT,
            reasoning="Notify team of deployment failure",
            parameters={
                "workflow_id": "deployment-failure-alert",
                "data": {
                    "severity": "high",
                    "deployment_id": deployment_id,
                    "rollback_deployment_id": last_success["id"],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            },
            priority=9,
        )

        await self.act(alert_decision)

        return rollback_result

    # ========================================================================
    # PRIVATE ACTION IMPLEMENTATIONS
    # ========================================================================

    async def _act_deploy(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute deployment action."""
        deployment = await self.railway.trigger_deployment(
            project_id=self.project_id, environment_id=self.environment_id
        )

        # Wait for deployment to complete
        result = await self.railway.wait_for_deployment(deployment_id=deployment["id"], timeout=600)

        deployment_result = {
            "deployment_id": deployment["id"],
            "status": result["status"],
            "url": result.get("url"),
        }

        # Send success notification if deployment succeeded
        if result["status"] == "SUCCESS":
            alert_decision = Decision(
                action=ActionType.ALERT,
                reasoning="Notify team of successful deployment",
                parameters={
                    "workflow_id": "deployment-success-alert",
                    "data": {
                        "severity": "info",
                        "deployment_id": deployment["id"],
                        "url": result.get("url"),
                        "commit": params.get("commit"),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                },
                priority=5,
            )
            await self.act(alert_decision)

        return deployment_result

    async def _act_rollback(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute rollback action."""
        deployment_id = params["deployment_id"]
        result = await self.railway.rollback_deployment(deployment_id=deployment_id)

        return {"rollback_deployment_id": result["id"], "status": result["status"]}

    async def _act_create_issue(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute create issue action."""
        issue = await self.github.create_issue(
            owner=self.owner,
            repo=self.repo,
            title=params["title"],
            body=params["body"],
        )

        return {"issue_number": issue["number"], "url": issue["html_url"]}

    async def _act_merge_pr(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute merge PR action."""
        result = await self.github.merge_pull_request(
            owner=self.owner, repo=self.repo, pull_number=params["pr_number"]
        )

        return {"merged": result["merged"], "sha": result["sha"]}

    async def _act_alert(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute alert action via n8n workflow."""
        workflow_id = params.get("workflow_id", "alert-workflow")
        execution_id = await self.n8n.execute_workflow(
            workflow_id=workflow_id, data=params.get("data", {})
        )

        return {"execution_id": execution_id}

    async def _act_execute_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute n8n workflow."""
        execution_id = await self.n8n.execute_workflow(
            workflow_id=params["workflow_id"], data=params.get("data", {})
        )

        return {"execution_id": execution_id}

    # ========================================================================
    # PRIVATE ANALYSIS METHODS
    # ========================================================================

    def _analyze_deployment_health(self) -> None:
        """Analyze Railway deployment health from world model."""
        railway_state = self.world_model.railway_state
        services = railway_state.get("services", [])

        for service in services:
            latest_deployment = service.get("latestDeployment", {})
            status = latest_deployment.get("status")

            if status in ["FAILED", "CRASHED"]:
                railway_state["deployment_failed"] = True
                railway_state["failed_deployment_id"] = latest_deployment.get("id")
                break

    def _analyze_ci_status(self) -> None:
        """Analyze GitHub CI status from world model."""
        # Analysis logic would go here
        # Will use self.world_model.github_state for pattern detection
        pass

    def _analyze_workflow_health(self) -> None:
        """Analyze n8n workflow health from world model."""
        # Analysis logic would go here
        # Will use self.world_model.n8n_state for pattern detection
        pass
