# ADR-013: Night Watch - Autonomous Overnight Operations with Morning Summary

**Date**: 2026-01-22
**Status**: Proposed
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: automation, monitoring, telegram, scheduled-tasks, autonomy

---

## Context

### Background

The system has extensive autonomous capabilities built:
- `MonitoringLoop` for health checks and anomaly detection (607 lines)
- `AutonomousController` with safety guardrails (954 lines)
- `MLAnomalyDetector` for anomaly detection (835 lines)
- `APScheduler` with PostgreSQL advisory locks (388 lines)
- Telegram Bot deployed on Railway
- MCP Gateway for autonomous operations

**Problem**: All this code exists but **nothing runs automatically**. The system is reactive (responds to commands) not proactive (operates autonomously).

### User Request

> "שאני אשן בלילה ואקום בבוקר ואקבל איזו הודעה של סיכום של מה המערכת עשתה בזמן שישנתי"

Translation: "When I sleep at night and wake up in the morning, I want to receive a message summarizing what the system did while I was sleeping"

### Gap Analysis

| Component | Exists | Running | Gap |
|-----------|--------|---------|-----|
| MonitoringLoop | ✅ | ❌ | No scheduled trigger |
| APScheduler | ✅ | ❌ | No jobs configured |
| Telegram Bot | ✅ | ✅ | Passive only (no proactive messages) |
| AutonomousController | ✅ | ❌ | Not invoked automatically |
| Activity Logging | ❌ | ❌ | No persistent action log |
| Morning Summary | ❌ | ❌ | No aggregation logic |

---

## Decision

**Implement "Night Watch" - a scheduled autonomous operations service with morning summary.**

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Railway Cron Service: night-watch                          │
│  Schedule: Every hour 00:00-06:00 Israel Time               │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  NightWatchService                                    │  │
│  │  ├── health_check() → or-infra.com/api/health        │  │
│  │  ├── collect_metrics() → Railway API                  │  │
│  │  ├── detect_anomalies() → MLAnomalyDetector          │  │
│  │  ├── auto_heal() → if confidence > 80%               │  │
│  │  └── log_action() → PostgreSQL activity_log          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (06:00 Israel Time)
┌─────────────────────────────────────────────────────────────┐
│  MorningSummaryJob                                          │
│  ├── Query: SELECT * FROM activity_log WHERE ts > now-24h  │
│  ├── Aggregate: health checks, anomalies, actions          │
│  ├── Format: Hebrew summary message                         │
│  └── Send: Telegram Bot API → User                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    📱 Telegram Message:
                    "בוקר טוב! 🌅

                     סיכום הלילה (00:00-06:00):
                     ✅ בדיקות בריאות: 6/6 עברו
                     📊 אנומליות: 0 זוהו
                     🔧 פעולות אוטונומיות: 0

                     המערכת יציבה. יום טוב!"
```

### Components to Build

#### 1. Activity Log Table (PostgreSQL)

```sql
CREATE TABLE activity_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    action_type VARCHAR(50) NOT NULL,  -- 'health_check', 'anomaly_detected', 'auto_heal', 'alert_sent'
    component VARCHAR(100),             -- 'railway', 'api', 'database'
    status VARCHAR(20),                 -- 'success', 'failure', 'skipped'
    details JSONB,                      -- Action-specific data
    confidence FLOAT                    -- For autonomous actions
);

CREATE INDEX idx_activity_log_timestamp ON activity_log(timestamp);
```

#### 2. NightWatchService (src/night_watch/service.py)

```python
class NightWatchService:
    """Autonomous overnight operations."""

    async def run_hourly_check(self):
        """Run every hour during night hours."""
        # 1. Health check
        health = await self._check_health()
        await self._log_action("health_check", health)

        # 2. Collect metrics
        metrics = await self._collect_metrics()

        # 3. Detect anomalies
        anomalies = await self._detect_anomalies(metrics)
        if anomalies:
            await self._log_action("anomaly_detected", anomalies)

        # 4. Auto-heal if confident
        for anomaly in anomalies:
            if anomaly.confidence > 0.8:
                result = await self._auto_heal(anomaly)
                await self._log_action("auto_heal", result)
