"""Health check endpoint for monitoring API availability.

This module provides endpoints for health checks and system status.
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.database import check_database_connection

router = APIRouter(prefix="/api")


class HealthResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: Current health status (healthy/degraded/unhealthy)
        timestamp: Current server timestamp
        version: API version
        database: Database connection status
        build: Build marker to verify deployment version
    """

    status: str
    timestamp: datetime
    version: str
    database: str = "not_connected"
    build: str = ""


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns current system health status including database connectivity.

    Returns:
        HealthResponse: System health information

    Example:
        >>> response = await health_check()
        >>> print(response.status)
        healthy
    """
    # Check database connection
    db_status = "connected" if await check_database_connection() else "disconnected"

    # Determine overall health status
    status = "healthy" if db_status == "connected" else "degraded"

    # Build marker to verify deployment version
    # Change this value to verify Railway is deploying new code
    build_marker = "2026-01-24-mcp-debug"

    return HealthResponse(
        status=status,
        timestamp=datetime.now(UTC),
        version="0.1.0",
        database=db_status,
        build=build_marker,
    )


@router.get("/", response_model=dict[str, str])
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns basic API information and documentation links.

    Returns:
        dict: API metadata
    """
    return {
        "name": "Agent Platform API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@router.get("/test/ping")
async def test_ping() -> dict:
    """Test endpoint to verify routes are being registered."""
    return {"status": "pong", "message": "If you see this, routes are working"}


@router.get("/mcp/status")
async def mcp_gateway_status() -> dict:
    """Check MCP Gateway status.

    Returns:
        dict: MCP Gateway status information
    """
    import os

    mcp_enabled_raw = os.getenv("MCP_GATEWAY_ENABLED", "NOT_SET")
    mcp_enabled = mcp_enabled_raw.lower() == "true" if mcp_enabled_raw != "NOT_SET" else False

    # Check if fastmcp is available
    fastmcp_available = False
    try:
        import fastmcp
        fastmcp_available = True
    except ImportError:
        pass

    # Check if MCP app was created
    mcp_app_created = False
    mcp_app_error = None
    if mcp_enabled and fastmcp_available:
        try:
            from src.mcp_gateway.server import create_mcp_app
            app = create_mcp_app()
            mcp_app_created = app is not None
        except Exception as e:
            mcp_app_error = str(e)

    return {
        "mcp_gateway_enabled_raw": mcp_enabled_raw,
        "mcp_gateway_enabled": mcp_enabled,
        "fastmcp_installed": fastmcp_available,
        "mcp_app_created": mcp_app_created,
        "mcp_app_error": mcp_app_error,
        "expected_path": "/mcp" if mcp_enabled and mcp_app_created else None,
    }


@router.get("/relay/status")
async def relay_status() -> dict:
    """Check GitHub MCP Relay status.

    Returns:
        dict: Relay status information
    """
    import os

    from src.api.main import get_github_relay, get_relay_startup_error

    relay = get_github_relay()
    startup_error = get_relay_startup_error()
    relay_enabled = os.getenv("GITHUB_RELAY_ENABLED", "true").lower() == "true"

    if relay is None:
        return {
            "status": "not_started",
            "relay_enabled": relay_enabled,
            "startup_error": startup_error,
            "message": "GitHub relay was not initialized",
            "repo": None,
            "issue": None,
        }

    return {
        "status": "running" if relay._running else "stopped",
        "relay_enabled": relay_enabled,
        "repo": relay.repo,
        "issue": relay.issue_number,
        "processed_requests": len(relay._processed_requests),
        "has_token": relay._github_token is not None,
    }
