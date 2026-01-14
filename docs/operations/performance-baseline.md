# Performance Baseline & Monitoring

**Last Updated:** 2026-01-14
**Status:** Production Ready
**Owners:** DevOps Team, SRE Team

---

## Overview

This document describes the performance baseline system for monitoring application health,
detecting anomalies, and alerting on performance degradation.

Based on Week 4 requirements from `docs/integrations/implementation-roadmap.md`.

**Key Features:**
- Automatic baseline establishment from historical metrics
- Real-time anomaly detection with configurable sensitivity
- Trend analysis (improving/degrading/stable)
- Alert suppression during maintenance windows
- Runbook integration for incident response
- Multi-channel notifications (Telegram, n8n)

**Components:**
- `src/performance_baseline.py` - Baseline calculation and anomaly detection
- `src/alert_manager.py` - Centralized alerting with suppression
- PostgreSQL `performance_snapshots` table - Metrics storage
- n8n workflows - Alert notification delivery

---

## Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    Metrics Collection                         │
│                                                               │
│  /metrics/summary → PerformanceBaseline.collect_metrics()    │
│                           ↓                                   │
│              PostgreSQL (performance_snapshots)              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                   Baseline Calculation                        │
│                                                               │
│  PerformanceBaseline.get_baseline_stats()                    │
│  - Calculate P50, P95, P99, mean, stddev                     │
│  - Use last 24 hours of data                                 │
│  - Store baseline for each metric                            │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    Anomaly Detection                          │
│                                                               │
│  PerformanceBaseline.detect_anomalies()                      │
│  - Calculate Z-score (deviations from baseline)              │
│  - Classify severity (info/warning/critical)                 │
│  - Generate anomaly reports                                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                     Alert Management                          │
│                                                               │
│  AlertManager.send_performance_alert()                       │
│  - Check maintenance windows (suppression)                   │
│  - Apply rate limiting (deduplication)                       │
│  - Add runbook URL                                           │
│  - Send to n8n webhook → Telegram                            │
└──────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
CREATE TABLE performance_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL,
    p95_latency_ms DOUBLE PRECISION NOT NULL,
    error_rate_pct DOUBLE PRECISION NOT NULL,
    throughput_rph INTEGER NOT NULL,
    active_agents INTEGER NOT NULL,
    total_tokens_1h INTEGER NOT NULL,
    cpu_percent DOUBLE PRECISION NOT NULL,
    memory_percent DOUBLE PRECISION NOT NULL,
    UNIQUE(timestamp)
);

CREATE INDEX idx_snapshots_timestamp
    ON performance_snapshots(timestamp DESC);
```

---

## Configuration

### Performance Baseline Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `baseline_window_hours` | 24 | Hours of historical data for baseline calculation |
| `collection_interval_minutes` | 5 | Frequency of metric snapshots |
| `anomaly_threshold_stddev` | 3.0 | Z-score threshold for anomaly detection (3σ) |

### Alert Manager Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rate_limit_minutes.critical` | 15 | Minutes between critical alerts (same dedupe key) |
| `rate_limit_minutes.warning` | 60 | Minutes between warning alerts |
| `rate_limit_minutes.info` | 1440 | Minutes between info alerts (24 hours) |

### Environment Variables

```bash
# Required for AlertManager
N8N_BASE_URL="https://n8n.railway.app"         # n8n instance URL
TELEGRAM_CHAT_ID="123456789"                   # Telegram chat for notifications

# Required for PerformanceBaseline
DATABASE_URL="postgresql://user:pass@host/db"  # PostgreSQL connection
```

---

## Usage

### 1. Collect Metrics Snapshot

```python
from src.performance_baseline import PerformanceBaseline

baseline = PerformanceBaseline(
    database_url="postgresql://...",
    baseline_window_hours=24,
    collection_interval_minutes=5,
    anomaly_threshold_stddev=3.0,
)

# Collect current metrics
snapshot = await baseline.collect_metrics()
print(f"Latency: {snapshot.latency_ms:.2f}ms")
print(f"Error Rate: {snapshot.error_rate_pct:.2f}%")
print(f"Throughput: {snapshot.throughput_rph} requests/hour")
```

### 2. Calculate Baseline Statistics

