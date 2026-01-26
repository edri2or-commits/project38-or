# ADR-016: n8n Daily Learning Agent

**Date**: 2026-01-25
**Status**: Implemented
**Deciders**: User (edri2or-commits), Claude AI Agent
**Tags**: n8n, automation, learning, telegram, scheduled-tasks

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

### Phase 1: API Endpoint ✅
- [x] Add `format_hebrew_summary()` function to `src/api/routes/learning.py` (PR #618)
- [x] Add `GET /api/learning/daily-insights` endpoint (PR #618)
- [ ] Add tests for new endpoint (deferred)
- [x] Deploy to Railway (automatic via merge)

### Phase 2: n8n Workflow ✅
- [x] Create workflow JSON (`docs/n8n/daily-learning-summary.json`)
- [x] Import to n8n via `import-n8n-workflow.yml` (Run #5, #6, #7)
- [x] Configure Schedule Trigger (07:00 UTC = 09:00 Israel)
- [x] Configure HTTP Request node
- [x] Add manual webhook trigger (PR #629)
- [x] Configure Telegram credentials via `setup-n8n-telegram.yml` (PR #632, Run #1)

### Phase 3: Activation ✅
- [x] Workflow activated via setup workflow
- [x] Telegram credentials configured automatically
- [x] TELEGRAM_CHAT_ID set in Railway
- [ ] Monitor for 3 days

---

## Update Log

| Date | Update | Evidence |
|------|--------|----------|
| 2026-01-25 | ADR created via adr-architect skill | This document |
| 2026-01-25 | Phase 1 complete: API endpoint added | PR #618 |
| 2026-01-26 | Phase 2 complete: Workflow imported to n8n | Run #5, #6 of import-n8n-workflow.yml |
| 2026-01-26 | Fixed import workflow - removed read-only 'active' field | PR #625, #626 |
| 2026-01-26 | Status updated to Implemented | Issue #627 |
| 2026-01-26 | Added manual webhook trigger | PR #629, Run #7 |
| 2026-01-26 | Created automated Telegram setup workflow | PR #632 |
| 2026-01-26 | Phase 3 complete: Telegram credentials configured, workflow activated | Run #1 of setup-n8n-telegram.yml |

---

## GitHub Workflows Created

| Workflow | Purpose | Usage |
|----------|---------|-------|
| `import-n8n-workflow.yml` | Import workflow JSON to n8n | `workflow_dispatch` with file path |
| `setup-n8n-telegram.yml` | Configure Telegram credentials in n8n | `workflow_dispatch` (one-time setup) |

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
