"""
Monitoring tools for MCP Gateway.

Provides health checks and metrics:
- Check all service health
- Get system metrics
"""

from typing import Any
import httpx

from ..config import get_config


async def check_health() -> dict[str, Any]:
    """
    Check health of all services.

    Checks:
    - Production app (or-infra.com/api/health)
    - Railway deployment status
    - n8n availability (if configured)
    - MCP Gateway itself

    Returns:
        Dictionary with:
        - status: "healthy", "degraded", or "unhealthy"
        - services: Individual service status
        - timestamp: Check timestamp
    """
    config = get_config()

    services = {}
    overall_healthy = True
    overall_degraded = False

    # Check production app
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.production_url}/api/health",
                timeout=10.0
            )

        if response.status_code == 200:
            health_data = response.json()
            services["production"] = {
                "status": health_data.get("status", "unknown"),
                "url": config.production_url,
                "database": health_data.get("database", "unknown"),
                "version": health_data.get("version", "unknown")
            }
        else:
            services["production"] = {
                "status": "unhealthy",
                "http_status": response.status_code
            }
            overall_healthy = False

    except httpx.HTTPError as e:
        services["production"] = {
            "status": "unreachable",
            "error": str(e)
        }
        overall_healthy = False

    # Check Railway (via GraphQL API accessibility)
    if config.railway_token:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://backboard.railway.app/graphql/v2",
                    json={"query": "{ me { name } }"},
                    headers={
                        "Authorization": f"Bearer {config.railway_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

            if response.status_code == 200:
                services["railway_api"] = {
                    "status": "connected",
                    "project_id": config.railway_project_id
                }
            else:
                services["railway_api"] = {
                    "status": "error",
                    "http_status": response.status_code
                }
                overall_degraded = True

        except httpx.HTTPError as e:
            services["railway_api"] = {
                "status": "unreachable",
                "error": str(e)
            }
            overall_degraded = True
    else:
        services["railway_api"] = {
            "status": "not_configured",
            "message": "RAILWAY-API token not set"
        }
        overall_degraded = True

    # Check n8n (if configured)
    if config.n8n_base_url:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    config.n8n_base_url,
                    timeout=10.0
                )

            services["n8n"] = {
                "status": "available" if response.status_code < 500 else "error",
                "url": config.n8n_base_url
            }

        except httpx.HTTPError as e:
            services["n8n"] = {
                "status": "unreachable",
                "error": str(e)
            }
            overall_degraded = True
    else:
        services["n8n"] = {
            "status": "not_configured",
            "message": "N8N_BASE_URL not set"
        }

    # MCP Gateway is running (since we're here)
    services["mcp_gateway"] = {
        "status": "running",
        "version": "0.1.0"
    }

    # Determine overall status
    if not overall_healthy:
        overall_status = "unhealthy"
    elif overall_degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    from datetime import datetime, timezone
    return {
        "status": overall_status,
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def get_metrics() -> dict[str, Any]:
    """
    Get system metrics.

    Returns metrics from production app if available,
    otherwise returns MCP Gateway metrics.

    Returns:
        Dictionary with:
        - status: "success" or "error"
        - metrics: System metrics data
        - source: Where metrics came from
    """
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.production_url}/metrics/summary",
                timeout=10.0
            )

        if response.status_code == 200:
            return {
                "status": "success",
                "metrics": response.json(),
                "source": "production_app"
            }
        else:
            return {
                "status": "error",
                "message": f"Metrics endpoint returned {response.status_code}",
                "source": "production_app"
            }

    except httpx.HTTPError as e:
        # Return basic MCP Gateway metrics as fallback
        return {
            "status": "partial",
            "message": f"Production metrics unavailable: {str(e)}",
            "metrics": {
                "mcp_gateway": {
                    "status": "running",
                    "version": "0.1.0"
                }
            },
            "source": "mcp_gateway"
        }


async def check_deployment_health() -> dict[str, Any]:
    """
    Comprehensive deployment health check.

    Combines health check with deployment status to provide
    a complete picture of production state.

    Returns:
        Dictionary with health, deployment, and recommendation
    """
    from .railway import get_deployment_status

    # Get both health and deployment status
    health = await check_health()
    deployment = await get_deployment_status()

    # Analyze and provide recommendation
    recommendation = None

    if health["status"] == "unhealthy":
        if deployment.get("status") == "success":
            current = deployment.get("current", {})
            if current.get("status") == "SUCCESS":
                recommendation = "Production unhealthy but deployment succeeded. Check application logs."
            elif current.get("status") in ["DEPLOYING", "BUILDING"]:
                recommendation = "Deployment in progress. Wait for completion."
            else:
                recommendation = f"Deployment status: {current.get('status')}. Consider rollback."
        else:
            recommendation = "Both health check and deployment status unavailable. Manual investigation required."

    elif health["status"] == "degraded":
        recommendation = "Some services degraded. Monitor closely."

    return {
        "health": health,
        "deployment": deployment,
        "recommendation": recommendation,
        "action_required": health["status"] != "healthy"
    }
