"""n8n Workflow Orchestration Client for autonomous operations.

Implements REST API client for n8n workflow automation with dynamic workflow
creation, execution monitoring, and import/export capabilities.

Example:
    >>> from src.secrets_manager import SecretManager
    >>> from src.n8n_client import N8nClient
    >>>
    >>> # Initialize from GCP Secret Manager
    >>> manager = SecretManager()
    >>> api_key = manager.get_secret("N8N-API")
    >>>
    >>> client = N8nClient(
    ...     base_url="https://n8n.railway.app",
    ...     api_key=api_key
    ... )
    >>>
    >>> # Create deployment alert workflow
    >>> workflow = await client.create_workflow(
    ...     name="Railway Deployment Alert",
    ...     nodes=[...],
    ...     connections={...}
    ... )
    >>>
    >>> # Execute workflow with data
    >>> execution_id = await client.execute_workflow(
    ...     workflow_id=workflow["id"],
    ...     data={"alert": {"severity": "critical", "title": "Deployment Failed"}}
    ... )
"""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ============================================================================
# EXCEPTION CLASSES
# ============================================================================


class N8nError(Exception):
    """Base exception for n8n operations."""

    pass


class N8nAuthenticationError(N8nError):
    """Raised when n8n API authentication fails (401 Unauthorized)."""

    pass


class N8nNotFoundError(N8nError):
    """Raised when requested workflow/execution is not found (404)."""

    pass


class N8nValidationError(N8nError):
    """Raised when workflow validation fails (400 Bad Request)."""

    pass


# ============================================================================
# N8N CLIENT
# ============================================================================


