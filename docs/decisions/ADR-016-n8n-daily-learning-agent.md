# ADR-016: n8n Daily Learning Agent

**Date**: 2026-01-25
**Status**: BLOCKED - n8n API Authentication Failure
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: n8n, automation, learning, telegram, scheduled-tasks

> ⚠️ **Blocking Issue (2026-01-26)**: n8n API returns HTTP 401 Unauthorized.
> All workflow imports fail. Dashboard is empty. See [Blocking Issue](#blocking-issue) section.

---

## Context

### User Request

> "אני רוצה סוכן ב N8N שיפעל אוטומטית פעם ביום ויסרוק את המערכת והמטרה שלו זה לשפר את המערכת ע"י למידה מהצלחות."

### Existing Infrastructure

The system already has extensive learning infrastructure:

| Component | Location | Lines | Purpose |
|-----------|----------|-------|---------|
| `LearningService` | `src/learning_service.py` | 707 | Record actions, calculate success rates, generate insights |
| `LearnInsightAgent` | `src/background_agents/learn_insight_agent.py` | 386 | Analyze GitHub Actions history, generate strategic insights |
| `background-agents.yml` | `.github/workflows/` | 240 | Scheduled execution (every 8 hours) |

**Gap identified**: Insights are generated but not delivered to user via Telegram in a daily summary format.

### Related ADRs

- **ADR-013**: Night Watch - Similar concept but uses Railway Cron (Status: Proposed)
- **ADR-010**: Multi-LLM Routing - LiteLLM Gateway used by LearnInsightAgent

---

## Decision

**Create n8n workflow that calls existing learning infrastructure and sends daily summary to Telegram.**

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  n8n Workflow: "Daily Learning Summary"                         │
│                                                                 │
│  ┌─────────────┐                                               │
│  │  Schedule   │──┐   ┌─────────────┐    ┌───────┐   ┌──────┐ │
│  │  Trigger    │  │   │ HTTP Request│    │  If   │   │ Tele │ │
│  │  (07:00UTC) │  ├──▶│ GET /api/   │───▶│ has   │──▶│ gram │ │
│  └─────────────┘  │   │ learning/   │    │ data? │   │      │ │
│                   │   │ daily-      │    └───────┘   └──────┘ │
│  ┌─────────────┐  │   │ insights    │        │               │
│  │  Webhook    │──┘   └─────────────┘        ▼               │
│  │  Trigger    │                         ┌──────┐            │
│  │  (manual)   │                         │ Skip │            │
│  └─────────────┘                         └──────┘            │
└─────────────────────────────────────────────────────────────────┘

Triggers:
- Schedule: 07:00 UTC (09:00 Israel) - automatic daily
- Webhook: POST /webhook/daily-learning - manual anytime
```
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Endpoint (NEW)                                         │
│  GET /api/learning/daily-insights                               │
│                                                                 │
│  1. Call LearningService.get_learning_summary(days=1)          │
│  2. Call LearningService.generate_insights(days=1)             │
│  3. Format response with Hebrew summary                         │
│  4. Return JSON with insights + stats                           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Existing Infrastructure (NO CHANGES)                           │
│  ├── LearningService (src/learning_service.py)                 │
│  ├── LearnInsightAgent (runs every 8h via GitHub Actions)      │
│  └── PostgreSQL action_records table                            │
└─────────────────────────────────────────────────────────────────┘
```

### Why n8n (not GitHub Actions)

| Aspect | GitHub Actions | n8n |
|--------|---------------|-----|
| Visual editing | ❌ YAML only | ✅ Drag & drop |
| Quick iteration | ❌ Commit per change | ✅ Instant save |
| Telegram integration | ⚠️ Manual API calls | ✅ Native node |
| User preference | ❌ | ✅ Explicitly requested |

### Components to Build

#### 1. API Endpoint (src/api/routes/learning.py - MODIFY)

```python
@router.get("/daily-insights")
async def get_daily_insights():
    """Get daily learning insights for n8n workflow.

    Returns formatted insights suitable for Telegram message.
    Called by n8n Daily Learning Summary workflow.
    """
    service = LearningService(database_url=get_database_url())
    await service.initialize()

    summary = await service.get_learning_summary(days=1)
    insights = await service.generate_insights(days=1)

    # Format Hebrew message
    message = format_hebrew_summary(summary, insights)

    return {
        "success": True,
        "message": message,
        "stats": summary,
        "insights_count": len(insights),
        "generated_at": datetime.now(UTC).isoformat()
    }
```

#### 2. n8n Workflow JSON

```json
{
  "name": "Daily Learning Summary",
  "nodes": [
    {
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": {
        "rule": {
          "interval": [{"field": "hours", "hoursInterval": 24}]
        },
        "triggerTimes": {"item": [{"hour": 7}]}
      },
      "position": [250, 300]
    },
    {
      "name": "Get Learning Insights",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://or-infra.com/api/learning/daily-insights",
        "method": "GET"
      },
      "position": [450, 300]
    },
    {
      "name": "Send Telegram",
      "type": "n8n-nodes-base.telegram",
      "parameters": {
        "chatId": "={{$env.TELEGRAM_CHAT_ID}}",
        "text": "={{$json.message}}",
        "additionalFields": {"parse_mode": "Markdown"}
      },
      "position": [650, 300]
    }
  ],
  "connections": {
    "Schedule Trigger": {"main": [[{"node": "Get Learning Insights"}]]},
    "Get Learning Insights": {"main": [[{"node": "Send Telegram"}]]}
  }
}
```

#### 3. Hebrew Message Format

```
📊 *סיכום למידה יומי - {date}*

*סטטיסטיקות:*
• פעולות שנרשמו: {total_actions}
• שיעור הצלחה: {success_rate}%
• מגמה: {trend}

*תובנות ({insights_count}):*
{for insight in insights:}
• {insight.title}
  └ {insight.description}
{endfor}

*עדיפות מובילה:*
{top_priority}

_נוצר אוטומטית ב-{time}_
```

---

## Consequences

### Positive

- User receives daily learning summary via Telegram (as requested)
- Uses existing tested infrastructure (LearningService)
- Visual workflow in n8n for easy modification
- Minimal new code required (~50 lines)

### Negative

- Depends on both n8n AND Railway API (two failure points)
- n8n requires TELEGRAM_CHAT_ID environment variable

### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| n8n service down | Low | No summary | Add fallback in background-agents.yml |
| Empty insights | Medium | Useless message | Skip sending if insights_count == 0 |
| API timeout | Low | Partial data | Set 30s timeout, return cached if fail |

---

## Implementation Checklist

## Blocking Issue

**Discovered**: 2026-01-26 08:40 UTC
**Status**: UNRESOLVED

### Problem Statement

n8n API returns HTTP 401 Unauthorized for all authenticated requests:

```
HTTP Status: 401
Endpoint: GET /api/v1/workflows
Header: X-N8N-API-KEY: [key from GCP Secret Manager]
```

### Evidence

| Check | Result | Workflow Run |
|-------|--------|--------------|
| n8n health | ✅ `{"status":"ok"}` HTTP 200 | check-n8n-workflows.yml Run #5 |
| n8n workflows API | ❌ HTTP 401 | check-n8n-workflows.yml Run #1-#5 (all failed) |
| Import workflow | ❌ Fails at import step | import-n8n-workflow.yml Run #9, #10 |
| User dashboard | ❌ Empty | User report: "הדשבורד ריק לגמרי" |

### Remediation Attempts

| Action | Result | Evidence |
|--------|--------|----------|
| Generate new API key | ✅ Completed | reset-n8n-api-key.yml Run #1 |
| Update GCP Secret Manager | ✅ Completed | reset-n8n-api-key.yml Run #1 |
| Update Railway env vars | ✅ Completed | deploy-n8n.yml Run #28, #29 |
| Redeploy n8n service | ✅ Completed | deploy-n8n.yml Run #28, #29 |
| Debug API auth | ✅ Completed | debug-n8n-auth.yml Run #1 |
| **401 still occurs** | ❌ Not fixed | check-n8n-workflows.yml Run #5 (09:05 UTC) |

### Root Cause Analysis

**Status**: UNKNOWN

Possible causes (not yet verified):
1. n8n not reading N8N_API_KEY environment variable on startup
2. Railway env var caching (redeploy not applying new values)
3. n8n version incompatibility with API key authentication

### Impact

- ❌ Cannot import workflows to n8n via API
- ❌ Workflow not visible in n8n dashboard
- ❌ Daily Learning Summary not operational
- ✅ API endpoint `/api/learning/daily-insights` works (tested via PR #618)

### Next Steps

1. Access n8n UI directly to verify container state
2. Check Railway logs for n8n startup errors
3. Consider alternative: manual workflow creation via UI

---

### Phase 1: API Endpoint ✅
- [x] Add `format_hebrew_summary()` function to `src/api/routes/learning.py` (PR #618)
- [x] Add `GET /api/learning/daily-insights` endpoint (PR #618)
- [ ] Add tests for new endpoint (deferred)
- [x] Deploy to Railway (automatic via merge)

### Phase 2: n8n Workflow ⚠️ BLOCKED
- [x] Create workflow JSON (`docs/n8n/daily-learning-summary.json`)
- [ ] **BLOCKED** Import to n8n via `import-n8n-workflow.yml`
  - Run #5, #6, #7 reported success but workflow NOT visible in n8n
  - Run #9, #10 explicitly failed at import step
  - API returns 401 Unauthorized
- [ ] Configure Schedule Trigger (blocked - workflow not imported)
- [ ] Configure HTTP Request node (blocked - workflow not imported)
- [x] Add manual webhook trigger to JSON (PR #629)
- [ ] **BLOCKED** Configure Telegram credentials - workflow must exist first

### Phase 3: Activation ❌ NOT STARTED
- [ ] Workflow activated - **BLOCKED** (workflow doesn't exist in n8n)
- [ ] Telegram credentials configured - **BLOCKED**
- [ ] TELEGRAM_CHAT_ID set - Railway var exists but not usable
- [ ] Monitor for 3 days - **BLOCKED**

---

## Update Log

| Date | Update | Evidence |
|------|--------|----------|
| 2026-01-25 | ADR created via adr-architect skill | This document |
| 2026-01-25 | Phase 1 complete: API endpoint added | PR #618 |
| 2026-01-26 07:28 | Import workflow runs succeeded (reported) | Run #5, #6, #7 |
| 2026-01-26 07:15 | Fixed import workflow - removed read-only 'active' field | PR #625, #626 |
| 2026-01-26 08:09 | Added manual webhook trigger to JSON | PR #629 |
| 2026-01-26 08:09 | Created automated Telegram setup workflow | PR #632 |
| 2026-01-26 08:14 | Status incorrectly marked as Implemented | Issue #627 comment |
| **2026-01-26 08:27** | **BLOCKING ISSUE DISCOVERED** | User: "הדשבורד ריק לגמרי" |
| 2026-01-26 08:27 | Import workflow runs #8, #9, #10 fail at import step | n8n API returns 401 |
| 2026-01-26 08:40 | Created diagnostic workflow | PR #639 |
| 2026-01-26 08:51 | API key reset attempted | PR #641, Run #1 |
| 2026-01-26 09:00 | Multiple redeploys attempted | deploy-n8n.yml Runs #28, #29 |
| 2026-01-26 09:05 | **401 persists after all remediation** | check-n8n-workflows.yml Run #5 |
| 2026-01-26 09:09 | Debug workflow created | PR #644 |
| 2026-01-26 09:15 | **Status corrected to BLOCKED** | This update (Truth Protocol) |

---

## GitHub Workflows Created

| Workflow | Purpose | Status |
|----------|---------|--------|
| `import-n8n-workflow.yml` | Import workflow JSON to n8n | ⚠️ Fails with 401 |
| `setup-n8n-telegram.yml` | Configure Telegram credentials in n8n | ⚠️ Blocked (workflow must exist) |
| `check-n8n-workflows.yml` | Diagnostic: list n8n workflows | ✅ Works (shows 401) |
| `reset-n8n-api-key.yml` | Generate and sync new API key | ✅ Works (doesn't fix 401) |
| `debug-n8n-auth.yml` | Debug API authentication | ✅ Works |
| `deploy-n8n.yml` | Deploy/configure n8n on Railway | ✅ Works |

### Manual Trigger URL

```bash
# Trigger workflow anytime
curl -X POST https://n8n-production-2fe0.up.railway.app/webhook/daily-learning
```

---

## References

- ADR-013: Night Watch - Autonomous Overnight Operations
- `src/learning_service.py` (707 lines)
- `src/background_agents/learn_insight_agent.py` (386 lines)
- n8n Documentation: https://docs.n8n.io/
