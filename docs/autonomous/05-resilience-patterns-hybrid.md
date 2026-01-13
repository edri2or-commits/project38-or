# Resilience Patterns: Building Antifragile Autonomous Systems

## Overview

An autonomous system must be **resilient** - capable of recovering from failures without human intervention. This document details battle-tested resilience patterns from distributed systems research, implemented in production-ready Python code.

---

## The Resilience Philosophy

### Beyond Robustness: Antifragility

**Robustness**: System resists failure (remains unchanged under stress)
**Resilience**: System recovers from failure (returns to normal state)
**Antifragility**: System improves from failure (learns and adapts)

**Goal**: Build an autonomous system that becomes *stronger* with each failure.

```
Failure → Detection → Recovery → Learning → Improvement
    ↑                                              ↓
    └──────────────── Feedback Loop ──────────────┘
```

---

## Failure Taxonomy

Understanding failure modes enables targeted resilience strategies.

| Failure Type | Characteristics | Recovery Strategy |
|--------------|----------------|-------------------|
| **Transient** | Temporary (network glitch, rate limit) | Retry with backoff |
| **Persistent** | Permanent (syntax error, missing file) | Rollback + Alert human |
| **Cascading** | Spreads to other services | Circuit breaker |
| **Byzantine** | Unpredictable (corrupted data) | Validation + Quarantine |
| **Silent** | No error raised (wrong behavior) | Health checks + Monitoring |

---

## Pattern 1: Exponential Backoff with Jitter

### The Problem

**Naive Retry**:
```python
for attempt in range(5):
    try:
        result = api_call()
        break
    except Exception:
        time.sleep(1)  # ❌ Fixed delay causes thundering herd
```

**Issue**: All retries happen simultaneously → amplifies load on recovering service.

---

### The Solution: Exponential Backoff + Jitter

**Formula**:
```
delay = min(base * 2^attempt + random(0, jitter), max_delay)
```

**Example Timeline**:
- Attempt 1: Fail → Wait 2s (2^0 * 2 + jitter)
- Attempt 2: Fail → Wait 4s (2^1 * 2 + jitter)
- Attempt 3: Fail → Wait 8s (2^2 * 2 + jitter)
- Attempt 4: Fail → Wait 16s (2^3 * 2 + jitter)
- Attempt 5: Fail → Wait 32s (2^4 * 2 + jitter)

**Jitter**: Adds randomness to prevent synchronized retries across multiple agents.

---

### Implementation with Tenacity

**Tenacity** is a battle-tested Python retry library (used by boto3, requests).

```python
"""Exponential backoff retry decorator using Tenacity."""
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep_log
)
import logging
import httpx

logger = logging.getLogger(__name__)

@retry(
    # Exponential backoff: 2^n seconds (max 60s)
    wait=wait_exponential(multiplier=2, min=2, max=60),

    # Stop after 5 attempts
    stop=stop_after_attempt(5),

    # Only retry on transient errors
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),

    # Log before each retry
    before_sleep=before_sleep_log(logger, logging.WARNING),

    # Re-raise exception if all retries fail
    reraise=True
)
async def resilient_api_call(url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Make API call with automatic retry on transient failures.

    Retries on:
    - Network timeouts
    - Connection errors
    - 5xx server errors (via raise_for_status)

    Does NOT retry on:
    - 4xx client errors (bad request, auth failure)
    - Logic errors in our code

    Returns:
        API response data

    Raises:
        httpx.HTTPStatusError: If all retries fail
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, timeout=10.0)
        response.raise_for_status()  # 4xx/5xx → exception
        return response.json()
```

**Usage**:
```python
# Automatic retry on transient failures
try:
    result = await resilient_api_call("https://api.railway.app/graphql", query)
    logger.info("API call succeeded")
except httpx.HTTPStatusError as e:
    logger.error(f"API call failed after 5 retries: {e}")
    # Escalate to human
```

---

### Retry Budget: Preventing Infinite Loops

**Problem**: Retrying forever can mask persistent failures and waste resources.

**Solution**: **Retry Budget** - limit total retry attempts across the system per time window.

