# Observability API

## Overview

Real-time AI agent monitoring system based on **Research Paper #08**: "Real-Time Observability Dashboard for AI Agent Platforms".

**Phase 1 Features:**
- ✅ OpenTelemetry instrumentation (GenAI conventions v1.37+)
- ✅ 3-layer metrics taxonomy (Infrastructure, Economic, Cognitive)
- ✅ Automatic PII redaction
- ✅ In-memory fallback (no DB required for development)
- ✅ FastAPI endpoints for dashboard API
- ✅ TimescaleDB schema with hypertables

## Architecture

```
┌─────────────────┐
│  Agent Code     │
│  @instrument    │
└────────┬────────┘
         │ OpenTelemetry Spans
         ▼
┌─────────────────┐
│ MetricsCollector│
│  - latency_ms   │
│  - tokens       │
│  - errors       │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────┐   ┌──────────────┐
│ RAM │   │ TimescaleDB  │
└─────┘   │ (Production) │
          └──────────────┘
                 │
                 ▼
          ┌──────────────┐
          │ FastAPI API  │
          │ /metrics/*   │
          └──────────────┘
```

## Modules

### 1. Tracer (`src/observability/tracer.py`)

OpenTelemetry instrumentation with automatic span creation.

#### `@instrument_tool(tool_name: str)` decorator

Automatically instruments agent tools with tracing.

**Captures:**
- Tool execution spans
- Input arguments (sanitized for PII)
- Output responses (truncated to 1000 chars)
- Success/failure status
- Execution time (automatic)

**Example:**
```python
from src.observability import instrument_tool

@instrument_tool("search_database")
async def search_db(query: str):
    results = await db.execute(query)
    return results
```

**GenAI Attributes (v1.37):**
- `gen_ai.system` - System name ("project38-agent")
- `gen_ai.tool.name` - Tool name (e.g., "search_database")
- `gen_ai.tool.args` - Sanitized input arguments (JSON)
- `gen_ai.tool.response` - Output (truncated)
- `error.type` - Exception type (on failure)
- `error.message` - Error message (on failure)

#### `sanitize_pii(data: Any) -> Any`

Redacts personally identifiable information.

**Patterns Detected:**
- Email addresses → `[EMAIL_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- SSNs → `[SSN_REDACTED]`
- Credit card numbers → `[CC_REDACTED]`

**Example:**
```python
from src.observability.tracer import sanitize_pii

text = "Contact user@example.com or call 555-123-4567"
safe = sanitize_pii(text)
# "Contact [EMAIL_REDACTED] or call [PHONE_REDACTED]"
```

#### `get_tracer()`

Returns the global OpenTelemetry tracer instance.

---

### 2. Metrics Collector (`src/observability/metrics.py`)

Collects and stores agent metrics in PostgreSQL/TimescaleDB.

#### `MetricsCollector(db_pool: asyncpg.Pool | None = None)`

Main metrics collection class.

**Initialization:**
```python
from src.observability import MetricsCollector
import asyncpg

# Development (in-memory)
collector = MetricsCollector(db_pool=None)

# Production (TimescaleDB)
pool = await asyncpg.create_pool(
    host="localhost",
    database="project38",
    user="postgres",
    password="password"
)
collector = MetricsCollector(db_pool=pool)
```

#### `record_latency(agent_id, latency_seconds, labels=None)`

Record end-to-end execution latency (Layer 1: Infrastructure).

**Parameters:**
- `agent_id` (str): Agent identifier
- `latency_seconds` (float): Execution time in seconds
- `labels` (dict, optional): Additional metadata

**Example:**
```python
import time

start = time.time()
result = await agent.execute()
elapsed = time.time() - start

