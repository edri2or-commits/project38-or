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
    """

    status: str
    timestamp: datetime
    version: str
    database: str = "not_connected"


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

    return HealthResponse(
        status=status,
        timestamp=datetime.now(UTC),
        version="0.1.0",
        database=db_status,
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