```python
"""Retry budget implementation."""
from datetime import datetime, timedelta, UTC
from typing import Dict

class RetryBudget:
    """Enforce system-wide retry limits to prevent infinite retry loops.

    Concept from Google SRE: "The Case Against Retries"
    """

    def __init__(
        self,
        max_retries_per_hour: int = 100,
        window_minutes: int = 60
    ):
        self.max_retries = max_retries_per_hour
        self.window = timedelta(minutes=window_minutes)
        self.retry_log: Dict[str, list[datetime]] = {}

    def can_retry(self, operation: str) -> bool:
        """Check if operation can be retried within budget.

        Args:
            operation: Operation identifier (e.g., "railway_deploy")

        Returns:
            True if retry is allowed, False if budget exhausted
        """
        now = datetime.now(UTC)

        # Initialize log for this operation
        if operation not in self.retry_log:
            self.retry_log[operation] = []

        # Remove retries outside time window
        self.retry_log[operation] = [
            ts for ts in self.retry_log[operation]
            if now - ts < self.window
        ]

        # Check budget
        if len(self.retry_log[operation]) >= self.max_retries:
            logger.error(
                f"Retry budget exhausted for {operation}: "
                f"{len(self.retry_log[operation])} retries in last {self.window}"
            )
            return False

        # Allow retry and log it
        self.retry_log[operation].append(now)
        return True

# Global retry budget
retry_budget = RetryBudget(max_retries_per_hour=100)

# Usage
if retry_budget.can_retry("railway_deploy"):
    await resilient_api_call(...)
else:
    await alert_manager.send_alert(
        severity=AlertSeverity.CRITICAL,
        title="Retry Budget Exhausted",
        message="Railway deployment retries exceeded limit. Manual intervention required."
    )
```

---

## Pattern 2: Circuit Breaker

### The Problem

**Cascading Failure Scenario**:
```
Railway API down (500 errors)
    ↓
Agent keeps calling Railway (5 retries per call)
    ↓
Agent spends all time waiting for timeouts
    ↓
Agent can't respond to other events (GitHub, n8n)
    ↓
Entire system appears unresponsive
```

---

### The Solution: Circuit Breaker Pattern

**Metaphor**: Like an electrical circuit breaker, it "trips" when too many failures occur, preventing further damage.

**States**:
```
┌─────────────────────────────────────────────────────────────┐
│                   CIRCUIT BREAKER STATES                    │
└─────────────────────────────────────────────────────────────┘

    CLOSED (Normal Operation)
        │
        │ Failures < threshold
        ▼
    ┌─────────┐
    │ CLOSED  │ ← Requests pass through
    └────┬────┘
         │
         │ Failures ≥ threshold
         ▼
    ┌─────────┐
    │  OPEN   │ ← Requests fail immediately (no retry)
    └────┬────┘
         │
         │ After timeout (e.g., 60s)
         ▼
    ┌──────────┐
    │ HALF-OPEN│ ← Allow 1 test request
    └────┬─────┘
         │
         ├─ Success → CLOSED
         └─ Failure → OPEN
```

---

### Implementation

```python
"""Circuit breaker pattern implementation."""
from enum import Enum
from datetime import datetime, timedelta, UTC
from typing import Callable, Any
import asyncio

class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """Circuit breaker to prevent cascading failures.

    Based on Netflix Hystrix design.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            timeout_seconds: Time before attempting recovery (HALF_OPEN)
            success_threshold: Successes needed in HALF_OPEN to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: Original exception if function fails
        """
        # Check if circuit should transition OPEN → HALF_OPEN
        if self.state == CircuitState.OPEN:
            if datetime.now(UTC) - self.last_failure_time > self.timeout:
                logger.info("Circuit breaker: OPEN → HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Retry after {self.timeout.total_seconds()}s"
                )

        # Execute function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker: HALF_OPEN → CLOSED (recovery confirmed)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset on success

    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(UTC)

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker: HALF_OPEN → OPEN (test failed)")
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker: CLOSED → OPEN "
                    f"({self.failure_count} failures)"
                )
                self.state = CircuitState.OPEN

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass

# Usage
railway_circuit = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

async def safe_railway_call():
    """Call Railway API with circuit breaker protection."""
    try:
        result = await railway_circuit.call(
            railway_client.get_deployment_status,
            deployment_id="abc123"
        )
        return result
    except CircuitBreakerOpenError:
        logger.warning("Railway API circuit is OPEN, skipping call")
        return None
```

---

## Pattern 3: Bulkhead Isolation

### The Problem

**Resource Exhaustion**:
```
Railway API slow (5s per request)
    ↓
Agent uses all async workers on Railway calls
    ↓
GitHub API calls can't be processed (no free workers)
    ↓
Entire system blocked by one slow service
```