class N8nClient:
    """Client for n8n REST API - workflow automation orchestration.

    Implements n8n REST API for programmatic workflow management, enabling
    autonomous agents to create, execute, and monitor workflows.

    Features:
    - Create/update/delete workflows programmatically
    - Execute workflows with custom data
    - Monitor execution status and results
    - Import/export workflows (version control)
    - Exponential backoff retry logic

    Attributes:
        base_url: n8n instance URL (e.g., "https://n8n.railway.app")
        api_key: n8n API key (X-N8N-API-KEY header)
    """

    def __init__(self, base_url: str, api_key: str):
        """Initialize n8n client.

        Args:
            base_url: n8n instance URL (e.g., "https://n8n.railway.app")
            api_key: n8n API key (from GCP Secret Manager: N8N-API)

        Example:
            >>> client = N8nClient(
            ...     base_url="https://n8n.railway.app",
            ...     api_key=secret_manager.get_secret("N8N-API")
            ... )
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _api_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated n8n API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/workflows")
            json_data: Request body (for POST/PUT)
            params: Query parameters (for GET)

        Returns:
            Parsed JSON response

        Raises:
            N8nAuthenticationError: If API key is invalid (401)
            N8nNotFoundError: If resource not found (404)
            N8nValidationError: If workflow validation fails (400)
            N8nError: For other API errors
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}/api/v1{endpoint}",
                    json=json_data,
                    params=params,
                    headers={
                        "X-N8N-API-KEY": self.api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                # Handle authentication errors
                if response.status_code == 401:
                    raise N8nAuthenticationError("Invalid n8n API key")

                # Handle not found
                if response.status_code == 404:
                    raise N8nNotFoundError(f"Resource not found: {endpoint}")

                # Handle validation errors
                if response.status_code == 400:
                    error_detail = response.text
                    raise N8nValidationError(f"Workflow validation failed: {error_detail}")

                response.raise_for_status()

                # Handle 204 No Content
                if response.status_code == 204:
                    return {}

                return response.json()
        except httpx.HTTPStatusError as e:
            raise N8nError(f"n8n API error: HTTP {e.response.status_code}") from e
        except httpx.TimeoutException as e:
            raise N8nError(f"n8n API timeout: {e}") from e
        except httpx.NetworkError as e:
            raise N8nError(f"n8n API network error: {e}") from e

    # ========================================================================
    # WORKFLOW MANAGEMENT
    # ========================================================================

    async def create_workflow(
        self,
        name: str,
        nodes: list[dict[str, Any]],
        connections: dict[str, Any],
        active: bool = True,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new workflow programmatically.

        Use Case: Agent creates alert workflow on first deployment.

        Args:
            name: Workflow name (e.g., "Railway Deployment Alert")
            nodes: List of node definitions (see n8n docs for node structure)
            connections: Connection graph (defines flow between nodes)
            active: Whether to activate immediately (default: True)
            settings: Optional workflow settings (timezone, error handling, etc.)

        Returns:
            Created workflow object with id, name, active status

        Raises:
            N8nValidationError: If workflow structure is invalid

        Example:
            >>> workflow = await client.create_workflow(
            ...     name="Railway Deployment Alert",
            ...     nodes=[
            ...         {
            ...             "name": "Webhook",
            ...             "type": "n8n-nodes-base.webhook",
            ...             "parameters": {"path": "railway-webhook"},
            ...             "position": [250, 300]
            ...         },
            ...         {
            ...             "name": "Telegram",
            ...             "type": "n8n-nodes-base.telegram",
            ...             "parameters": {"text": "Deployment failed!"},
            ...             "position": [450, 300]
            ...         }
            ...     ],
            ...     connections={"Webhook": {"main": [[{"node": "Telegram"}]]}},
            ...     active=True
            ... )
            >>> print(f"Workflow created: {workflow['id']}")
        """
        return await self._api_request(
            method="POST",
            endpoint="/workflows",
            json_data={
                "name": name,
                "nodes": nodes,
                "connections": connections,
                "active": active,
                "settings": settings or {},
            },
        )

    async def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow details by ID.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Workflow object with nodes, connections, active status

        Raises:
            N8nNotFoundError: If workflow doesn't exist

        Example:
            >>> workflow = await client.get_workflow("wf-abc123")
            >>> print(f"Workflow: {workflow['name']}, Active: {workflow['active']}")
        """
        return await self._api_request(method="GET", endpoint=f"/workflows/{workflow_id}")

    async def list_workflows(self, active_only: bool = False) -> list[dict[str, Any]]:
        """List all workflows.

        Use Case: Agent audits existing automation.

        Args:
            active_only: If True, return only active workflows

        Returns:
            List of workflow objects

        Example:
            >>> workflows = await client.list_workflows()
            >>> for wf in workflows:
            ...     print(f"{wf['name']}: {'active' if wf['active'] else 'inactive'}")
        """
        result = await self._api_request(method="GET", endpoint="/workflows")
        workflows = result.get("data", [])

        if active_only:
            workflows = [wf for wf in workflows if wf.get("active", False)]

        return workflows

    async def update_workflow(
        self,
        workflow_id: str,
        name: str | None = None,
        nodes: list[dict[str, Any]] | None = None,
        connections: dict[str, Any] | None = None,
        active: bool | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing workflow.

        Use Case: Agent modifies alert thresholds or routing logic.

        Args:
            workflow_id: n8n workflow ID
            name: New workflow name (optional)
            nodes: Updated node definitions (optional)
            connections: Updated connections (optional)
            active: Update active status (optional)
            settings: Updated settings (optional)

        Returns:
            Updated workflow object

        Raises:
            N8nNotFoundError: If workflow doesn't exist
            N8nValidationError: If updated structure is invalid

        Example:
            >>> updated = await client.update_workflow(
            ...     workflow_id="wf-abc123",
            ...     name="Updated Alert Workflow",
            ...     active=False
            ... )
        """
        # Get current workflow
        workflow = await self.get_workflow(workflow_id)

        # Update only provided fields
        if name is not None:
            workflow["name"] = name
        if nodes is not None:
            workflow["nodes"] = nodes
        if connections is not None:
            workflow["connections"] = connections
        if active is not None:
            workflow["active"] = active
        if settings is not None:
            workflow["settings"] = settings

        return await self._api_request(
            method="PUT", endpoint=f"/workflows/{workflow_id}", json_data=workflow
        )

    async def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow.

        Use Case: Agent cleans up temporary test workflows.

        Args:
            workflow_id: n8n workflow ID

        Raises:
            N8nNotFoundError: If workflow doesn't exist

        Example:
            >>> await client.delete_workflow("wf-test-123")
        """
        await self._api_request(method="DELETE", endpoint=f"/workflows/{workflow_id}")

    async def activate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Activate a workflow.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Updated workflow object

        Example:
            >>> workflow = await client.activate_workflow("wf-abc123")
            >>> assert workflow['active'] is True
        """
        return await self.update_workflow(workflow_id, active=True)

    async def deactivate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Deactivate a workflow.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Updated workflow object

        Example:
            >>> workflow = await client.deactivate_workflow("wf-abc123")
            >>> assert workflow['active'] is False
        """
        return await self.update_workflow(workflow_id, active=False)

    # ========================================================================
    # WORKFLOW EXECUTION
    # ========================================================================

    async def execute_workflow(self, workflow_id: str, data: dict[str, Any] | None = None) -> str:
        """Execute a workflow with custom input data.

        Use Case: Agent triggers alert workflow with deployment details.

        Args:
            workflow_id: n8n workflow ID
            data: Input data for the workflow (accessible in nodes)

        Returns:
            Execution ID (for monitoring)

        Raises:
            N8nNotFoundError: If workflow doesn't exist

        Example:
            >>> execution_id = await client.execute_workflow(
            ...     workflow_id="wf-alert-123",
            ...     data={
            ...         "alert": {
            ...             "severity": "critical",
            ...             "title": "Deployment Failed",
            ...             "deployment_id": "deploy-456"
            ...         }
            ...     }
            ... )
            >>> print(f"Workflow execution started: {execution_id}")
        """
        result = await self._api_request(
            method="POST",
            endpoint=f"/workflows/{workflow_id}/execute",
            json_data={"data": data or {}},
        )
        return result["data"]["executionId"]

    async def get_execution_status(self, execution_id: str) -> dict[str, Any]:
        """Get execution status and results.

        Args:
            execution_id: n8n execution ID

        Returns:
            Execution object with:
            - finished: bool (True if complete)
            - mode: "manual" or "trigger"
            - data: Execution result data
            - startedAt: ISO timestamp
            - stoppedAt: ISO timestamp (if finished)
            - status: "success", "error", "running"

        Raises:
            N8nNotFoundError: If execution doesn't exist

        Example:
            >>> execution = await client.get_execution_status("exec-abc123")
            >>> if execution['finished']:
            ...     print(f"Status: {execution.get('status', 'unknown')}")
            ...     print(f"Duration: {execution['stoppedAt']} - {execution['startedAt']}")
        """
        return await self._api_request(method="GET", endpoint=f"/executions/{execution_id}")

    async def get_recent_executions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent workflow executions.

        Use Case: Agent audits automation health.

        Args:
            limit: Max results (default: 20, max: 100)

        Returns:
            List of execution objects

        Example:
            >>> executions = await client.get_recent_executions(limit=10)
            >>> for exec in executions:
            ...     print(f"{exec['workflowName']}: {exec.get('status', 'unknown')}")
        """
        result = await self._api_request(
            method="GET", endpoint="/executions", params={"limit": min(limit, 100)}
        )
        return result.get("data", [])

    # ========================================================================
    # WORKFLOW IMPORT/EXPORT
    # ========================================================================

    async def export_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Export workflow as JSON (for version control).

        Use Case: Agent backs up critical workflows to GitHub repo.

        Args:
            workflow_id: n8n workflow ID

        Returns:
            Complete workflow definition (can be re-imported)

        Raises:
            N8nNotFoundError: If workflow doesn't exist

        Example:
            >>> workflow_json = await client.export_workflow("wf-abc123")
            >>> # Save to file or GitHub
            >>> with open("workflow.json", "w") as f:
            ...     json.dump(workflow_json, f, indent=2)
        """
        return await self.get_workflow(workflow_id)

    async def import_workflow(
        self, workflow_data: dict[str, Any], activate: bool = False
    ) -> dict[str, Any]:
        """Import workflow from JSON definition.

        Use Case: Agent restores workflow from GitHub backup.

        Args:
            workflow_data: Complete workflow definition (from export_workflow)
            activate: Whether to activate after import (default: False)

        Returns:
            Created workflow object with new ID

        Raises:
            N8nValidationError: If workflow structure is invalid

        Example:
            >>> with open("workflow.json") as f:
            ...     workflow_data = json.load(f)
            >>> imported = await client.import_workflow(workflow_data, activate=True)
            >>> print(f"Imported workflow ID: {imported['id']}")
        """
        # Remove ID and timestamps from imported data
        workflow_copy = workflow_data.copy()
        workflow_copy.pop("id", None)
        workflow_copy.pop("createdAt", None)
        workflow_copy.pop("updatedAt", None)

        # Set activation status
        workflow_copy["active"] = activate

        return await self._api_request(
            method="POST", endpoint="/workflows", json_data=workflow_copy
        )
