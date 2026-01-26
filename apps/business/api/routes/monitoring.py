"""Monitoring API endpoints for system health and anomaly detection.

This module provides endpoints to:
- Start/stop/pause the monitoring loop
- View monitoring statistics and recent metrics
- Configure monitoring behavior
- Check anomaly detection status
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from apps.business.core.monitoring_loop import (
    MetricsEndpoint,
    MonitoringLoop,
    MonitoringState,
    create_railway_monitoring_loop,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Global monitoring loop instance
_monitoring_loop: MonitoringLoop | None = None


class MonitoringConfigRequest(BaseModel):
    """Request model for monitoring configuration."""

    collection_interval: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Interval between metric collections (seconds)",
    )
    anomaly_detection_enabled: bool = Field(
        default=True,
        description="Enable ML-based anomaly detection",
    )
    self_healing_enabled: bool = Field(
        default=True,
        description="Enable automatic self-healing responses",
    )
    max_consecutive_errors: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max errors before pausing",
    )


class EndpointRequest(BaseModel):
    """Request model for adding an endpoint."""

    url: str = Field(..., description="Endpoint URL to monitor")
    name: str = Field(..., description="Unique name for the endpoint")
    timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Request timeout in seconds",
    )
    enabled: bool = Field(default=True, description="Whether endpoint is enabled")


class MonitoringStatus(BaseModel):
    """Response model for monitoring status."""

    state: str
    is_running: bool
    endpoints_count: int
    enabled_endpoints: int
    collections_total: int
    collections_successful: int
    collections_failed: int
    anomalies_detected: int
    healing_actions_triggered: int
    last_collection_time: str | None
    last_anomaly_time: str | None


def get_monitoring_loop() -> MonitoringLoop:
    """Get or create the global monitoring loop instance."""
    global _monitoring_loop
    if _monitoring_loop is None:
        _monitoring_loop = create_railway_monitoring_loop()
    return _monitoring_loop


@router.get("/api/monitoring/status", response_model=MonitoringStatus)
async def get_monitoring_status() -> MonitoringStatus:
    """
    Get current monitoring loop status and statistics.

    Returns the current state of the monitoring system including
    collection statistics and anomaly detection metrics.
    """
    loop = get_monitoring_loop()
    stats = loop.get_stats()

    return MonitoringStatus(
        state=stats["state"],
        is_running=loop.is_running,
        endpoints_count=stats["endpoints_count"],
        enabled_endpoints=stats["enabled_endpoints"],
        collections_total=stats["collections_total"],
        collections_successful=stats["collections_successful"],
        collections_failed=stats["collections_failed"],
        anomalies_detected=stats["anomalies_detected"],
        healing_actions_triggered=stats["healing_actions_triggered"],
        last_collection_time=stats["last_collection_time"],
        last_anomaly_time=stats["last_anomaly_time"],
    )


@router.post("/api/monitoring/start")
async def start_monitoring(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """
    Start the monitoring loop.

    Begins continuous metric collection and anomaly detection
    in the background.
    """
    loop = get_monitoring_loop()

    if loop.state == MonitoringState.RUNNING:
        return {
            "status": "already_running",
            "message": "Monitoring loop is already running",
        }

    background_tasks.add_task(loop.start)

    logger.info("Monitoring loop start requested")
    return {
        "status": "starting",
        "message": "Monitoring loop is starting",
        "collection_interval": loop.config.collection_interval,
    }


@router.post("/api/monitoring/stop")
async def stop_monitoring() -> dict[str, Any]:
    """
    Stop the monitoring loop.

    Gracefully stops metric collection and anomaly detection.
    """
    loop = get_monitoring_loop()

    if loop.state == MonitoringState.STOPPED:
        return {
            "status": "already_stopped",
            "message": "Monitoring loop is already stopped",
        }

    await loop.stop()

    logger.info("Monitoring loop stopped")
    return {
        "status": "stopped",
        "message": "Monitoring loop has been stopped",
    }


@router.post("/api/monitoring/pause")
async def pause_monitoring() -> dict[str, Any]:
    """
    Pause the monitoring loop.

    Temporarily suspends metric collection without stopping the loop.
    """
    loop = get_monitoring_loop()

    if loop.state != MonitoringState.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause: monitoring is {loop.state.value}",
        )

    await loop.pause()

    return {
        "status": "paused",
        "message": "Monitoring loop has been paused",
    }


@router.post("/api/monitoring/resume")
async def resume_monitoring() -> dict[str, Any]:
    """
    Resume the monitoring loop.

    Resumes metric collection after being paused.
    """
    loop = get_monitoring_loop()

    if loop.state != MonitoringState.PAUSED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume: monitoring is {loop.state.value}",
        )

    await loop.resume()

    return {
        "status": "running",
        "message": "Monitoring loop has been resumed",
    }


@router.get("/api/monitoring/metrics/recent")
async def get_recent_metrics(limit: int = 10) -> dict[str, Any]:
    """
    Get recent collected metrics.

    Args:
        limit: Maximum number of recent metrics to return (1-100)

    Returns metrics history for analysis and debugging.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    loop = get_monitoring_loop()
    recent = loop.get_recent_metrics(limit)

    return {
        "count": len(recent),
        "metrics": recent,
    }