```python
# Get baseline for all metrics
stats = await baseline.get_baseline_stats()

latency_baseline = stats["latency_ms"]
print(f"Latency P50: {latency_baseline.median:.2f}ms")
print(f"Latency P95: {latency_baseline.p95:.2f}ms")
print(f"Latency P99: {latency_baseline.p99:.2f}ms")
print(f"Mean: {latency_baseline.mean:.2f}ms ± {latency_baseline.stddev:.2f}ms")
print(f"Samples: {latency_baseline.sample_count}")

# Get baseline for specific metric
latency_stats = await baseline.get_baseline_stats(metric_name="latency_ms")
```

### 3. Detect Anomalies

```python
# Detect anomalies automatically
anomalies = await baseline.detect_anomalies()

for anomaly in anomalies:
    print(f"[{anomaly.severity.upper()}] {anomaly.message}")
    print(f"  Current: {anomaly.current_value:.2f}")
    print(f"  Expected: {anomaly.expected_value:.2f}")
    print(f"  Deviation: {anomaly.deviation_stddev:.1f}σ")

# Detect anomalies with provided snapshot
current_snapshot = await baseline.collect_metrics()
anomalies = await baseline.detect_anomalies(current_snapshot=current_snapshot)
```

### 4. Analyze Trends

```python
# Analyze performance trends
trends = await baseline.analyze_trends(recent_window_hours=6)

for trend in trends:
    print(f"{trend.metric_name}: {trend.trend}")
    print(f"  Change: {trend.change_pct:+.1f}%")
    print(f"  Recent Mean: {trend.recent_mean:.2f}")
    print(f"  Baseline Mean: {trend.baseline_mean:.2f}")
    print(f"  Confidence: {trend.confidence}")
```

### 5. Get Dashboard Data

```python
# Get comprehensive dashboard data
data = await baseline.get_dashboard_data()

print(f"Total Anomalies: {data['summary']['total_anomalies']}")
print(f"Critical Anomalies: {data['summary']['critical_anomalies']}")
print(f"Degrading Trends: {data['summary']['degrading_trends']}")
print(f"Improving Trends: {data['summary']['improving_trends']}")

# Use in API endpoint
from fastapi import APIRouter, Depends
router = APIRouter()

@router.get("/performance/dashboard")
async def get_performance_dashboard():
    baseline = PerformanceBaseline(database_url=get_db_url())
    return await baseline.get_dashboard_data()
```

### 6. Alert Management

```python
from src.alert_manager import AlertManager, MaintenanceWindow
from datetime import UTC, datetime, timedelta

manager = AlertManager(
    n8n_webhook_url="https://n8n.railway.app/webhook/alerts",
    telegram_chat_id="123456789",
)

# Send alert
result = await manager.send_alert(
    severity="warning",
    title="High Latency Detected",
    message="Average latency is 4.5σ above baseline (500ms vs 150ms expected)",
    runbook_url="https://docs.example.com/runbooks/high-latency",
    tags=["performance", "latency"],
    metadata={"current": 500.0, "expected": 150.0, "deviation": 4.5},
)

if result.success:
    print(f"Alert sent: {result.alert_id}")
elif result.suppressed:
    print(f"Alert suppressed: {result.suppression_reason}")
elif result.rate_limited:
    print("Alert rate limited (cooldown active)")
```

### 7. Maintenance Windows

```python
# Schedule maintenance window
window = MaintenanceWindow(
    start=datetime.now(UTC),
    end=datetime.now(UTC) + timedelta(hours=2),
    reason="Database migration",
    suppress_all=True,  # Suppress all alerts (critical/warning/info)
    created_by="admin@example.com",
    tags=["database", "migration"],
)

manager.add_maintenance_window(window)

# Suppress only info alerts during maintenance
partial_window = MaintenanceWindow(
    start=datetime.now(UTC),
    end=datetime.now(UTC) + timedelta(hours=1),
    reason="Minor deployment",
    suppress_all=False,  # Only suppress info alerts
)

manager.add_maintenance_window(partial_window)

# Check suppression status
suppressed, reason = manager.is_suppressed("warning")
if suppressed:
    print(f"Alerts suppressed: {reason}")
```

### 8. Performance Alert Integration

```python
# Integrate baseline anomaly detection with alert manager
baseline = PerformanceBaseline(database_url="postgresql://...")
manager = AlertManager(n8n_webhook_url="https://n8n.railway.app/webhook/alerts")

# Detect and alert on anomalies
anomalies = await baseline.detect_anomalies()
baseline_stats = await baseline.get_baseline_stats()

for anomaly in anomalies:
    result = await manager.send_performance_alert(anomaly, baseline_stats)
    if result.success:
        print(f"Alert sent for {anomaly.metric_name}")
```

