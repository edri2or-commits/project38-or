# Observability Module

Real-time AI agent monitoring based on **Research Paper #08**: "Real-Time Observability Dashboard for AI Agent Platforms".

## 🎯 Features (Phase 1)

- ✅ **OpenTelemetry instrumentation** (GenAI conventions v1.37+)
- ✅ **3-layer metrics**: Infrastructure, Economic, Cognitive
- ✅ **Automatic PII redaction** (emails, SSNs, phone numbers)
- ✅ **In-memory fallback** (no DB required for development)
- ✅ **FastAPI endpoints** (`/metrics/summary`, `/metrics/agents`)
- ✅ **TimescaleDB schema** (hypertables, continuous aggregates)

## 📦 Components

| File | Purpose |
|------|---------|
| `tracer.py` | OTel instrumentation, `@instrument_tool` decorator |
| `metrics.py` | Metrics collector, `MetricsCollector` class |
| `README.md` | This file |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Instrument Your Agent

```python
from src.observability import instrument_tool, MetricsCollector

# Initialize collector (in-memory for dev)
collector = MetricsCollector(db_pool=None)

# Decorate your tools
@instrument_tool("search_database")
async def search_database(query: str):
    # Your code here
    return results

# Record metrics manually
await collector.record_latency("agent-123", 1.5)  # 1.5 seconds
await collector.record_tokens("agent-123", 100, 50, "claude-sonnet-4.5")
await collector.record_success("agent-123", "search")
```

### 3. Run Demo

```bash
python examples/observability_demo.py
```

## 🗄️ Database Setup (Optional for Production)

### Install TimescaleDB

```bash
# macOS
brew install timescaledb

# Ubuntu/Debian
sudo apt install postgresql-14-timescaledb

# Enable extension
psql -d your_database -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Apply Schema

```bash
psql -d your_database -f sql/observability_schema.sql
```

### Configure Database Connection

```python
import asyncpg

# Create connection pool
pool = await asyncpg.create_pool(
    host="localhost",
    port=5432,
    database="project38",
    user="postgres",
    password="your_password"
)

# Initialize collector with DB
collector = MetricsCollector(db_pool=pool)
```

## 📊 API Endpoints

Start FastAPI server:

```bash
uvicorn src.api.main:app --reload
```

### Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metrics/summary` | GET | Dashboard summary (active agents, error rate, latency, tokens) |
| `/metrics/agents` | GET | Per-agent statistics |
| `/metrics/timeseries` | GET | Time-series data for charts |
| `/metrics/health` | GET | Health check |

### Example: Get Summary

```bash
curl http://localhost:8000/metrics/summary
```

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

### Example: Get Time-Series

```bash
curl "http://localhost:8000/metrics/timeseries?metric_name=latency_ms&interval=1%20hour&bucket_size=5%20minutes"
```

## 🎨 Dashboard (Phase 2)

Phase 1 provides the **API foundation**. Phase 2 will add:

- ✅ Real-time updates with Server-Sent Events (SSE)
- ✅ HTMX-based UI (no React/Vue complexity)
- ✅ Live charts (Mermaid.js, Chart.js)
- ✅ Alert thresholds (PagerDuty, Slack integration)

## 📏 Metrics Taxonomy

### Layer 1: Infrastructure
- `latency_ms` - End-to-end execution time
- `error_count` - Failed requests
- `success_count` - Successful requests

### Layer 2: Economic
- `tokens_input` - Input tokens consumed
- `tokens_output` - Output tokens generated
- `tokens_reasoning` - Hidden reasoning tokens (2026 models)

### Layer 3: Cognitive (Future)
- `confidence_score` - Agent confidence (0-1)
- `coherence_score` - Response coherence
- `containment_rate` - Tasks resolved without escalation

## 🔍 Useful Queries

### Get Error Rate for Agent

```sql
SELECT get_agent_error_rate('agent-123', '1 hour');
```

### Get P95 Latency

```sql
SELECT get_agent_p95_latency('agent-123', '1 hour');
```

### Find Top Token Consumers

```sql
SELECT
    agent_id,
    SUM(value) AS total_tokens
FROM agent_metrics
WHERE metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
  AND time >= NOW() - INTERVAL '24 hours'
GROUP BY agent_id
ORDER BY total_tokens DESC
LIMIT 10;
```

## 🧪 Testing

Run observability tests:

```bash
pytest tests/test_observability.py -v
```

## 📚 Research Paper References

All implementation follows **Research Paper #08**:

- Section 1.1: OTel GenAI Conventions v1.37+ (line 15)
- Section 2: 3-Layer Metrics Taxonomy (line 23-61)
- Section 5.1: Python Decorator for Instrumentation (line 180-223)
- Section 5.2: TimescaleDB Schema (line 231-257)
- Section 5.3: FastAPI SSE Endpoint (line 266-305)

## 🚧 Roadmap

- [x] Phase 1: Basic instrumentation + metrics collection
- [ ] Phase 2: SSE real-time updates
- [ ] Phase 3: HTMX dashboard UI
- [ ] Phase 4: Alert thresholds + PagerDuty
- [ ] Phase 5: Trust Score integration (from Paper #09)

## 💡 Tips

1. **Start with in-memory collector** - No DB required for development
2. **Use @instrument_tool** - Automatic tracing with zero boilerplate
3. **Check /metrics/summary** - Quick health check via API
4. **Enable TimescaleDB compression** - Saves 90% storage for historical data
5. **Set retention policies** - Auto-delete metrics older than 90 days

## 🤝 Integration with Other Modules

- **Agent Factory** (`src/factory/`) - Instrument generator functions
- **Agent Harness** (`src/harness/`) - Track scheduler execution
- **Trust Score** (Future, Paper #09) - Feed success/failure to Beta parameters

---

**Questions? See Research Paper #08 or create an issue.**
