"""
Railway tools for MCP Gateway.

Provides autonomous Railway operations:
- Trigger deployments
- Check deployment status
- Execute rollbacks
- Fetch deployment history
"""

from typing import Any, Optional
import httpx

from ..config import get_config

RAILWAY_GRAPHQL_API = "https://backboard.railway.app/graphql/v2"


async def _graphql_request(query: str, variables: dict = None) -> dict:
    """
    Execute a GraphQL request to Railway API.

    Args:
        query: GraphQL query or mutation string.
        variables: Optional variables for the query.

    Returns:
        Response data dictionary.

    Raises:
        httpx.HTTPError: If request fails.
    """
    config = get_config()

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient() as client:
        response = await client.post(
            RAILWAY_GRAPHQL_API,
            json=payload,
            headers={
                "Authorization": f"Bearer {config.railway_token}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()


async def trigger_deployment(service_id: Optional[str] = None) -> dict[str, Any]:
    """
    Trigger a new Railway deployment.

    Args:
        service_id: Railway service ID. Uses default from config if not provided.

    Returns:
        Dictionary with deployment status:
        - status: "triggered" or "error"
        - service_id: The service being deployed
        - environment_id: The target environment
        - message: Status message or error details
    """
    config = get_config()
    service_id = service_id or config.railway_service_id
    environment_id = config.railway_environment_id

    if not service_id:
        return {
            "status": "error",
            "message": "No service_id configured. Set RAILWAY_SERVICE_ID environment variable."
        }

    query = """
    mutation ServiceInstanceRedeploy($serviceId: String!, $environmentId: String!) {
        serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
    }
    """

    try:
        data = await _graphql_request(query, {
            "serviceId": service_id,
            "environmentId": environment_id
        })

        if "errors" in data:
            return {
                "status": "error",
                "message": data["errors"][0]["message"]
            }

        return {
            "status": "triggered",
            "service_id": service_id,
            "environment_id": environment_id,
            "message": "Deployment triggered successfully. Check status in ~60 seconds."
        }

    except httpx.HTTPError as e:
        return {
            "status": "error",
            "message": f"HTTP error: {str(e)}"
        }


async def get_deployment_status(service_id: Optional[str] = None) -> dict[str, Any]:
    """
    Get current Railway deployment status.

    Args:
        service_id: Railway service ID. Uses default from config if not provided.

    Returns:
        Dictionary with:
        - status: "success" or "error"
        - current: Current deployment info (id, status, createdAt)
        - message: Error message if failed
    """
    config = get_config()
    service_id = service_id or config.railway_service_id
    environment_id = config.railway_environment_id

    if not service_id:
        return {
            "status": "error",
            "message": "No service_id configured."
        }

    query = """
    query GetDeployments($serviceId: String!, $environmentId: String!) {
        deployments(first: 1, input: {
            serviceId: $serviceId
            environmentId: $environmentId
        }) {
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

    try:
        data = await _graphql_request(query, {
            "serviceId": service_id,
            "environmentId": environment_id
        })

        if "errors" in data:
            return {
                "status": "error",
                "message": data["errors"][0]["message"]
            }

        edges = data.get("data", {}).get("deployments", {}).get("edges", [])

        if not edges:
            return {
                "status": "success",
                "current": None,
                "message": "No deployments found"
            }

        return {
            "status": "success",
            "current": edges[0]["node"],
            "service_id": service_id
        }

    except httpx.HTTPError as e:
        return {
            "status": "error",
            "message": f"HTTP error: {str(e)}"
        }


async def get_recent_deployments(
    count: int = 5,
    service_id: Optional[str] = None
) -> dict[str, Any]:
    """
    Get recent Railway deployments.

    Args:
        count: Number of deployments to fetch (default: 5).
        service_id: Railway service ID. Uses default from config if not provided.

    Returns:
        Dictionary with:
        - status: "success" or "error"
        - deployments: List of deployment info
        - message: Error message if failed
    """
    config = get_config()
    service_id = service_id or config.railway_service_id
    environment_id = config.railway_environment_id

    if not service_id:
        return {
            "status": "error",
            "message": "No service_id configured."
        }

    query = """
    query GetDeployments($first: Int!, $serviceId: String!, $environmentId: String!) {
        deployments(first: $first, input: {
            serviceId: $serviceId
            environmentId: $environmentId
        }) {
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

    try:
        data = await _graphql_request(query, {
            "first": count,
            "serviceId": service_id,
            "environmentId": environment_id
        })

        if "errors" in data:
            return {
                "status": "error",
                "message": data["errors"][0]["message"]
            }

        edges = data.get("data", {}).get("deployments", {}).get("edges", [])
        deployments = [edge["node"] for edge in edges]

        return {
            "status": "success",
            "deployments": deployments,
            "count": len(deployments)
        }

    except httpx.HTTPError as e:
        return {
            "status": "error",
            "message": f"HTTP error: {str(e)}"
        }


async def execute_rollback(deployment_id: Optional[str] = None) -> dict[str, Any]:
    """
    Execute rollback to a previous successful deployment.

    Args:
        deployment_id: Target deployment ID. If not provided, finds the last
                       successful deployment automatically.

    Returns:
        Dictionary with:
        - status: "rollback_initiated" or "error"
        - deployment_id: New deployment ID
        - target_deployment: The deployment we rolled back to
        - message: Error message if failed
    """
    config = get_config()

    # If no deployment_id specified, find last successful
    if not deployment_id:
        recent = await get_recent_deployments(count=10)

        if recent["status"] == "error":
            return recent

        # Find first SUCCESS deployment after the current one
        deployments = recent.get("deployments", [])
        for deployment in deployments[1:]:  # Skip current
            if deployment.get("status") == "SUCCESS":
                deployment_id = deployment["id"]
                break

        if not deployment_id:
            return {
                "status": "error",
                "message": "No successful deployment found for rollback"
            }

    query = """
    mutation DeploymentRollback($id: String!) {
        deploymentRollback(id: $id) {
            id
            status
        }
    }
    """

    try:
        data = await _graphql_request(query, {"id": deployment_id})

        if "errors" in data:
            return {
                "status": "error",
                "message": data["errors"][0]["message"]
            }

        rollback_data = data.get("data", {}).get("deploymentRollback", {})

        return {
            "status": "rollback_initiated",
            "deployment_id": rollback_data.get("id"),
            "target_deployment": deployment_id,
            "message": "Rollback initiated. Check health in ~30 seconds."
        }

    except httpx.HTTPError as e:
        return {
            "status": "error",
            "message": f"HTTP error: {str(e)}"
        }