---

## Runbook Mapping

The alert manager automatically maps metric names to runbook URLs:

| Metric | Runbook URL | Description |
|--------|-------------|-------------|
| `latency_ms` | `/runbooks/high-latency` | High request latency troubleshooting |
| `error_rate_pct` | `/runbooks/high-error-rate` | Elevated error rate investigation |
| `cpu_percent` | `/runbooks/high-cpu` | CPU usage spike resolution |
| `memory_percent` | `/runbooks/high-memory` | Memory pressure mitigation |
| `throughput_rph` | `/runbooks/low-throughput` | Low traffic investigation |

**To update runbooks**: Edit `src/alert_manager.py` → `send_performance_alert()` → `runbook_mapping`.

---

## Anomaly Detection Thresholds

### Z-Score Classification

| Z-Score | Severity | Alert | Description |
|---------|----------|-------|-------------|
| < 3.0σ | None | No alert | Within normal variation |
| 3.0-3.9σ | Info | Logged only | Minor deviation |
| 4.0-4.9σ | Warning | Alert sent | Significant deviation |
| ≥ 5.0σ | Critical | Urgent alert | Extreme deviation |

### Example Calculation

```
Baseline: latency_ms mean=150ms, stddev=25ms
Current: latency_ms = 250ms

Z-score = (250 - 150) / 25 = 4.0σ
Severity: Warning
```

### Tuning Sensitivity

```python
# More sensitive (detect smaller anomalies)
baseline = PerformanceBaseline(
    database_url="...",
    anomaly_threshold_stddev=2.0,  # Detect at 2σ
)

# Less sensitive (reduce false positives)
baseline = PerformanceBaseline(
    database_url="...",
    anomaly_threshold_stddev=4.0,  # Only detect at 4σ
)
```

---

## Trend Analysis

### Trend Classification

| Change % | Latency/Error | Throughput | Classification |
|----------|---------------|------------|----------------|
| < -5% | Improving | Degrading | Stable |
| -5% to +5% | Stable | Stable | Stable |
| > +5% | Degrading | Improving | Needs attention |

**For metrics where lower is better** (latency, error rate, CPU, memory):
- Decrease > 5% = Improving
- Increase > 5% = Degrading

**For metrics where higher is better** (throughput):
- Increase > 5% = Improving
- Decrease > 5% = Degrading

### Confidence Levels

| Sample Count | Confidence | Meaning |
|--------------|------------|---------|
| Recent ≥ 10, Baseline ≥ 20 | High | Trend is statistically significant |
| Recent ≥ 5, Baseline ≥ 10 | Medium | Trend is likely accurate |
| Less data | Low | Trend may be noise |

---

## Monitoring Schedule

### Automated Tasks

| Task | Frequency | Implementation |
|------|-----------|----------------|
| Metric Snapshot Collection | Every 5 minutes | n8n workflow or cron job |
| Anomaly Detection | Every 5 minutes | After each snapshot collection |
| Baseline Recalculation | Hourly | Rolling 24-hour window |
| Trend Analysis | Every 6 hours | Compare 6h recent vs 24h baseline |
| Dashboard Update | Real-time | API endpoint `/performance/dashboard` |

### Manual Tasks

| Task | Frequency | Owner |
|------|-----------|-------|
| Review Baseline Stats | Weekly | SRE Team |
| Tune Anomaly Thresholds | Monthly | DevOps Team |
| Update Runbooks | As needed | On-call Engineer |
| Test Alert Delivery | Weekly | DevOps Team |

---

## Alert Rate Limiting

### Default Cooldowns

- **Critical**: 15 minutes (urgent, frequent updates needed)
- **Warning**: 60 minutes (important but not urgent)
- **Info**: 1440 minutes (24 hours, low priority)

### Deduplication

Alerts with the same `dedupe_key` are subject to rate limiting:

```python
# These three alerts will be deduplicated
await manager.send_alert(
    title="High Latency",
    message="Latency is high (attempt 1)",
    dedupe_key="performance_latency_ms",  # Same key
)

await manager.send_alert(
    title="High Latency",
    message="Latency is high (attempt 2)",  # Sent immediately after
    dedupe_key="performance_latency_ms",  # Same key → Rate limited
)
```