---

### The Solution: Bulkhead Pattern

**Metaphor**: Ship compartments (bulkheads) - if one floods, others remain intact.

**Implementation**: Limit concurrent operations per service.

```python
"""Bulkhead pattern using asyncio semaphores."""
import asyncio
from typing import Dict

class Bulkhead:
    """Resource isolation to prevent one service from exhausting all workers.

    Based on Netflix Hystrix design.
    """

    def __init__(self, max_concurrent: int = 10):
        """Initialize bulkhead.

        Args:
            max_concurrent: Max concurrent operations allowed
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.active_count = 0

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function within bulkhead limits.

        If max concurrent operations reached, this will wait until a slot is free.
        """
        async with self.semaphore:
            self.active_count += 1
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.active_count -= 1

# Create bulkheads per service
bulkheads = {
    "railway": Bulkhead(max_concurrent=5),
    "github": Bulkhead(max_concurrent=10),
    "n8n": Bulkhead(max_concurrent=3)
}

# Usage
async def isolated_railway_call():
    """Railway API call with bulkhead protection."""
    return await bulkheads["railway"].execute(
        railway_client.get_deployment_status,
        deployment_id="abc123"
    )

# Even if Railway is slow, GitHub calls can still proceed
async def isolated_github_call():
    """GitHub API call in separate bulkhead."""
    return await bulkheads["github"].execute(
        github_client.get_recent_commits,
        owner="edri2or-commits",
        repo="project38-or"
    )
```

---

## Pattern 4: Graceful Degradation

### The Philosophy

**Fail Gracefully**: When a service is unavailable, provide partial functionality instead of total failure.

**Example Scenarios**:

| Service Failure | Degraded Response |
|----------------|------------------|
| Railway API down | Return cached deployment status (with warning) |
| GitHub API down | Skip commit correlation, proceed with deployment |
| n8n API down | Log alert locally, skip Telegram notification |
| Database down | Store in memory, sync when recovered |

---

### Implementation

```python
"""Graceful degradation with fallback strategies."""
from typing import Optional
import json

class GracefulService:
    """Service wrapper with fallback strategies."""

    def __init__(
        self,
        primary_func: Callable,
        fallback_func: Optional[Callable] = None,
        cache_func: Optional[Callable] = None
    ):
        self.primary = primary_func
        self.fallback = fallback_func
        self.cache = cache_func

    async def execute(self, *args, **kwargs) -> Any:
        """Execute with fallback strategy.

        Strategy:
        1. Try primary function
        2. If fails and cache available, return cached value (with warning)
        3. If fails and fallback available, use fallback
        4. If all fail, raise exception
        """
        try:
            result = await self.primary(*args, **kwargs)

            # Cache successful result
            if self.cache:
                await self.cache.store(result)

            return result

        except Exception as e:
            logger.warning(f"Primary function failed: {e}")

            # Try cache
            if self.cache:
                cached_result = await self.cache.retrieve(*args, **kwargs)
                if cached_result:
                    logger.warning("Returning cached result (degraded mode)")
                    return {
                        "data": cached_result,
                        "degraded": True,
                        "reason": str(e)
                    }

            # Try fallback
            if self.fallback:
                logger.warning("Using fallback strategy")
                return await self.fallback(*args, **kwargs)

            # No recovery possible
            raise e

# Example: Railway deployment status with cache fallback
class DeploymentStatusCache:
    """In-memory cache for deployment status."""

    def __init__(self):
        self.cache: Dict[str, Dict] = {}

    async def store(self, deployment_id: str, status: Dict[str, Any]):
        """Cache deployment status."""
        self.cache[deployment_id] = {
            "status": status,
            "timestamp": datetime.now(UTC).isoformat()
        }

    async def retrieve(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached status."""
        return self.cache.get(deployment_id)

# Usage
status_cache = DeploymentStatusCache()

graceful_railway = GracefulService(
    primary_func=railway_client.get_deployment_status,
    cache_func=status_cache
)

# This will return cached status if Railway API is down
status = await graceful_railway.execute(deployment_id="abc123")
if status.get("degraded"):
    logger.warning(f"Operating in degraded mode: {status['reason']}")
```

---

## Pattern 5: Health Checks & Dead Letter Queue

### Health Check Implementation

