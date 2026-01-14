"""
n8n tools for MCP Gateway.

Provides autonomous n8n workflow operations:
- Trigger workflows via webhooks
- List available workflows
- Check workflow status
"""

from typing import Any

import httpx

from ..config import get_config

# Workflow webhook mappings
# These map workflow names to their webhook paths
WORKFLOW_REGISTRY = {
    "health-monitor": {
        "path": "/webhook/health-check",
        "method": "GET",
        "description": "Check production health status"
    },
    "deploy-railway": {
        "path": "/webhook/deploy-railway",
        "method": "POST",
        "description": "Trigger Railway deployment on push to main"
    },
    "rollback-railway": {
        "path": "/webhook/rollback-railway",
        "method": "POST",
        "description": "Rollback to previous successful deployment"
    },
    # Week 2: Cost Monitoring Workflows
    "cost-alert": {
        "path": "/webhook/cost-alert",
        "method": "POST",
        "description": "Send cost alert notification to Telegram (critical/warning/info)"
    },
    "cost-weekly-report": {
        "path": "/webhook/cost-weekly-report",
        "method": "POST",
        "description": "Weekly cost summary report to Telegram"
    }
}


async def trigger_workflow(
    workflow_name: str,
    data: dict | None = None
) -> dict[str, Any]:
    """
    Trigger an n8n workflow via webhook.

    Args:
        workflow_name: Name of the workflow to trigger (e.g., 'deploy-railway').
        data: Optional JSON data to pass to the workflow.

    Returns:
        Dictionary with:
        - status: "triggered" or "error"
        - workflow: Workflow name
        - response: Workflow response data
        - http_status: HTTP response status code
        - message: Error message if failed
    """
    config = get_config()

    if not config.n8n_base_url:
        return {
            "status": "error",
            "message": "N8N_BASE_URL not configured"
        }

    if workflow_name not in WORKFLOW_REGISTRY:
        return {
            "status": "error",
            "message": f"Unknown workflow: {workflow_name}",
            "available_workflows": list(WORKFLOW_REGISTRY.keys())
        }

    workflow = WORKFLOW_REGISTRY[workflow_name]
    url = f"{config.n8n_base_url}{workflow['path']}"
    method = workflow.get("method", "POST")

    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, timeout=30.0)
            else:
                response = await client.post(
                    url,
                    json=data or {},
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )

        # Try to parse JSON response
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"raw": response.text}

        return {
            "status": "triggered",
            "workflow": workflow_name,
            "response": response_data,
            "http_status": response.status_code
        }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "workflow": workflow_name,
            "message": "Workflow timed out (>30s). Check n8n execution logs."
        }
    except httpx.HTTPError as e:
        return {
            "status": "error",
            "workflow": workflow_name,
            "message": f"HTTP error: {str(e)}"
        }


async def list_workflows() -> dict[str, Any]:
    """
    List all available n8n workflows.

    Returns:
        Dictionary with:
        - status: "success"
        - workflows: List of workflow info (name, webhook_url, description)
        - count: Number of workflows
    """
    config = get_config()
    base_url = config.n8n_base_url or "<N8N_BASE_URL not configured>"

    workflows = []
    for name, info in WORKFLOW_REGISTRY.items():
        workflows.append({
            "name": name,
            "webhook_url": f"{base_url}{info['path']}",
            "method": info.get("method", "POST"),
            "description": info.get("description", "")
        })

    return {
        "status": "success",
        "workflows": workflows,
        "count": len(workflows)
    }


async def get_workflow_status(workflow_name: str) -> dict[str, Any]:
    """
    Check if a workflow webhook is accessible.

    Args:
        workflow_name: Name of the workflow to check.

    Returns:
        Dictionary with:
        - status: "available", "unavailable", or "error"
        - workflow: Workflow name
        - message: Status message
    """
    config = get_config()

    if not config.n8n_base_url:
        return {
            "status": "error",
            "message": "N8N_BASE_URL not configured"
        }

    if workflow_name not in WORKFLOW_REGISTRY:
        return {
            "status": "error",
            "message": f"Unknown workflow: {workflow_name}"
        }

    workflow = WORKFLOW_REGISTRY[workflow_name]
    url = f"{config.n8n_base_url}{workflow['path']}"

    try:
        async with httpx.AsyncClient() as client:
            # Use OPTIONS to check if endpoint exists without triggering
            response = await client.options(url, timeout=10.0)

        if response.status_code < 500:
            return {
                "status": "available",
                "workflow": workflow_name,
                "url": url,
                "message": "Webhook endpoint is accessible"
            }
        else:
            return {
                "status": "unavailable",
                "workflow": workflow_name,
                "message": f"Server error: {response.status_code}"
            }

    except httpx.HTTPError as e:
        return {
            "status": "unavailable",
            "workflow": workflow_name,
            "message": f"Connection error: {str(e)}"
        }


def register_workflow(
    name: str,
    path: str,
    method: str = "POST",
    description: str = ""
) -> None:
    """
    Register a new workflow in the registry.

    Args:
        name: Workflow name (used to trigger it).
        path: Webhook path (e.g., '/webhook/my-workflow').
        method: HTTP method (GET or POST).
        description: Human-readable description.
    """
    WORKFLOW_REGISTRY[name] = {
        "path": path,
        "method": method,
        "description": description
    }
