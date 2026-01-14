"""
Metrics API Endpoints

Provides real-time metrics for the observability dashboard.
Based on Research Paper #08, Section 5.3 (Dashboard Prototyping).

Phase 1: Basic metrics without SSE streaming.
Phase 2: Add Server-Sent Events (SSE) for real-time updates.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.database import get_session

router = APIRouter(prefix="/metrics", tags=["Metrics"])


# =============================================================================
# Pydantic Models
# =============================================================================


class MetricSummary(BaseModel):
    """Summary statistics for dashboard."""

    active_agents: int = Field(description="Number of agents with recent activity")
    total_requests_1h: int = Field(description="Total requests in last hour")
    error_rate_pct: float = Field(description="Error rate percentage (0-100)")
    avg_latency_ms: float = Field(description="Average latency in milliseconds")
    p95_latency_ms: float = Field(description="P95 latency in milliseconds")
    total_tokens_1h: int = Field(description="Total tokens consumed in last hour")
    estimated_cost_1h: float = Field(description="Estimated cost in USD")


class AgentMetricPoint(BaseModel):
    """Single metric data point."""

    timestamp: datetime
    agent_id: str
    metric_name: str
    value: float
    labels: dict[str, str] = {}


class AgentStatus(BaseModel):
    """Status of a single agent."""

    agent_id: str
    last_seen: datetime
    error_rate_pct: float
    total_requests_1h: int
    avg_latency_ms: float
    total_tokens_1h: int


class SystemMetrics(BaseModel):
    """System resource metrics."""

    timestamp: datetime
    cpu_percent: float = Field(description="CPU usage percentage (0-100)")
    memory_percent: float = Field(description="Memory usage percentage (0-100)")
    memory_available_mb: float = Field(description="Available memory in MB")
    disk_percent: float = Field(description="Disk usage percentage (0-100)")
    disk_available_gb: float = Field(description="Available disk space in GB")


# =============================================================================
# Helper Functions
# =============================================================================


async def get_active_agent_count(conn: AsyncSession) -> int:
    """Count agents active in last hour."""
    result = await conn.execute(
        text(
            """
        SELECT COUNT(DISTINCT agent_id)
        FROM agent_metrics
        WHERE time >= NOW() - INTERVAL '1 hour'
        """
        )
    )
    value = result.scalar_one_or_none()
    return value or 0


async def get_total_requests(conn: AsyncSession, interval: str = "1 hour") -> int:
    """Count total requests (successes + errors)."""
    result = await conn.execute(
        text(
            f"""
        SELECT COALESCE(SUM(value), 0)::INT
        FROM agent_metrics
        WHERE metric_name IN ('success_count', 'error_count')
          AND time >= NOW() - INTERVAL '{interval}'
        """
        )
    )
    value = result.scalar_one_or_none()
    return value or 0


async def get_error_rate(conn: AsyncSession, interval: str = "1 hour") -> float:
    """Calculate global error rate."""
    result = await conn.execute(
        text(
            f"""
        SELECT COALESCE(SUM(value), 0)
        FROM agent_metrics
        WHERE metric_name = 'error_count'
          AND time >= NOW() - INTERVAL '{interval}'
        """
        )
    )
    errors = result.scalar_one_or_none() or 0

    result = await conn.execute(
        text(
            f"""
        SELECT COALESCE(SUM(value), 0)
        FROM agent_metrics
        WHERE metric_name IN ('success_count', 'error_count')
          AND time >= NOW() - INTERVAL '{interval}'
        """
        )
    )
    total = result.scalar_one_or_none() or 0

    if total == 0:
        return 0.0
    return round((errors / total) * 100, 2)


async def get_avg_latency(conn: AsyncSession, interval: str = "1 hour") -> float:
    """Calculate average latency."""
    result = await conn.execute(
        text(
            f"""
        SELECT COALESCE(AVG(value), 0)
        FROM agent_metrics
        WHERE metric_name = 'latency_ms'
          AND time >= NOW() - INTERVAL '{interval}'
        """
        )
    )
    value = result.scalar_one_or_none()
    return round(value or 0, 2)


async def get_p95_latency(conn: AsyncSession, interval: str = "1 hour") -> float:
    """Calculate P95 latency."""
    result = await conn.execute(
        text(
            f"""
        SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value), 0)
        FROM agent_metrics
        WHERE metric_name = 'latency_ms'
          AND time >= NOW() - INTERVAL '{interval}'
        """
        )
    )
    value = result.scalar_one_or_none()
    return round(value or 0, 2)


async def get_total_tokens(conn: AsyncSession, interval: str = "1 hour") -> int:
    """Calculate total token usage."""
    result = await conn.execute(
        text(
            f"""
        SELECT COALESCE(SUM(value), 0)::INT
        FROM agent_metrics
        WHERE metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
          AND time >= NOW() - INTERVAL '{interval}'
        """
        )
    )
    value = result.scalar_one_or_none()
    return value or 0


def estimate_cost(total_tokens: int, model_id: str = "claude-sonnet-4.5") -> float:
    """
    Estimate cost based on token usage.

    Pricing (as of 2026):
    - Claude Sonnet 4.5: $3/MTok input, $15/MTok output
    - Simplified: Assume 50/50 split
    """
    # Simplified calculation: ($3 + $15) / 2 = $9 per MTok average
    avg_price_per_mtok = 9.0
    cost = (total_tokens / 1_000_000) * avg_price_per_mtok
    return round(cost, 4)


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/summary", response_model=MetricSummary)
async def get_metrics_summary(conn: AsyncSession = Depends(get_session)) -> MetricSummary:
    """
    Get summary metrics for the dashboard.

    Returns high-level statistics for the last hour:
    - Active agent count
    - Total requests
    - Error rate
    - Latency metrics (avg, P95)
    - Token usage and estimated cost

    Example:
        GET /metrics/summary

    Returns:
        MetricSummary with all statistics
    """
    active_agents = await get_active_agent_count(conn)
    total_requests = await get_total_requests(conn)
    error_rate = await get_error_rate(conn)
    avg_latency = await get_avg_latency(conn)
    p95_latency = await get_p95_latency(conn)
    total_tokens = await get_total_tokens(conn)
    estimated_cost = estimate_cost(total_tokens)

    return MetricSummary(
        active_agents=active_agents,
        total_requests_1h=total_requests,
        error_rate_pct=error_rate,
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        total_tokens_1h=total_tokens,
        estimated_cost_1h=estimated_cost,
    )


@router.get("/agents", response_model=list[AgentStatus])
async def get_agent_statuses(
    conn: AsyncSession = Depends(get_session),
    limit: int = Query(10, ge=1, le=100, description="Max agents to return"),
) -> list[AgentStatus]:
    """
    Get status of all active agents.

    Returns per-agent statistics including:
    - Last seen timestamp
    - Error rate
    - Request count
    - Average latency
    - Token usage

    Example:
        GET /metrics/agents?limit=10

    Returns:
        List of AgentStatus objects
    """
    # Get list of active agents
    result = await conn.execute(
        text(
            """
        SELECT DISTINCT agent_id, MAX(time) as last_seen
        FROM agent_metrics
        WHERE time >= NOW() - INTERVAL '1 hour'
        GROUP BY agent_id
        ORDER BY last_seen DESC
        LIMIT :limit
        """
        ),
        {"limit": limit},
    )
    agent_ids = result.mappings().all()

    statuses = []
    for row in agent_ids:
        agent_id = row["agent_id"]
        last_seen = row["last_seen"]

        # Get agent-specific metrics
        result = await conn.execute(
            text(
                """
            SELECT get_agent_error_rate(:agent_id, '1 hour')
            """
            ),
            {"agent_id": agent_id},
        )
        error_rate = result.scalar_one_or_none()

        result = await conn.execute(
            text(
                """
            SELECT COALESCE(SUM(value), 0)::INT
            FROM agent_metrics
            WHERE agent_id = :agent_id
              AND metric_name IN ('success_count', 'error_count')
              AND time >= NOW() - INTERVAL '1 hour'
            """
            ),
            {"agent_id": agent_id},
        )
        total_requests = result.scalar_one_or_none()

        result = await conn.execute(
            text(
                """
            SELECT COALESCE(AVG(value), 0)
            FROM agent_metrics
            WHERE agent_id = :agent_id
              AND metric_name = 'latency_ms'
              AND time >= NOW() - INTERVAL '1 hour'
            """
            ),
            {"agent_id": agent_id},
        )
        avg_latency = result.scalar_one_or_none()

        result = await conn.execute(
            text(
                """
            SELECT COALESCE(SUM(value), 0)::INT
            FROM agent_metrics
            WHERE agent_id = :agent_id
              AND metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
              AND time >= NOW() - INTERVAL '1 hour'
            """
            ),
            {"agent_id": agent_id},
        )
        total_tokens = result.scalar_one_or_none()

        statuses.append(
            AgentStatus(
                agent_id=agent_id,
                last_seen=last_seen,
                error_rate_pct=round(error_rate or 0, 2),
                total_requests_1h=total_requests or 0,
                avg_latency_ms=round(avg_latency or 0, 2),
                total_tokens_1h=total_tokens or 0,
            )
        )

    return statuses


@router.get("/timeseries", response_model=list[AgentMetricPoint])
async def get_metric_timeseries(
    metric_name: str = Query(..., description="Metric name (e.g., 'latency_ms')"),
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    interval: str = Query("1 hour", description="Time interval (e.g., '1 hour', '24 hours')"),
    bucket_size: str = Query("5 minutes", description="Bucket size for aggregation"),
    conn: AsyncSession = Depends(get_session),
) -> list[AgentMetricPoint]:
    """
    Get time-series data for a specific metric.

    Useful for charting latency, tokens, or errors over time.

    Example:
        GET /metrics/timeseries?metric_name=latency_ms&interval=1%20hour&bucket_size=5%20minutes

    Returns:
        List of metric data points bucketed by time
    """
    query = """
    SELECT
        time_bucket(:bucket_size::INTERVAL, time) AS bucket,
        agent_id,
        :metric_name AS metric_name,
        AVG(value) AS value
    FROM agent_metrics
    WHERE metric_name = :metric_name
      AND time >= NOW() - :interval::INTERVAL
    """

    params = {
        "bucket_size": bucket_size,
        "metric_name": metric_name,
        "interval": interval,
    }

    if agent_id:
        query += " AND agent_id = :agent_id"
        params["agent_id"] = agent_id

    query += """
    GROUP BY bucket, agent_id
    ORDER BY bucket DESC
    LIMIT 288
    """  # Max 288 points (24 hours at 5-min buckets)

    result = await conn.execute(text(query), params)
    rows = result.mappings().all()

    return [
        AgentMetricPoint(
            timestamp=row["bucket"],
            agent_id=row["agent_id"],
            metric_name=row["metric_name"],
            value=round(row["value"], 2),
            labels={},
        )
        for row in rows
    ]


@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics() -> SystemMetrics:
    """
    Get system resource metrics (CPU, memory, disk).

    Returns:
        SystemMetrics with current resource usage

    Example:
        >>> curl http://localhost:8000/metrics/system
        {
            "timestamp": "2026-01-13T12:00:00Z",
            "cpu_percent": 45.2,
            "memory_percent": 62.8,
            "memory_available_mb": 4096.5,
            "disk_percent": 73.1,
            "disk_available_gb": 125.7
        }
    """
    import psutil

    # Get memory info
    memory = psutil.virtual_memory()
    memory_available_mb = memory.available / (1024 * 1024)

    # Get disk info (root partition)
    disk = psutil.disk_usage("/")
    disk_available_gb = disk.free / (1024 * 1024 * 1024)

    return SystemMetrics(
        timestamp=datetime.now(UTC),
        cpu_percent=round(psutil.cpu_percent(interval=0.1), 2),
        memory_percent=round(memory.percent, 2),
        memory_available_mb=round(memory_available_mb, 2),
        disk_percent=round(disk.percent, 2),
        disk_available_gb=round(disk_available_gb, 2),
    )


@router.get("/health")
async def metrics_health_check():
    """
    Health check for metrics API.

    Returns:
        Status message
    """
    return {
        "status": "healthy",
        "service": "metrics-api",
        "timestamp": datetime.now(UTC).isoformat(),
    }