await collector.record_latency("agent-123", elapsed, {"task": "search"})
```

#### `record_tokens(agent_id, input_tokens, output_tokens, model_id, reasoning_tokens=None, labels=None)`

Record token usage (Layer 2: Economic).

**Parameters:**
- `agent_id` (str): Agent identifier
- `input_tokens` (int): Input token count
- `output_tokens` (int): Output token count
- `model_id` (str): Model identifier (e.g., "claude-sonnet-4.5")
- `reasoning_tokens` (int, optional): Hidden reasoning tokens (2026 models)
- `labels` (dict, optional): Additional metadata

**Example:**
```python
await collector.record_tokens(
    "agent-123",
    input_tokens=500,
    output_tokens=200,
    model_id="claude-sonnet-4.5",
    reasoning_tokens=100  # For models with extended thinking
)
```

**Token Pricing (Estimated):**
- Claude Sonnet 4.5: ~$0.003/1K input, ~$0.015/1K output
- GPT-4 Turbo: ~$0.01/1K input, ~$0.03/1K output
- DeepSeek-R1: ~$0.0002/1K (open source)

#### `record_success(agent_id, task_type, labels=None)`

Record successful task completion (Layer 3: Cognitive).

**Parameters:**
- `agent_id` (str): Agent identifier
- `task_type` (str): Type of task completed
- `labels` (dict, optional): Additional metadata

**Example:**
```python
await collector.record_success("agent-123", "database_query")
```

#### `record_error(agent_id, error_type, error_message, labels=None)`

Record agent error (Layer 1: Infrastructure).

**Parameters:**
- `agent_id` (str): Agent identifier
- `error_type` (str): Type of error (e.g., "APIError", "ValidationError")
- `error_message` (str): Error description (truncated to 200 chars)
- `labels` (dict, optional): Additional metadata

**Example:**
```python
try:
    await agent.execute()
except Exception as e:
    await collector.record_error(
        "agent-123",
        type(e).__name__,
        str(e)
    )
    raise
```

#### `get_recent_metrics(agent_id=None, limit=100)`

Retrieve recent metrics (for Phase 1 development).

**Parameters:**
- `agent_id` (str, optional): Filter by agent
- `limit` (int): Max number of metrics (default: 100)

**Returns:**
- `list[dict]`: List of metric dictionaries

**Example:**
```python
# Get all recent metrics
metrics = await collector.get_recent_metrics()

# Get metrics for specific agent
agent_metrics = await collector.get_recent_metrics(agent_id="agent-123")
```

---

### 3. FastAPI Endpoints (`src/api/routes/metrics.py`)

REST API for observability dashboard.

#### `GET /metrics/summary`

Dashboard summary statistics.

**Response:**
```json
{
  "active_agents": 5,
  "total_requests_1h": 234,
  "error_rate_pct": 2.5,
  "avg_latency_ms": 1250.5,
  "p95_latency_ms": 2100.0,
  "total_tokens_1h": 125000,
  "estimated_cost_1h": 1.125
}
```

#### `GET /metrics/agents`

Per-agent statistics.

**Response:**
```json
[
  {
    "agent_id": "agent-123",
    "status": "active",
    "last_execution": "2026-01-12T10:30:00Z",
    "success_rate_pct": 97.5,
    "avg_latency_ms": 1200,
    "total_tokens_24h": 15000,
    "estimated_cost_24h": 0.225
  }
]
```

#### `GET /metrics/timeseries`

Time-series data for charts.

**Query Parameters:**
- `metric_name` (str): Metric to retrieve (e.g., "latency_ms")
- `agent_id` (str, optional): Filter by agent
- `interval` (str): Time range (e.g., "1 hour", "24 hours")
- `bucket_size` (str): Aggregation bucket (e.g., "5 minutes")

**Response:**
```json
[
  {
    "bucket": "2026-01-12T10:00:00Z",
    "avg_value": 1250.5,
    "min_value": 800.0,
    "max_value": 2100.0,
    "count": 42
  }
]
```

#### `GET /metrics/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "metrics_count": 15234
}
```

---

## Usage Examples

### Basic Instrumentation

```python
from src.observability import instrument_tool, MetricsCollector

collector = MetricsCollector(db_pool=None)

@instrument_tool("process_data")
async def process_data(data: dict):
    # Automatically traced
    await collector.record_tokens("agent-1", 100, 50, "claude-sonnet-4.5")
    await collector.record_success("agent-1", "process_data")
    return {"status": "ok"}

result = await process_data({"key": "value"})
```

### With Context Manager

```python
from src.observability import MetricsCollector
from src.observability.metrics import LatencyTracker

