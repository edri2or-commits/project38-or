"""
MCP Gateway Server.

This module provides the FastMCP server with tools for autonomous
Railway and n8n operations.

Usage:
    Standalone:
        python -m src.mcp_gateway.server

    With FastAPI (mount):
        from src.mcp_gateway.server import create_mcp_app
        app.mount("/mcp", create_mcp_app())
"""

import os
from typing import Any

# Check if fastmcp is available
try:
    from fastmcp import FastMCP

    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    FastMCP = None


def create_mcp_server() -> Any | None:
    """
    Create and configure the FastMCP server.

    Returns:
        FastMCP server instance, or None if fastmcp is not installed.
    """
    if not FASTMCP_AVAILABLE:
        return None

    mcp = FastMCP(
        "Claude Gateway", description="MCP Gateway for Railway and n8n autonomous operations"
    )

    # Register Railway tools
    @mcp.tool
    async def railway_deploy(service_id: str = "") -> dict:
        """
        Trigger a new deployment on Railway.

        Args:
            service_id: Railway service ID (optional, uses default if empty)

        Returns:
            Deployment status and ID
        """
        from .tools.railway import trigger_deployment

        return await trigger_deployment(service_id if service_id else None)

    @mcp.tool
    async def railway_status() -> dict:
        """
        Get current Railway deployment status.

        Returns:
            Current deployment status with ID, status, and timestamp
        """
        from .tools.railway import get_deployment_status

        return await get_deployment_status()

    @mcp.tool
    async def railway_deployments(count: int = 5) -> dict:
        """
        Get recent Railway deployments.

        Args:
            count: Number of deployments to fetch (default: 5)

        Returns:
            List of recent deployments
        """
        from .tools.railway import get_recent_deployments

        return await get_recent_deployments(count)

    @mcp.tool
    async def railway_rollback(deployment_id: str = "") -> dict:
        """
        Rollback to a previous successful deployment.

        Args:
            deployment_id: Target deployment ID (optional, finds last successful if empty)

        Returns:
            Rollback status and new deployment ID
        """
        from .tools.railway import execute_rollback

        return await execute_rollback(deployment_id if deployment_id else None)

    # Register n8n tools
    @mcp.tool
    async def n8n_trigger(workflow_name: str, data: str = "{}") -> dict:
        """
        Trigger an n8n workflow.

        Args:
            workflow_name: Name of workflow (e.g., 'deploy-railway', 'health-monitor')
            data: JSON string of data to pass to workflow (default: empty object)

        Returns:
            Workflow execution result
        """
        import json

        from .tools.n8n import trigger_workflow

        try:
            parsed_data = json.loads(data) if data else {}
        except json.JSONDecodeError:
            return {"status": "error", "message": f"Invalid JSON: {data}"}

        return await trigger_workflow(workflow_name, parsed_data)

    @mcp.tool
    async def n8n_list() -> dict:
        """
        List all available n8n workflows.

        Returns:
            List of workflow names and their webhook URLs
        """
        from .tools.n8n import list_workflows

        return await list_workflows()

    @mcp.tool
    async def n8n_status(workflow_name: str) -> dict:
        """
        Check if an n8n workflow webhook is accessible.

        Args:
            workflow_name: Name of workflow to check

        Returns:
            Workflow availability status
        """
        from .tools.n8n import get_workflow_status

        return await get_workflow_status(workflow_name)

    # Register monitoring tools
    @mcp.tool
    async def health_check() -> dict:
        """
        Check health of all services.

        Returns:
            Health status of Railway, n8n, production app, and MCP gateway
        """
        from .tools.monitoring import check_health

        return await check_health()

    @mcp.tool
    async def get_metrics() -> dict:
        """
        Get current system metrics.

        Returns:
            System metrics from production app
        """
        from .tools.monitoring import get_metrics

        return await get_metrics()

    @mcp.tool
    async def deployment_health() -> dict:
        """
        Comprehensive deployment health check with recommendations.

        Returns:
            Combined health + deployment status with action recommendations
        """
        from .tools.monitoring import check_deployment_health

        return await check_deployment_health()

    # Register OAuth tools
    @mcp.tool
    async def workspace_oauth_exchange(auth_code: str) -> dict:
        """
        Exchange OAuth authorization code for refresh token.

        Gets Client ID and Secret from GCP Secret Manager,
        exchanges the code, and stores the refresh token.

        Args:
            auth_code: The authorization code from Google OAuth

        Returns:
            Success status and any error messages
        """
        from .tools.oauth import exchange_oauth_code

        return await exchange_oauth_code(auth_code)

    @mcp.tool
    async def workspace_oauth_status() -> dict:
        """
        Check Google Workspace OAuth configuration status.

        Returns:
            Which OAuth secrets are configured in Secret Manager
        """
        from .tools.oauth import check_oauth_status

        return await check_oauth_status()

    return mcp


def create_mcp_app() -> object | None:
    """
    Create ASGI app for mounting in FastAPI.

    Returns:
        ASGI application, or None if fastmcp not available.

    Example:
        >>> from fastapi import FastAPI
        >>> from src.mcp_gateway.server import create_mcp_app
        >>> app = FastAPI()
        >>> mcp_app = create_mcp_app()
        >>> if mcp_app:
        ...     app.mount("/mcp", mcp_app)
    """
    mcp = create_mcp_server()
    if mcp is None:
        return None

    return mcp.http_app()


# Module-level server instance for standalone use
mcp = create_mcp_server()


if __name__ == "__main__":
    if mcp is None:
        print("Error: fastmcp not installed. Run: pip install fastmcp")
        exit(1)

    port = int(os.environ.get("MCP_PORT", "8080"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")

    print(f"Starting MCP Gateway on {host}:{port}")
    print("Available tools:")
    print("  - railway_deploy: Trigger deployment")
    print("  - railway_status: Get deployment status")
    print("  - railway_rollback: Rollback deployment")
    print("  - n8n_trigger: Trigger workflow")
    print("  - n8n_list: List workflows")
    print("  - health_check: Check all services")
    print("  - get_metrics: Get system metrics")

    mcp.run(transport="streamable-http", host=host, port=port)