```python
"""Comprehensive health check system."""
from enum import Enum

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthCheck:
    """System health monitoring."""

    async def check_all(self) -> Dict[str, Any]:
        """Check health of all dependencies.

        Returns:
            Health report with status per service
        """
        checks = {
            "railway": await self._check_railway(),
            "github": await self._check_github(),
            "n8n": await self._check_n8n(),
            "database": await self._check_database()
        }

        # Determine overall health
        if all(c["status"] == HealthStatus.HEALTHY for c in checks.values()):
            overall = HealthStatus.HEALTHY
        elif any(c["status"] == HealthStatus.UNHEALTHY for c in checks.values()):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED

        return {
            "status": overall,
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat()
        }

    async def _check_railway(self) -> Dict[str, Any]:
        """Check Railway API connectivity."""
        try:
            # Simple query to verify authentication
            await railway_client.get_deployment_status("test")
            return {"status": HealthStatus.HEALTHY, "latency_ms": 50}
        except Exception as e:
            return {"status": HealthStatus.UNHEALTHY, "error": str(e)}
```

---

### Dead Letter Queue (DLQ)

**Purpose**: Store failed operations for later retry or analysis.

```python
"""Dead Letter Queue for failed operations."""
from sqlmodel import SQLModel, Field
from typing import Optional

class FailedOperation(SQLModel, table=True):
    """Failed operation record."""

    __tablename__ = "dead_letter_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    operation: str  # "railway_deploy", "github_create_issue"
    params: Dict[str, Any] = Field(sa_column_kwargs={"type_": "JSONB"})
    error_message: str
    retry_count: int = 0
    max_retries: int = 3

class DeadLetterQueue:
    """Manage failed operations."""

    async def add(
        self,
        operation: str,
        params: Dict[str, Any],
        error: Exception
    ):
        """Add failed operation to DLQ."""
        failed_op = FailedOperation(
            operation=operation,
            params=params,
            error_message=str(error),
            retry_count=0,
            max_retries=3
        )
        session.add(failed_op)
        await session.commit()
        logger.warning(f"Operation added to DLQ: {operation}")

    async def process_dlq(self):
        """Retry failed operations from DLQ."""
        failed_ops = await session.execute(
            select(FailedOperation).where(
                FailedOperation.retry_count < FailedOperation.max_retries
            )
        )

        for op in failed_ops.scalars():
            try:
                # Retry operation
                await self._retry_operation(op)

                # Success - remove from DLQ
                await session.delete(op)
                await session.commit()
            except Exception as e:
                # Failed again - increment retry count
                op.retry_count += 1
                await session.commit()

                if op.retry_count >= op.max_retries:
                    # Max retries exceeded - alert human
                    await alert_manager.send_alert(
                        severity=AlertSeverity.CRITICAL,
                        title=f"DLQ: {op.operation} Failed After {op.max_retries} Retries",
                        message=f"Operation: {op.operation}\nError: {e}"
                    )
```

---

## Integration with OODA Loop

Resilience patterns integrate into every phase:

| OODA Phase | Resilience Pattern |
|------------|-------------------|
| **OBSERVE** | Graceful degradation (use cached data if API down) |
| **ORIENT** | Health checks (detect which services are degraded) |
| **DECIDE** | Circuit breaker (skip calls to failing services) |
| **ACT** | Exponential backoff + DLQ (retry failures intelligently) |

---

## Resilience Metrics

Track these metrics to measure system resilience:

```python
# Prometheus metrics
resilience_retry_total = Counter(
    "resilience_retry_total",
    "Total retry attempts",
    ["operation", "result"]
)

resilience_circuit_state = Gauge(
    "resilience_circuit_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"]
)

resilience_dlq_size = Gauge(
    "resilience_dlq_size",
    "Dead letter queue size"
)

resilience_degraded_responses = Counter(
    "resilience_degraded_responses_total",
    "Responses returned in degraded mode",
    ["service"]
)
```

---

## Production Checklist

- [ ] All external API calls wrapped in retry decorator
- [ ] Circuit breakers configured for Railway, GitHub, n8n
- [ ] Bulkheads limit concurrent operations per service
- [ ] Graceful degradation with cached fallbacks
- [ ] Health check endpoint returns service status
- [ ] Dead letter queue processes failed operations
- [ ] Retry budget prevents infinite retry loops
- [ ] Resilience metrics exported to Prometheus

---

**Next Document**: [Security Architecture](06-security-architecture-hybrid.md) - Zero Trust and Defense in Depth