### Bypassing Rate Limits

```python
# Force send alert regardless of cooldown
result = await manager.send_alert(
    severity="critical",
    title="Critical Issue",
    message="System is down",
    force=True,  # Bypass suppression and rate limits
)
```

---

## Maintenance Windows

### Use Cases

1. **Planned Deployments** - Suppress alerts during deployment
2. **Database Migrations** - Suppress alerts during schema changes
3. **Infrastructure Upgrades** - Suppress alerts during Railway maintenance
4. **Load Testing** - Suppress alerts during performance testing

### Suppression Modes

#### Full Suppression (`suppress_all=True`)

Suppresses **all alerts** (critical, warning, info):

```python
window = MaintenanceWindow(
    start=datetime.now(UTC),
    end=datetime.now(UTC) + timedelta(hours=2),
    reason="Critical database migration",
    suppress_all=True,
)
```

**Use for:** High-impact maintenance where all alerts are expected.

#### Partial Suppression (`suppress_all=False`)

Suppresses **only info alerts** (critical and warning still sent):

```python
window = MaintenanceWindow(
    start=datetime.now(UTC),
    end=datetime.now(UTC) + timedelta(minutes=30),
    reason="Minor deployment",
    suppress_all=False,
)
```

**Use for:** Low-impact changes where critical issues should still alert.

### Example: Weekly Deployment Window

```python
from datetime import UTC, datetime, timedelta

# Every Friday 10:00 PM - 11:00 PM UTC
def create_weekly_deployment_window():
    now = datetime.now(UTC)
    # Find next Friday
    days_until_friday = (4 - now.weekday()) % 7
    next_friday = now + timedelta(days=days_until_friday)
    start = next_friday.replace(hour=22, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    return MaintenanceWindow(
        start=start,
        end=end,
        reason="Weekly deployment window",
        suppress_all=False,  # Only suppress info
        tags=["deployment", "weekly"],
    )

window = create_weekly_deployment_window()
manager.add_maintenance_window(window)
```

---

## Dashboard Integration

### API Endpoints

```python
from fastapi import APIRouter
from src.performance_baseline import PerformanceBaseline

router = APIRouter()

@router.get("/performance/dashboard")
async def get_dashboard():
    """Get comprehensive performance dashboard data."""
    baseline = PerformanceBaseline(database_url=get_db_url())
    return await baseline.get_dashboard_data()

@router.get("/performance/anomalies")
async def get_anomalies():
    """Get current anomalies only."""
    baseline = PerformanceBaseline(database_url=get_db_url())
    anomalies = await baseline.detect_anomalies()
    return {"anomalies": [a.to_dict() for a in anomalies]}

@router.get("/performance/trends")
async def get_trends():
    """Get performance trends."""
    baseline = PerformanceBaseline(database_url=get_db_url())
    trends = await baseline.analyze_trends()
    return {"trends": [t.to_dict() for t in trends]}
```

### Dashboard Response Structure

```json
{
  "current_metrics": {
    "timestamp": "2026-01-14T12:00:00Z",
    "latency_ms": 150.5,
    "p95_latency_ms": 350.2,
    "error_rate_pct": 1.5,
    "throughput_rph": 1200,
    "active_agents": 5,
    "total_tokens_1h": 50000,
    "cpu_percent": 45.5,
    "memory_percent": 62.3
  },
  "baselines": {
    "latency_ms": {
      "mean": 145.2,
      "median": 142.5,
      "p95": 320.8,
      "p99": 450.3,
      "stddev": 25.4,
      "sample_count": 288
    }
  },
  "anomalies": [
    {
      "metric_name": "latency_ms",
      "current_value": 500.0,
      "expected_value": 145.2,
      "deviation_stddev": 4.5,
      "severity": "warning",
      "message": "latency_ms is 4.5σ above baseline"
    }
  ],
  "trends": [
    {
      "metric_name": "latency_ms",
      "trend": "degrading",
      "change_pct": 12.5,
      "confidence": "high"
    }
  ],
  "summary": {
    "total_anomalies": 1,
    "critical_anomalies": 0,
    "degrading_trends": 1,
    "improving_trends": 2
  }
}
```

---

## Troubleshooting

### No Baseline Data

**Symptom:** `get_baseline_stats()` returns empty dict.

**Cause:** No metrics in `performance_snapshots` table.

