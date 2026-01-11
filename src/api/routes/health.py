"""Health check endpoint for monitoring API availability.

This module provides endpoints for health checks and system status.
"""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


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
    # TODO: Add database connection check
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="0.1.0",
        database="not_connected",  # Will be updated after database integration
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
        "health": "/health",
    }

