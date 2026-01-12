"""
Metrics Collection for AI Agent Observability

Implements the 3-layer metrics taxonomy from Research Paper #08:
1. Infrastructure (latency, throughput, errors)
2. Economic (token usage, cost)
3. Cognitive (success rate, confidence)

Phase 1: Basic metrics without Trust Score integration.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass, asdict
import asyncpg


@dataclass
class AgentMetric:
    """
    Single metric data point.

    Attributes:
        agent_id: Unique agent identifier
        model_id: LLM model used (e.g., "claude-sonnet-4.5")
        metric_name: Name of metric (e.g., "latency_ms", "token_usage")
        value: Numeric value
        labels: Additional metadata (JSON)
        timestamp: When the metric was recorded
    """
    agent_id: str
    model_id: Optional[str]
    metric_name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime


class MetricsCollector:
    """
    Collects and stores agent metrics in PostgreSQL/TimescaleDB.

    Based on Research Paper #08, Section 5.2 (Storage & Ingestion).

    Usage:
        collector = MetricsCollector(db_connection)
        await collector.record_latency("agent-123", 1.5, {"environment": "prod"})
        await collector.record_tokens("agent-123", 500, 200, "claude-sonnet-4.5")
    """

    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize metrics collector.

        Args:
            db_pool: AsyncPG connection pool (optional for Phase 1)
        """
        self.db_pool = db_pool
        self._in_memory_buffer = []  # Fallback for Phase 1

    async def record_metric(self, metric: AgentMetric):
        """
        Record a single metric.

        Args:
            metric: AgentMetric instance

        Returns:
            True if successfully stored
        """
        if self.db_pool:
            # Store in TimescaleDB
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_metrics (time, agent_id, model_id, metric_name, value, labels)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    metric.timestamp,
                    metric.agent_id,
                    metric.model_id,
                    metric.metric_name,
                    metric.value,
                    metric.labels
                )
            return True
        else:
            # Phase 1 fallback: in-memory buffer
            self._in_memory_buffer.append(metric)
            # Keep only last 1000 metrics
            if len(self._in_memory_buffer) > 1000:
                self._in_memory_buffer = self._in_memory_buffer[-1000:]
            return True

    async def record_latency(
        self,
        agent_id: str,
        latency_seconds: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Record end-to-end latency (Layer 1: Infrastructure).

        Args:
            agent_id: Agent identifier
            latency_seconds: Execution time in seconds
            labels: Additional metadata

        Example:
            >>> await collector.record_latency("agent-123", 1.5, {"task": "search"})
        """
        metric = AgentMetric(
            agent_id=agent_id,
            model_id=None,
            metric_name="latency_ms",
            value=latency_seconds * 1000,  # Convert to milliseconds
            labels=labels or {},
            timestamp=datetime.now(timezone.utc)
        )
        await self.record_metric(metric)

    async def record_tokens(
        self,
        agent_id: str,
        input_tokens: int,
        output_tokens: int,
        model_id: str,
        reasoning_tokens: Optional[int] = None,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Record token usage (Layer 2: Economic).

        Handles new 2026 models with separate reasoning tokens
        (e.g., OpenAI o-series, DeepSeek-R1).

        Args:
            agent_id: Agent identifier
            input_tokens: Input token count
            output_tokens: Output token count
            model_id: Model identifier
            reasoning_tokens: Hidden reasoning tokens (2026 models)
            labels: Additional metadata

        Example:
            >>> await collector.record_tokens(
            >>>     "agent-123", 100, 50, "claude-sonnet-4.5",
            >>>     reasoning_tokens=200
            >>> )
        """
        timestamp = datetime.now(timezone.utc)

        # Input tokens
        await self.record_metric(AgentMetric(
            agent_id=agent_id,
            model_id=model_id,
            metric_name="tokens_input",
            value=float(input_tokens),
            labels=labels or {},
            timestamp=timestamp
        ))

        # Output tokens
        await self.record_metric(AgentMetric(
            agent_id=agent_id,
            model_id=model_id,
            metric_name="tokens_output",
            value=float(output_tokens),
            labels=labels or {},
            timestamp=timestamp
        ))

        # Reasoning tokens (new in 2026)
        if reasoning_tokens:
            await self.record_metric(AgentMetric(
                agent_id=agent_id,
                model_id=model_id,
                metric_name="tokens_reasoning",
                value=float(reasoning_tokens),
                labels=labels or {},
                timestamp=timestamp
            ))

    async def record_error(
        self,
        agent_id: str,
        error_type: str,
        error_message: str,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Record agent error (Layer 1: Infrastructure).

        Args:
            agent_id: Agent identifier
            error_type: Type of error (e.g., "APIError", "ValidationError")
            error_message: Error description
            labels: Additional metadata

        Example:
            >>> await collector.record_error(
            >>>     "agent-123", "APIError", "Rate limit exceeded"
            >>> )
        """
        error_labels = labels or {}
        error_labels.update({
            "error_type": error_type,
            "error_message": error_message[:200]  # Truncate
        })

        metric = AgentMetric(
            agent_id=agent_id,
            model_id=None,
            metric_name="error_count",
            value=1.0,
            labels=error_labels,
            timestamp=datetime.now(timezone.utc)
        )
        await self.record_metric(metric)

    async def record_success(
        self,
        agent_id: str,
        task_type: str,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Record successful task completion (Layer 3: Cognitive).

        Args:
            agent_id: Agent identifier
            task_type: Type of task completed
            labels: Additional metadata

        Example:
            >>> await collector.record_success("agent-123", "database_query")
        """
        success_labels = labels or {}
        success_labels["task_type"] = task_type

        metric = AgentMetric(
            agent_id=agent_id,
            model_id=None,
            metric_name="success_count",
            value=1.0,
            labels=success_labels,
            timestamp=datetime.now(timezone.utc)
        )
        await self.record_metric(metric)

    async def get_recent_metrics(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict]:
        """
        Retrieve recent metrics (for Phase 1 development).

        Args:
            agent_id: Optional filter by agent
            limit: Max number of metrics

        Returns:
            List of metric dictionaries
        """
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                if agent_id:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM agent_metrics
                        WHERE agent_id = $1
                        ORDER BY time DESC
                        LIMIT $2
                        """,
                        agent_id, limit
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM agent_metrics
                        ORDER BY time DESC
                        LIMIT $1
                        """,
                        limit
                    )
                return [dict(row) for row in rows]
        else:
            # Phase 1 fallback
            filtered = self._in_memory_buffer
            if agent_id:
                filtered = [m for m in filtered if m.agent_id == agent_id]
            return [asdict(m) for m in filtered[-limit:]]


# Context manager for automatic latency tracking
class LatencyTracker:
    """
    Context manager to automatically track execution latency.

    Usage:
        async with LatencyTracker(collector, "agent-123"):
            # Do work
            result = await some_task()
    """

    def __init__(self, collector: MetricsCollector, agent_id: str, labels: Optional[Dict] = None):
        self.collector = collector
        self.agent_id = agent_id
        self.labels = labels or {}
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        await self.collector.record_latency(self.agent_id, elapsed, self.labels)

        # Record error if exception occurred
        if exc_type:
            await self.collector.record_error(
                self.agent_id,
                exc_type.__name__,
                str(exc_val),
                self.labels
            )