```

#### 3. MorningSummaryJob (src/night_watch/summary.py)

```python
class MorningSummaryJob:
    """Generate and send morning summary."""

    async def run(self):
        """Run at 06:00 Israel time."""
        # 1. Query last 24h of activity
        activities = await self._get_activities(hours=24)

        # 2. Aggregate stats
        summary = self._aggregate(activities)

        # 3. Format Hebrew message
        message = self._format_hebrew(summary)

        # 4. Send via Telegram
        await self._send_telegram(message)
```

#### 4. Railway Cron Configuration

```toml
# railway.toml for night-watch service
[deploy]
startCommand = "python -m src.night_watch.main"

[[crons]]
name = "night-watch-hourly"
schedule = "0 22,23,0,1,2,3,4 * * *"  # 00:00-06:00 Israel (UTC+2)
command = "python -m src.night_watch.service"

[[crons]]
name = "morning-summary"
schedule = "0 4 * * *"  # 06:00 Israel (04:00 UTC)
command = "python -m src.night_watch.summary"
```

### Safety Guardrails

| Guardrail | Implementation |
|-----------|----------------|
| Confidence threshold | Auto-heal only if confidence > 80% |
| Rate limiting | Max 3 auto-heal actions per night |
| Kill switch | `NIGHT_WATCH_ENABLED=false` env var |
| Audit log | All actions logged to PostgreSQL |
| Alert on failure | Telegram alert if health check fails 3x |

### Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Morning summaries sent | 0/week | 7/week |
| Autonomous actions logged | 0/night | 1-5/night |
| Anomalies detected | unknown | tracked |
| Mean time without intervention | 0 hours | 8 hours |

---

## Alternatives Considered

### Alternative A: Do Nothing
- **Pros**: Zero risk, zero effort
- **Cons**: System remains "dead code", user frustration continues
- **Rejected**: Does not address the core problem

### Alternative B: Passive Monitoring Only
- **Pros**: Simple, safe, quick to implement
- **Cons**: System still doesn't "do" anything
- **Rejected**: Doesn't fulfill "system works while I sleep" requirement

### Alternative D: Full Claude Agent 24/7
- **Pros**: Maximum autonomy
- **Cons**: High API costs, complex, high risk
- **Rejected**: Overkill for current needs

---

## Consequences

### Positive
- System becomes "alive" - operates autonomously overnight
- User gets daily visibility into system health
- Existing code finally gets used (MonitoringLoop, AutonomousController)
- Foundation for future autonomy expansion

### Negative
- New service to maintain (night-watch)
- Potential for false positive auto-healing
- Railway costs increase slightly (cron jobs)

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Auto-heal causes damage | 80% confidence threshold + rate limiting |
| Summary spam | Once daily at 06:00 only |
| Service failure unnoticed | Alert if 3 consecutive health checks fail |

---

## Implementation Checklist

### Phase 1: Activity Logging (Foundation)
- [ ] Create `activity_log` table migration
- [ ] Create `src/night_watch/__init__.py`
- [ ] Implement `ActivityLogger` class
- [ ] Add tests

### Phase 2: Night Watch Service
- [ ] Implement `NightWatchService`
- [ ] Integrate with `MonitoringLoop`
- [ ] Add Railway cron configuration
- [ ] Deploy to Railway

### Phase 3: Morning Summary
- [ ] Implement `MorningSummaryJob`
- [ ] Add Telegram integration
- [ ] Add Hebrew message formatting
- [ ] Deploy and test

### Phase 4: Auto-Healing
- [ ] Integrate with `AutonomousController`
- [ ] Add confidence-based triggers
- [ ] Add rate limiting
- [ ] Test with simulated anomalies

---

## Update Log

| Date | Update | Evidence |
|------|--------|----------|
| 2026-01-22 | ADR created | This document |

---

## References

- ADR-003: Railway Autonomous Control Architecture
- ADR-008: Robust Automation Strategy
- `src/monitoring_loop.py` (607 lines)
- `src/autonomous_controller.py` (954 lines)
- `src/harness/scheduler.py` (388 lines)