**Solution:**
```python
# Manually collect initial snapshot
baseline = PerformanceBaseline(database_url="...")
await baseline.collect_metrics()

# Wait 5 minutes and collect again
import asyncio
await asyncio.sleep(300)
await baseline.collect_metrics()

# Verify
stats = await baseline.get_baseline_stats()
print(f"Samples: {stats.get('latency_ms', {}).get('sample_count', 0)}")
```

### False Positive Anomalies

**Symptom:** Too many anomaly alerts for normal variations.

**Cause:** `anomaly_threshold_stddev` too low (default 3.0σ).

**Solution:**
```python
# Increase threshold to reduce sensitivity
baseline = PerformanceBaseline(
    database_url="...",
    anomaly_threshold_stddev=4.0,  # Only alert at 4σ+
)
```

### Alerts Not Sending

**Symptom:** `send_alert()` returns `success=False`.

**Causes:**
1. **Suppression**: Check maintenance windows
2. **Rate limiting**: Check cooldown period
3. **n8n webhook fail**: Verify n8n URL

**Solution:**
```python
# Check status
status = manager.get_status()
print(f"n8n configured: {status['n8n_configured']}")
print(f"Active windows: {status['active_maintenance_windows']}")
print(f"Maintenance windows: {status['maintenance_windows']}")

# Force send to bypass suppression/rate limits
result = await manager.send_alert(
    severity="critical",
    title="Test Alert",
    message="Testing alert delivery",
    force=True,
)
```

### High Memory Usage

**Symptom:** Alert history grows unbounded.

**Solution:**
```python
# Periodically clear old history
manager.clear_history()

# Or restart AlertManager periodically
```

---

## Performance Considerations

### Database Queries

The performance baseline runs these queries:

| Query | Frequency | Rows | Index Used |
|-------|-----------|------|------------|
| INSERT snapshot | Every 5 min | 1 | N/A |
| SELECT for baseline | On demand | 288 (24h @ 5min) | `idx_snapshots_timestamp` |
| SELECT for trends | On demand | 72 (6h @ 5min) | `idx_snapshots_timestamp` |

**Index:**
```sql
CREATE INDEX idx_snapshots_timestamp
    ON performance_snapshots(timestamp DESC);
```

### Data Retention

```sql
-- Delete snapshots older than 7 days (run daily)
DELETE FROM performance_snapshots
WHERE timestamp < NOW() - INTERVAL '7 days';
```

### Memory Usage

| Component | Memory | Notes |
|-----------|--------|-------|
| PerformanceBaseline | < 1 MB | Stateless, no caching |
| AlertManager | < 100 KB | Stores alert history in-memory |
| Dashboard Data | < 500 KB | Full JSON response |

---

## Migration from Week 2 Alerting

### Changes

1. **Cost alerts** → Use `AlertManager` instead of `CostAlertService`
2. **Direct Telegram** → Use `AlertManager` with n8n webhook
3. **No suppression** → Add `MaintenanceWindow` support
4. **No deduplication** → Add rate limiting by `dedupe_key`

### Migration Steps

```python
# Old (Week 2)
from src.cost_alert_service import CostAlertService

service = CostAlertService(
    cost_monitor=monitor,
    n8n_webhook_url="https://n8n.railway.app/webhook/cost-alert",
)

result = await service.check_and_alert(deployment_id, budget)

# New (Week 4)
from src.alert_manager import AlertManager

manager = AlertManager(
    n8n_webhook_url="https://n8n.railway.app/webhook/alerts",
    telegram_chat_id="123456789",
)

result = await manager.send_alert(
    severity="warning",
    title="Budget Alert",
    message=f"Projected cost: ${projected_cost:.2f} (budget: ${budget:.2f})",
    runbook_url="https://docs.example.com/runbooks/cost-optimization",
)
```

---

## Security Considerations

1. **Database Access**: `performance_snapshots` table should be read-only for most users
2. **Alert Webhooks**: n8n webhook URLs should be kept secret (use environment variables)
3. **Telegram Chat IDs**: Should not be committed to code
4. **Runbook URLs**: Should require authentication (internal docs)

---

## References

- Week 4 roadmap: `docs/integrations/implementation-roadmap.md` (lines 1942-1951)
- Cost monitoring (Week 2): `src/cost_monitor.py`
- Metrics API: `src/api/routes/metrics.py`
- Backup automation (Week 3): `docs/operations/disaster-recovery.md`