collector = MetricsCollector(db_pool=None)

async with LatencyTracker(collector, "agent-123", {"task": "search"}):
    # Latency automatically recorded
    result = await perform_search()
```

### Dashboard API Client

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get summary
    response = await client.get("http://localhost:8000/metrics/summary")
    summary = response.json()
    print(f"Active agents: {summary['active_agents']}")

    # Get time-series data
    response = await client.get(
        "http://localhost:8000/metrics/timeseries",
        params={
            "metric_name": "latency_ms",
            "interval": "1 hour",
            "bucket_size": "5 minutes"
        }
    )
    timeseries = response.json()
```

---

## 3-Layer Metrics Taxonomy

Based on Research Paper #08, Section 2.

### Layer 1: Infrastructure Metrics
Performance and reliability indicators.

| Metric | Description | Unit | Target |
|--------|-------------|------|--------|
| `latency_ms` | End-to-end execution time | milliseconds | < 2000ms (P95) |
| `error_count` | Failed requests | count | < 1% error rate |
| `success_count` | Successful requests | count | > 99% success rate |

### Layer 2: Economic Metrics
Cost and resource utilization.

| Metric | Description | Unit | Cost (Approx) |
|--------|-------------|------|---------------|
| `tokens_input` | Input tokens consumed | count | $0.003/1K (Claude) |
| `tokens_output` | Output tokens generated | count | $0.015/1K (Claude) |
| `tokens_reasoning` | Hidden reasoning tokens | count | $0.015/1K (Claude) |

### Layer 3: Cognitive Metrics (Future)
Agent intelligence and effectiveness.

| Metric | Description | Unit | Target |
|--------|-------------|------|--------|
| `confidence_score` | Agent confidence (0-1) | float | > 0.8 |
| `coherence_score` | Response coherence | float | > 0.9 |
| `containment_rate` | Tasks resolved without escalation | percent | > 95% |

---

## Database Schema (TimescaleDB)

See `sql/observability_schema.sql` for complete schema.

**Hypertable:**
```sql
CREATE TABLE agent_metrics (
    time TIMESTAMPTZ NOT NULL,
    agent_id TEXT NOT NULL,
    model_id TEXT,
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    labels JSONB
);

SELECT create_hypertable('agent_metrics', 'time');
```

**Helper Functions:**
- `get_agent_error_rate(agent_id, interval)` - Calculate error rate
- `get_agent_p95_latency(agent_id, interval)` - Calculate P95 latency
- `estimate_cost(agent_id, interval)` - Estimate cost from token usage

---

## Testing

```bash
# Run observability tests
pytest tests/test_observability.py -v

# Run with coverage
pytest tests/test_observability.py --cov=src/observability --cov-report=html
```

**Test Coverage:**
- ✅ 25 comprehensive tests
- ✅ 100% coverage of tracer.py
- ✅ 100% coverage of metrics.py
- ✅ Integration tests with FastAPI endpoints

---

## Troubleshooting

### Issue: Metrics not appearing in dashboard

**Solution:**
1. Check if MetricsCollector is initialized with DB pool
2. Verify TimescaleDB connection
3. Check `agent_metrics` table exists
4. Review database logs for errors

### Issue: PII not being redacted

**Solution:**
- Verify using `sanitize_pii()` before logging
- Check regex patterns in `tracer.py`
- Add custom patterns if needed

### Issue: High memory usage in development

**Solution:**
- In-memory buffer keeps last 1000 metrics
- Use TimescaleDB in production
- Enable compression: `ALTER TABLE agent_metrics SET (timescaledb.compress);`

---

## Roadmap

- [x] Phase 1: Basic instrumentation + metrics collection
- [ ] Phase 2: Server-Sent Events (SSE) for real-time updates
- [ ] Phase 3: HTMX dashboard UI
- [ ] Phase 4: Alert thresholds + PagerDuty integration
- [ ] Phase 5: Trust Score integration (from Paper #09)

---

## References

- [Research Paper #08](../../research/08_realtime_observability_dashboard_ai_agents.md) - Complete architecture
- [OpenTelemetry GenAI Conventions v1.37](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/README.md)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
