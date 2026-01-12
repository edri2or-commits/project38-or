"""
Metrics API Endpoints

Provides real-time metrics for the observability dashboard.
Based on Research Paper #08, Section 5.3 (Dashboard Prototyping).

Phase 1: Basic metrics without SSE streaming.
Phase 2: Add Server-Sent Events (SSE) for real-time updates.
"""

from datetime import UTC, datetime

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.database import get_db

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


# =============================================================================
# Helper Functions
# =============================================================================


async def get_active_agent_count(conn: asyncpg.Connection) -> int:
    """Count agents active in last hour."""
    result = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT agent_id)
        FROM agent_metrics
        WHERE time >= NOW() - INTERVAL '1 hour'
        """
    )
    return result or 0


async def get_total_requests(conn: asyncpg.Connection, interval: str = "1 hour") -> int:
    """Count total requests (successes + errors)."""
    result = await conn.fetchval(
        f"""
        SELECT COALESCE(SUM(value), 0)::INT
        FROM agent_metrics
        WHERE metric_name IN ('success_count', 'error_count')
          AND time >= NOW() - INTERVAL '{interval}'
        """
    )
    return result or 0


async def get_error_rate(conn: asyncpg.Connection, interval: str = "1 hour") -> float:
    """Calculate global error rate."""
    errors = await conn.fetchval(
        f"""
        SELECT COALESCE(SUM(value), 0)
        FROM agent_metrics
        WHERE metric_name = 'error_count'
          AND time >= NOW() - INTERVAL '{interval}'
        """
    )

    total = await conn.fetchval(  # noqa: S608
        f"""
        SELECT COALESCE(SUM(value), 0)
        FROM agent_metrics
        WHERE metric_name IN ('success_count', 'error_count')
          AND time >= NOW() - INTERVAL '{interval}'
        """
    )

    if total == 0:
        return 0.0
    return round((errors / total) * 100, 2)


async def get_avg_latency(conn: asyncpg.Connection, interval: str = "1 hour") -> float:
    """Calculate average latency."""
    result = await conn.fetchval(  # noqa: S608
        f"""
        SELECT COALESCE(AVG(value), 0)
        FROM agent_metrics
        WHERE metric_name = 'latency_ms'
          AND time >= NOW() - INTERVAL '{interval}'
        """
    )
    return round(result or 0, 2)


async def get_p95_latency(conn: asyncpg.Connection, interval: str = "1 hour") -> float:
    """Calculate P95 latency."""
    result = await conn.fetchval(  # noqa: S608
        f"""
        SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value), 0)
        FROM agent_metrics
        WHERE metric_name = 'latency_ms'
          AND time >= NOW() - INTERVAL '{interval}'
        """
    )
    return round(result or 0, 2)


async def get_total_tokens(conn: asyncpg.Connection, interval: str = "1 hour") -> int:
    """Calculate total token usage."""
    result = await conn.fetchval(  # noqa: S608
        f"""
        SELECT COALESCE(SUM(value), 0)::INT
        FROM agent_metrics
        WHERE metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
          AND time >= NOW() - INTERVAL '{interval}'
        """
    )
    return result or 0


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
async def get_metrics_summary(conn: asyncpg.Connection = Depends(get_db)) -> MetricSummary:
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
    conn: asyncpg.Connection = Depends(get_db),
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
    agent_ids = await conn.fetch(
        """
        SELECT DISTINCT agent_id, MAX(time) as last_seen
        FROM agent_metrics
        WHERE time >= NOW() - INTERVAL '1 hour'
        GROUP BY agent_id
        ORDER BY last_seen DESC
        LIMIT $1
        """,
        limit,
    )

    statuses = []
    for row in agent_ids:
        agent_id = row["agent_id"]
        last_seen = row["last_seen"]

        # Get agent-specific metrics
        error_rate = await conn.fetchval(
            """
            SELECT get_agent_error_rate($1, '1 hour')
            """,
            agent_id,
        )

        total_requests = await conn.fetchval(
            """
            SELECT COALESCE(SUM(value), 0)::INT
            FROM agent_metrics
            WHERE agent_id = $1
              AND metric_name IN ('success_count', 'error_count')
              AND time >= NOW() - INTERVAL '1 hour'
            """,
            agent_id,
        )

        avg_latency = await conn.fetchval(
            """
            SELECT COALESCE(AVG(value), 0)
            FROM agent_metrics
            WHERE agent_id = $1
              AND metric_name = 'latency_ms'
              AND time >= NOW() - INTERVAL '1 hour'
            """,
            agent_id,
        )

        total_tokens = await conn.fetchval(
            """
            SELECT COALESCE(SUM(value), 0)::INT
            FROM agent_metrics
            WHERE agent_id = $1
              AND metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
              AND time >= NOW() - INTERVAL '1 hour'
            """,
            agent_id,
        )

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
    conn: asyncpg.Connection = Depends(get_db),
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
        time_bucket($1::INTERVAL, time) AS bucket,
        agent_id,
        $2 AS metric_name,
        AVG(value) AS value
    FROM agent_metrics
    WHERE metric_name = $2
      AND time >= NOW() - $3::INTERVAL
    """

    params = [bucket_size, metric_name, interval]

    if agent_id:
        query += " AND agent_id = $4"
        params.append(agent_id)

    query += """
    GROUP BY bucket, agent_id
    ORDER BY bucket DESC
    LIMIT 288
    """  # Max 288 points (24 hours at 5-min buckets)

    rows = await conn.fetch(query, *params)

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
