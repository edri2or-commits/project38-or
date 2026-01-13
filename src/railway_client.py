"""Railway GraphQL API client for autonomous deployment management.

This module provides async client for Railway's GraphQL API with:
- Cloudflare workaround (timestamp query param)
- Exponential backoff retry with Tenacity
- State machine monitoring (INITIALIZING → ACTIVE/FAILED)
- Rollback capability
- Log retrieval
- Environment variable management

Example:
    >>> from src.secrets_manager import SecretManager
    >>> from src.railway_client import RailwayClient
    >>>
    >>> manager = SecretManager()
    >>> token = manager.get_secret("RAILWAY-API")
    >>> client = RailwayClient(api_token=token)
    >>>
    >>> # Trigger deployment
    >>> deployment_id = await client.trigger_deployment(
    ...     environment_id="env-123",
    ...     service_id="svc-456"
    ... )
    >>>
    >>> # Monitor until stable
    >>> status = await client.monitor_deployment_until_stable(deployment_id)
    >>> print(f"Final status: {status}")
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTION CLASSES
# =============================================================================


class RailwayAPIError(Exception):
    """Base exception for Railway API errors."""

    pass


class RailwayAuthenticationError(RailwayAPIError):
    """Authentication failed (invalid or expired token)."""

    pass


class RailwayRateLimitError(RailwayAPIError):
    """Rate limit exceeded."""

    pass


class RailwayDeploymentError(RailwayAPIError):
    """Deployment operation failed."""

    pass


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class DeploymentStatus:
    """Deployment status information.

    Attributes:
        id: Deployment ID
        status: Current status (INITIALIZING, BUILDING, DEPLOYING, ACTIVE,
                FAILED, CRASHED, REMOVED)
        static_url: Public URL if deployment is active
        created_at: ISO timestamp of creation
        updated_at: ISO timestamp of last update
        meta: Additional metadata from Railway
    """

    id: str
    status: str
    static_url: str | None
    created_at: str
    updated_at: str
    meta: dict[str, Any] | None = None


# =============================================================================
# RAILWAY CLIENT
# =============================================================================


class RailwayClient:
    """Async client for Railway GraphQL API.

    Implements autonomous deployment management with:
    - Cloudflare workaround (timestamp query param)
    - Exponential backoff retry (transient failures)
    - State machine monitoring (INITIALIZING → ACTIVE/FAILED)
    - Rollback capability (recovery mechanism)
    - Log retrieval (debugging)

    The client is stateless - state management is handled by orchestrator.

    Example:
        >>> client = RailwayClient(api_token="your-token")
        >>> deployment_id = await client.trigger_deployment(
        ...     environment_id="env-123",
        ...     service_id="svc-456"
        ... )
        >>> status = await client.monitor_deployment_until_stable(deployment_id)
    """

    def __init__(self, api_token: str):
        """Initialize Railway API client.

        Args:
            api_token: Railway API token from GCP Secret Manager
        """
        self.api_token = api_token
        self.base_url = "https://backboard.railway.com/graphql/v2"

    def _build_url(self) -> str:
        """Build GraphQL URL with Cloudflare workaround.

        CRITICAL: Railway's Cloudflare blocks requests without query params.
        Adding ?t={timestamp} prevents Error 1015 "You are being rate limited".

        Returns:
            URL with timestamp query parameter
        """
        return f"{self.base_url}?t={int(time.time())}"

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    async def _execute_graphql(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query with retry logic.

        Retry strategy:
        - Attempt 1: immediate
        - Attempt 2: wait 4s
        - Attempt 3: wait 8s
        - Attempt 4: wait 16s
        - Attempt 5: wait 32s
        - Attempt 6+: wait 60s (max)

        Args:
            query: GraphQL query or mutation
            variables: Query variables

        Returns:
            Parsed JSON response data

        Raises:
            RailwayAuthenticationError: If token is invalid
            RailwayRateLimitError: If rate limit exceeded
            RailwayAPIError: For other API errors
            httpx.HTTPStatusError: If all retries fail
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._build_url(),
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                # Handle HTTP-level errors
                if response.status_code == 401:
                    raise RailwayAuthenticationError("Invalid or expired API token")

                if response.status_code == 429:
                    raise RailwayRateLimitError("Rate limit exceeded")

                response.raise_for_status()

                # Handle GraphQL-level errors
                data = response.json()
                if "errors" in data:
                    error_messages = [e.get("message", str(e)) for e in data["errors"]]
                    logger.error(f"GraphQL errors: {error_messages}")
                    raise RailwayAPIError(f"GraphQL errors: {error_messages}")

                return data.get("data", {})

            except httpx.TimeoutException as e:
                logger.error(f"Request timed out: {e}")
                raise RailwayAPIError(f"Request timed out after 30s: {e}") from e

            except httpx.HTTPError as e:
                logger.error(f"HTTP error: {e}")
                raise RailwayAPIError(f"HTTP error: {e}") from e

    # =========================================================================
    # DEPLOYMENT OPERATIONS
    # =========================================================================

    async def trigger_deployment(self, environment_id: str, service_id: str) -> str:
        """Trigger a new deployment.

        Use Case: Agent detects new commit on main branch → trigger deployment.

        Args:
            environment_id: Railway environment ID
            service_id: Railway service ID

        Returns:
            New deployment ID

        Raises:
            RailwayAPIError: If deployment trigger fails

        Example:
            >>> deployment_id = await client.trigger_deployment(
            ...     environment_id="99c99a18-aea2-4d01-9360-6a93705102a0",
            ...     service_id="svc-456"
            ... )
            >>> print(f"Deployment initiated: {deployment_id}")
        """
        mutation = """
        mutation DeployService($environmentId: String!, $serviceId: String!) {
          serviceInstanceDeploy(
            environmentId: $environmentId
            serviceId: $serviceId
          )
        }
        """

        variables = {"environmentId": environment_id, "serviceId": service_id}

        data = await self._execute_graphql(mutation, variables)
        deployment_id = data["serviceInstanceDeploy"]

        logger.info(f"Triggered deployment: {deployment_id}")
        return deployment_id

    async def get_deployment_status(self, deployment_id: str) -> str:
        """Get current deployment status.

        Use Case: Agent polls this during monitoring phase.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            Status string (INITIALIZING, BUILDING, DEPLOYING, ACTIVE,
                          FAILED, CRASHED, REMOVED)

        Example:
            >>> status = await client.get_deployment_status("deploy-123")
            >>> print(f"Status: {status}")
        """
        query = """
        query GetDeployment($id: String!) {
          deployment(id: $id) {
            id
            status
            createdAt
            updatedAt
          }
        }
        """

        result = await self._execute_graphql(query, {"id": deployment_id})
        return result["deployment"]["status"]

    async def get_deployment_details(self, deployment_id: str) -> DeploymentStatus:
        """Get full deployment details (status + metadata).

        Use Case: Agent needs context for decision-making (URL, timestamps, etc.)

        Args:
            deployment_id: Railway deployment ID

        Returns:
            DeploymentStatus object with all details

        Example:
            >>> details = await client.get_deployment_details("deploy-123")
            >>> print(f"Status: {details.status}, URL: {details.static_url}")
        """
        query = """
        query GetDeploymentDetails($id: String!) {
          deployment(id: $id) {
            id
            status
            staticUrl
            createdAt
            updatedAt
            meta
          }
        }
        """

        result = await self._execute_graphql(query, {"id": deployment_id})
        deployment = result["deployment"]

        return DeploymentStatus(
            id=deployment["id"],
            status=deployment["status"],
            static_url=deployment.get("staticUrl"),
            created_at=deployment["createdAt"],
            updated_at=deployment["updatedAt"],
            meta=deployment.get("meta"),
        )

    async def rollback_deployment(self, deployment_id: str) -> str:
        """Rollback to a previous deployment.

        CRITICAL: This is the agent's primary recovery mechanism.
        Use when current deployment has status FAILED or CRASHED.

        How it works:
        1. Railway redeploys the specified deployment
        2. Creates new deployment with same configuration
        3. Returns new deployment ID

        Args:
            deployment_id: ID of stable deployment to rollback to

        Returns:
            New deployment ID

        Raises:
            RailwayAPIError: If rollback fails

        Example:
            >>> # Current deployment failed
            >>> last_stable = await client.get_last_active_deployment(
            ...     project_id="proj-123",
            ...     environment_id="env-456"
            ... )
            >>> rollback_id = await client.rollback_deployment(last_stable["id"])
            >>> print(f"Rolled back to: {rollback_id}")
        """
        mutation = """
        mutation DeploymentRollback($id: String!) {
          serviceInstanceRedeploy(deploymentId: $id)
        }
        """

        result = await self._execute_graphql(mutation, {"id": deployment_id})
        new_deployment_id = result["serviceInstanceRedeploy"]

        logger.info(
            f"Rolled back to deployment: {deployment_id}, new deployment: {new_deployment_id}"
        )
        return new_deployment_id

    async def get_last_active_deployment(
        self, project_id: str, environment_id: str
    ) -> dict[str, Any] | None:
        """Get the last successful (ACTIVE) deployment.

        Use Case: Find stable version to rollback to.

        Args:
            project_id: Railway project ID
            environment_id: Railway environment ID

        Returns:
            Deployment info dict or None if no ACTIVE deployment exists

        Example:
            >>> last_stable = await client.get_last_active_deployment(
            ...     project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
            ...     environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
            ... )
            >>> if last_stable:
            ...     print(f"Last stable: {last_stable['id']}")
        """
        query = """
        query GetDeployments($projectId: String!, $environmentId: String!) {
          deployments(
            input: {
              projectId: $projectId
              environmentId: $environmentId
            }
            first: 20
          ) {
            edges {
              node {
                id
                status
                createdAt
              }
            }
          }
        }
        """

        result = await self._execute_graphql(
            query, {"projectId": project_id, "environmentId": environment_id}
        )

        deployments = result["deployments"]["edges"]
        for edge in deployments:
            if edge["node"]["status"] == "ACTIVE":
                return edge["node"]

        return None

    # =========================================================================
    # MONITORING & LOGS
    # =========================================================================

    async def get_build_logs(self, deployment_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve build logs for debugging.

        Use Case: Deployment FAILED → agent reads logs to identify error.

        Args:
            deployment_id: Railway deployment ID
            limit: Max number of log lines

        Returns:
            List of log entries with:
            - message: Log line text
            - timestamp: When logged
            - severity: ERROR, INFO, WARN

        Example:
            >>> logs = await client.get_build_logs("deploy-123")
            >>> errors = [log for log in logs if log["severity"] == "ERROR"]
            >>> if errors:
            ...     print(f"Build error: {errors[0]['message']}")
        """
        query = """
        query BuildLogs($deploymentId: String!, $limit: Int) {
          buildLogs(deploymentId: $deploymentId, limit: $limit) {
            lines {
              message
              timestamp
              severity
            }
          }
        }
        """

        result = await self._execute_graphql(query, {"deploymentId": deployment_id, "limit": limit})
        return result["buildLogs"]["lines"]

    async def get_runtime_logs(self, deployment_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve runtime logs (stdout/stderr).

        Use Case: Deployment CRASHED → agent reads logs to identify exception.

        Args:
            deployment_id: Railway deployment ID
            limit: Max number of log lines

        Returns:
            List of log entries with message, timestamp, severity

        Example:
            >>> logs = await client.get_runtime_logs("deploy-123")
            >>> for log in logs:
            ...     print(f"{log['timestamp']}: {log['message']}")
        """
        query = """
        query RuntimeLogs($deploymentId: String!, $limit: Int) {
          runtimeLogs(deploymentId: $deploymentId, limit: $limit) {
            lines {
              message
              timestamp
              severity
            }
          }
        }
        """

        result = await self._execute_graphql(query, {"deploymentId": deployment_id, "limit": limit})
        return result["runtimeLogs"]["lines"]

    async def get_deployment_metrics(self, deployment_id: str) -> dict[str, Any]:
        """Get resource utilization metrics.

        Use Case: Agent detects performance degradation → scales resources.

        Args:
            deployment_id: Railway deployment ID

        Returns:
            Dictionary with:
            - cpu_usage: CPU percentage
            - memory_usage: RAM in MB
            - request_count: HTTP requests
            - response_time: Avg latency in ms

        Note:
            Metrics availability depends on Railway plan tier.
        """
        query = """
        query DeploymentMetrics($id: String!) {
          deploymentMetrics(deploymentId: $id) {
            cpuUsage
            memoryUsage
            requestCount
            responseTime
          }
        }
        """

        result = await self._execute_graphql(query, {"id": deployment_id})
        return result["deploymentMetrics"]

    # =========================================================================
    # AUTONOMOUS MONITORING
    # =========================================================================

    async def monitor_deployment_until_stable(
        self,
        deployment_id: str,
        timeout_seconds: int = 600,
        poll_interval: int = 5,
    ) -> str:
        """Monitor deployment until it reaches a stable state.

        Implements the State Machine monitoring logic:
        - Stable States: ACTIVE (success), FAILED (build error),
                        CRASHED (runtime error)
        - Transient States: INITIALIZING, BUILDING, DEPLOYING (keep polling)

        Args:
            deployment_id: Deployment to monitor
            timeout_seconds: Max time to wait (default: 10 minutes)
            poll_interval: Seconds between status checks

        Returns:
            Final status (ACTIVE, FAILED, or CRASHED)

        Raises:
            TimeoutError: If deployment doesn't stabilize in time

        Example:
            >>> deployment_id = await client.trigger_deployment(...)
            >>> final_status = await client.monitor_deployment_until_stable(
            ...     deployment_id
            ... )
            >>> if final_status == "ACTIVE":
            ...     print("Deployment successful!")
            >>> elif final_status == "FAILED":
            ...     logs = await client.get_build_logs(deployment_id)
            ...     print(f"Build failed: {logs}")
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout_seconds:
            status = await self.get_deployment_status(deployment_id)
            logger.info(f"Deployment {deployment_id} status: {status}")

            # Stable states - return immediately
            if status in ("ACTIVE", "FAILED", "CRASHED", "REMOVED"):
                return status

            # Transient states - keep polling
            if status in ("INITIALIZING", "BUILDING", "DEPLOYING"):
                await asyncio.sleep(poll_interval)
                continue

            # Unknown state - raise error
            raise ValueError(f"Unknown deployment status: {status}")

        raise TimeoutError(
            f"Deployment {deployment_id} did not stabilize within {timeout_seconds}s"
        )

    # =========================================================================
    # SERVICE MANAGEMENT
    # =========================================================================

    async def list_services(self, project_id: str, environment_id: str) -> list[dict[str, Any]]:
        """List all services in a project environment.

        Args:
            project_id: Railway project ID
            environment_id: Railway environment ID

        Returns:
            List of service dicts with id, name, icon, createdAt

        Example:
            >>> services = await client.list_services(
            ...     project_id="95ec21cc-9ada-41c5-8485-12f9a00e0116",
            ...     environment_id="99c99a18-aea2-4d01-9360-6a93705102a0"
            ... )
            >>> for service in services:
            ...     print(f"{service['name']}: {service['id']}")
        """
        query = """
        query ListServices($projectId: String!, $environmentId: String!) {
          project(id: $projectId) {
            services(environmentId: $environmentId) {
              edges {
                node {
                  id
                  name
                  icon
                  createdAt
                }
              }
            }
          }
        }
        """

        variables = {"projectId": project_id, "environmentId": environment_id}

        data = await self._execute_graphql(query, variables)
        edges = data["project"]["services"]["edges"]

        return [edge["node"] for edge in edges]

    async def get_service_details(self, service_id: str) -> dict[str, Any]:
        """Get detailed information about a service.

        Args:
            service_id: Railway service ID

        Returns:
            Service details dict with deployments list

        Example:
            >>> details = await client.get_service_details("svc-123")
            >>> print(f"Service: {details['name']}")
            >>> print(f"Deployments: {len(details['deployments'])}")
        """
        query = """
        query ServiceDetails($serviceId: String!) {
          service(id: $serviceId) {
            id
            name
            icon
            createdAt
            deployments(first: 10) {
              edges {
                node {
                  id
                  status
                  createdAt
                }
              }
            }
          }
        }
        """

        result = await self._execute_graphql(query, {"serviceId": service_id})
        service = result["service"]

        # Flatten deployments
        service["deployments"] = [edge["node"] for edge in service["deployments"]["edges"]]

        return service

    # =========================================================================
    # ENVIRONMENT VARIABLES
    # =========================================================================

    async def set_environment_variable(
        self, service_id: str, environment_id: str, key: str, value: str
    ) -> None:
        """Set an environment variable.

        Use Case: Agent updates configuration dynamically.

        Args:
            service_id: Railway service ID
            environment_id: Railway environment ID
            key: Variable name
            value: Variable value

        Security:
            Never log the value parameter.

        Example:
            >>> await client.set_environment_variable(
            ...     service_id="svc-123",
            ...     environment_id="env-456",
            ...     key="MAX_WORKERS",
            ...     value="4"
            ... )
        """
        mutation = """
        mutation SetEnvVar(
          $serviceId: String!,
          $environmentId: String!,
          $key: String!,
          $value: String!
        ) {
          variableUpsert(
            input: {
              serviceId: $serviceId,
              environmentId: $environmentId,
              name: $key,
              value: $value
            }
          ) {
            id
          }
        }
        """

        await self._execute_graphql(
            mutation,
            {
                "serviceId": service_id,
                "environmentId": environment_id,
                "key": key,
                "value": value,
            },
        )

        logger.info(
            f"Set environment variable {key} for service {service_id} "
            f"in environment {environment_id}"
        )