@router.get("/api/monitoring/endpoints")
async def list_endpoints() -> dict[str, Any]:
    """
    List all configured monitoring endpoints.

    Returns the list of endpoints being monitored
    with their current configuration.
    """
    loop = get_monitoring_loop()

    endpoints = [
        {
            "name": ep.name,
            "url": ep.url,
            "timeout": ep.timeout,
            "enabled": ep.enabled,
        }
        for ep in loop.collector.endpoints
    ]

    return {
        "count": len(endpoints),
        "endpoints": endpoints,
    }


@router.post("/api/monitoring/endpoints")
async def add_endpoint(request: EndpointRequest) -> dict[str, Any]:
    """
    Add a new monitoring endpoint.

    Args:
        request: Endpoint configuration

    Adds a new endpoint to the monitoring rotation.
    """
    loop = get_monitoring_loop()

    # Check for duplicate name
    existing_names = [ep.name for ep in loop.collector.endpoints]
    if request.name in existing_names:
        raise HTTPException(
            status_code=400,
            detail=f"Endpoint with name '{request.name}' already exists",
        )

    endpoint = MetricsEndpoint(
        url=request.url,
        name=request.name,
        timeout=request.timeout,
        enabled=request.enabled,
    )

    loop.collector.add_endpoint(endpoint)
    logger.info(f"Added monitoring endpoint: {request.name}")

    return {
        "status": "added",
        "endpoint": {
            "name": endpoint.name,
            "url": endpoint.url,
            "timeout": endpoint.timeout,
            "enabled": endpoint.enabled,
        },
    }


@router.delete("/api/monitoring/endpoints/{name}")
async def remove_endpoint(name: str) -> dict[str, Any]:
    """
    Remove a monitoring endpoint.

    Args:
        name: Name of the endpoint to remove
    """
    loop = get_monitoring_loop()

    if not loop.collector.remove_endpoint(name):
        raise HTTPException(
            status_code=404,
            detail=f"Endpoint '{name}' not found",
        )

    logger.info(f"Removed monitoring endpoint: {name}")
    return {
        "status": "removed",
        "name": name,
    }


@router.put("/api/monitoring/config")
async def update_config(request: MonitoringConfigRequest) -> dict[str, Any]:
    """
    Update monitoring configuration.

    Args:
        request: New configuration values

    Updates the monitoring loop configuration.
    Note: Some changes may require a restart to take effect.
    """
    loop = get_monitoring_loop()

    loop.config.collection_interval = request.collection_interval
    loop.config.anomaly_detection_enabled = request.anomaly_detection_enabled
    loop.config.self_healing_enabled = request.self_healing_enabled
    loop.config.max_consecutive_errors = request.max_consecutive_errors

    logger.info(f"Updated monitoring config: interval={request.collection_interval}s")

    return {
        "status": "updated",
        "config": {
            "collection_interval": loop.config.collection_interval,
            "anomaly_detection_enabled": loop.config.anomaly_detection_enabled,
            "self_healing_enabled": loop.config.self_healing_enabled,
            "max_consecutive_errors": loop.config.max_consecutive_errors,
        },
    }


@router.get("/api/monitoring/config")
async def get_config() -> dict[str, Any]:
    """
    Get current monitoring configuration.

    Returns the current configuration settings
    for the monitoring loop.
    """
    loop = get_monitoring_loop()

    return {
        "collection_interval": loop.config.collection_interval,
        "min_interval": loop.config.min_interval,
        "anomaly_detection_enabled": loop.config.anomaly_detection_enabled,
        "self_healing_enabled": loop.config.self_healing_enabled,
        "max_consecutive_errors": loop.config.max_consecutive_errors,
        "error_pause_duration": loop.config.error_pause_duration,
        "history_size": loop.config.history_size,
    }


@router.post("/api/monitoring/collect-now")
async def collect_now() -> dict[str, Any]:
    """
    Trigger an immediate metric collection.

    Performs a single collection cycle immediately,
    regardless of the scheduled interval.
    """
    loop = get_monitoring_loop()

    collected = await loop.collector.collect_all()

    results = [
        {
            "endpoint": m.endpoint_name,
            "latency_ms": m.latency_ms,
            "is_healthy": m.is_healthy,
            "metrics": m.metrics,
            "error": m.error,
        }
        for m in collected
    ]

    return {
        "status": "collected",
        "count": len(results),
        "results": results,
    }
