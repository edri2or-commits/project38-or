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

    # Note: FastMCP 2.x doesn't support 'description' parameter
    mcp = FastMCP("Claude Gateway")

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

    # =========================================================================
    # Google Workspace Tools (Gmail, Calendar, Drive, Sheets, Docs)
    # =========================================================================

    @mcp.tool
    async def gmail_send(
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict:
        """
        Send an email via Gmail.

        Args:
            to: Recipient email address(es), comma-separated
            subject: Email subject
            body: Email body (plain text)
            cc: CC recipients, comma-separated (optional)
            bcc: BCC recipients, comma-separated (optional)

        Returns:
            Result with message ID and thread ID
        """
        from .tools.workspace import gmail_send

        return await gmail_send(to, subject, body, cc, bcc)

    @mcp.tool
    async def gmail_search(query: str, max_results: int = 10) -> dict:
        """
        Search emails in Gmail.

        Args:
            query: Gmail search query (e.g., "from:user@example.com is:unread")
            max_results: Maximum number of results (default: 10)

        Returns:
            List of matching email summaries
        """
        from .tools.workspace import gmail_search

        return await gmail_search(query, max_results)

    @mcp.tool
    async def gmail_list(label: str = "INBOX", max_results: int = 10) -> dict:
        """
        List recent emails in a label.

        Args:
            label: Gmail label (default: INBOX)
            max_results: Maximum number of results (default: 10)

        Returns:
            List of recent email summaries
        """
        from .tools.workspace import gmail_list

        return await gmail_list(label, max_results)

    @mcp.tool
    async def calendar_list_events(
        calendar_id: str = "primary",
        max_results: int = 10,
        time_min: str = "",
    ) -> dict:
        """
        List upcoming calendar events.

        Args:
            calendar_id: Calendar ID (default: primary)
            max_results: Maximum number of events (default: 10)
            time_min: Start time in ISO format (default: now)

        Returns:
            List of upcoming events
        """
        from .tools.workspace import calendar_list_events

        return await calendar_list_events(calendar_id, max_results, time_min)

    @mcp.tool
    async def calendar_create_event(
        summary: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        description: str = "",
        location: str = "",
        attendees: str = "",
    ) -> dict:
        """
        Create a calendar event.

        Args:
            summary: Event title
            start_time: Start time in ISO format (e.g., 2026-01-20T10:00:00Z)
            end_time: End time in ISO format
            calendar_id: Calendar ID (default: primary)
            description: Event description (optional)
            location: Event location (optional)
            attendees: Comma-separated email addresses (optional)

        Returns:
            Created event details with event ID and link
        """
        from .tools.workspace import calendar_create_event

        return await calendar_create_event(
            summary, start_time, end_time, calendar_id, description, location, attendees
        )

    @mcp.tool
    async def drive_list_files(
        query: str = "",
        max_results: int = 10,
        folder_id: str = "",
    ) -> dict:
        """
        List files in Google Drive.

        Args:
            query: Search query (e.g., "name contains 'report'")
            max_results: Maximum number of results (default: 10)
            folder_id: Specific folder ID to search in (optional)

        Returns:
            List of files with ID, name, type, and link
        """
        from .tools.workspace import drive_list_files

        return await drive_list_files(query, max_results, folder_id)

    @mcp.tool
    async def drive_create_folder(name: str, parent_id: str = "") -> dict:
        """
        Create a folder in Google Drive.

        Args:
            name: Folder name
            parent_id: Parent folder ID (optional)

        Returns:
            Created folder ID and name
        """
        from .tools.workspace import drive_create_folder

        return await drive_create_folder(name, parent_id)

    @mcp.tool
    async def sheets_read(
        spreadsheet_id: str,
        range_notation: str = "Sheet1!A1:Z100",
    ) -> dict:
        """
        Read data from a Google Sheet.

        Args:
            spreadsheet_id: Spreadsheet ID from URL
            range_notation: A1 notation range (e.g., "Sheet1!A1:B10")

        Returns:
            Cell values as 2D array
        """
        from .tools.workspace import sheets_read

        return await sheets_read(spreadsheet_id, range_notation)

    @mcp.tool
    async def sheets_write(
        spreadsheet_id: str,
        range_notation: str,
        values: str,
    ) -> dict:
        """
        Write data to a Google Sheet.

        Args:
            spreadsheet_id: Spreadsheet ID from URL
            range_notation: A1 notation range (e.g., "Sheet1!A1:B2")
            values: JSON string of 2D array (e.g., '[["A1","B1"],["A2","B2"]]')

        Returns:
            Update result with cell count
        """
        import json

        from .tools.workspace import sheets_write

        try:
            parsed_values = json.loads(values)
        except json.JSONDecodeError:
            return {"success": False, "error": f"Invalid JSON: {values}"}

        return await sheets_write(spreadsheet_id, range_notation, parsed_values)

    @mcp.tool
    async def sheets_create(title: str) -> dict:
        """
        Create a new Google Sheet.

        Args:
            title: Spreadsheet title

        Returns:
            Spreadsheet ID and URL
        """
        from .tools.workspace import sheets_create

        return await sheets_create(title)

    @mcp.tool
    async def docs_create(title: str) -> dict:
        """
        Create a new Google Doc.

        Args:
            title: Document title

        Returns:
            Document ID and title
        """
        from .tools.workspace import docs_create

        return await docs_create(title)

    @mcp.tool
    async def docs_read(document_id: str) -> dict:
        """
        Read content from a Google Doc.

        Args:
            document_id: Document ID from URL

        Returns:
            Document title and text content
        """
        from .tools.workspace import docs_read

        return await docs_read(document_id)

    @mcp.tool
    async def docs_append(document_id: str, text: str) -> dict:
        """
        Append text to a Google Doc.

        Args:
            document_id: Document ID from URL
            text: Text to append

        Returns:
            Update result
        """
        from .tools.workspace import docs_append

        return await docs_append(document_id, text)

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
    print("  Railway:")
    print("    - railway_deploy: Trigger deployment")
    print("    - railway_status: Get deployment status")
    print("    - railway_rollback: Rollback deployment")
    print("  n8n:")
    print("    - n8n_trigger: Trigger workflow")
    print("    - n8n_list: List workflows")
    print("  Monitoring:")
    print("    - health_check: Check all services")
    print("    - get_metrics: Get system metrics")
    print("  Google Workspace:")
    print("    - gmail_send, gmail_search, gmail_list")
    print("    - calendar_list_events, calendar_create_event")
    print("    - drive_list_files, drive_create_folder")
    print("    - sheets_read, sheets_write, sheets_create")
    print("    - docs_create, docs_read, docs_append")

    mcp.run(transport="streamable-http", host=host, port=port)
