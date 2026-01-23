# ADR-014: Smart Email Agent with Telegram Integration

## Status
**APPROVED** - 2026-01-23

## Context

The user needs an intelligent email agent that:
1. Scans Gmail inbox every morning
2. Identifies bureaucracy, important items, and required tasks
3. Researches email history and context
4. Investigates relevant external websites (government, banks, etc.)
5. Delivers friendly summaries to Telegram
6. Is ACTIVE (suggests actions, drafts replies) not passive
7. Understands calendar context and schedule
8. Presents forms in smart, accessible format

### Key Requirements (User-Specified)
- **Does NOT auto-reply** - only suggests and writes drafts for approval
- **Does NOT auto-pay** - only presents payment info accessibly
- **Does NOT auto-submit forms** - extracts and presents form data
- **DOES understand schedule** - integrates with Google Calendar
- **DOES research** - investigates external websites per email

### Research Findings (2026 Best Practices)

| Pattern | Description | Source |
|---------|-------------|--------|
| Sub-agent Architecture | Break complex tasks into specialized agents | Claude Agent SDK |
| Persistent Context Memory | Remember senders, conversation history | n8n AI Email Triage |
| MCP as Middleware | Secure OAuth handling, no credential exposure | Klavis Guide |
| Telegram Approval Flow | AI proposes, human approves | n8n Workflows |
| Browser Automation | Playwright/Skyvern for form extraction | Skyvern Government |

## Decision

Build a **Smart Email Agent** with the following architecture:

### Architecture: Multi-Agent System

```
┌─────────────────────────────────────────────────────────────┐
│  EmailAgent (Orchestrator)                                  │
│  src/agents/email_agent.py                                  │
├─────────────────────────────────────────────────────────────┤
│  Sub-Agents:                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Classifier   │  │ Historian    │  │ ActionPlanner│      │
│  │ P1-P4 + Type │  │ Past threads │  │ What to do   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Researcher   │  │ DraftWriter  │  │ FormExtractor│      │
│  │ Web lookup   │  │ Reply drafts │  │ Smart forms  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Email Categories

| Category | Hebrew | Description | Priority |
|----------|--------|-------------|----------|
| BUREAUCRACY | בירוקרטיה | Government, taxes, official letters | P1 |
| FINANCE | כספים | Banks, payments, invoices | P1 |
| URGENT | דחוף | Deadlines within 48h | P1 |
| CALENDAR | יומן | Meetings, appointments | P2 |
| ACTION_REQUIRED | דורש פעולה | Tasks, requests | P2 |
| INFORMATIONAL | מידע | Newsletters, updates | P3 |
| PROMOTIONAL | פרסום | Marketing, sales | P4 |

### Output Format (Telegram)

```markdown
🌅 *סיכום מיילים - יום שלישי 23/01/2026*

📊 *סטטיסטיקה:*
• 12 מיילים חדשים (3 חשובים, 2 דחופים)
• לו"ז היום: 2 פגישות (10:00, 14:30)

━━━━━━━━━━━━━━━━━━━━━━

🔴 *דחוף (P1):*

1️⃣ **ביטוח לאומי** - דרישת מסמכים
   📅 דדליין: 25/01 (עוד יומיים!)
   📝 נדרש: אישור תושב + צילום ת.ז
   🔗 [קישור לטופס](https://...)
   💡 *הצעה:* הכנתי לך את הטופס מלא, רק צריך לצרף מסמכים

2️⃣ **בנק לאומי** - אישור הלוואה
   💰 סכום: ₪50,000
   ⏰ תוקף ההצעה: 30/01
   📋 *סקיצת תשובה מוכנה* ← /draft_1

━━━━━━━━━━━━━━━━━━━━━━

🟡 *דורש פעולה (P2):*

3️⃣ **משרד הפנים** - חידוש דרכון
   📅 התור שלך: 02/02 ב-09:30
   📍 לשכת רמת גן
   📝 מסמכים נדרשים: [רשימה]

━━━━━━━━━━━━━━━━━━━━━━

📬 *מידע (P3-P4):* 7 מיילים נוספים
[הצג הכל →]
```

### Safety Rules (Non-Negotiable)

1. **NEVER send emails automatically** - only draft for approval
2. **NEVER make payments** - only present payment info
3. **NEVER submit forms** - only pre-fill and present
4. **ALWAYS show sources** - link to original email
5. **ALWAYS allow override** - user can dismiss suggestions

### Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Scheduling | Railway Cron + GitHub Actions | Redundancy, already deployed |
| Gmail Access | MCP Gateway (workspace tools) | Already working, OAuth handled |
| Calendar | MCP Gateway (calendar_list_events) | Same integration |
| Web Research | WebFetch tool | Built into Claude Code |
| LLM | LiteLLM Gateway (claude-sonnet) | Multi-model fallback |
| Telegram | Existing bot /send endpoint | Already deployed |
| Forms | Playwright browser (optional) | For deep extraction |

### Schedule

- **Daily Run**: 07:00 Israel Time (05:00 UTC)
- **Lookback**: 24 hours (newer_than:1d)
- **Timeout**: 5 minutes max
- **Retry**: 3 attempts with exponential backoff

## Implementation Plan

### Phase 1: Core Agent ✅ COMPLETE (2026-01-23)
- [x] `src/agents/email_agent.py` - Main orchestrator (500+ lines)
- [x] Email classification (P1-P4 + categories)
- [x] Basic Telegram formatting
- [x] GitHub workflow for daily trigger
- [x] Calendar context integration

### Phase 2: Intelligence ✅ COMPLETE (2026-01-23)
- [x] `src/agents/email_history.py` - History lookup (250+ lines)
- [x] `src/agents/draft_generator.py` - Draft replies (400+ lines)
- [x] `src/agents/web_researcher.py` - Web research (350+ lines)
- [x] Smart action suggestions via LLM
- [x] `run_with_research()` method for full Phase 2

### Phase 3: Advanced Features ✅ COMPLETE (2026-01-23)
- [x] `src/agents/form_extractor.py` - Form extraction and pre-filling (500+ lines)
- [x] `src/agents/deadline_tracker.py` - Deep deadline tracking with reminders (550+ lines)
- [x] `src/agents/user_preferences.py` - Learning from user feedback (450+ lines)
- [x] `src/agents/task_integration.py` - Task management integration (550+ lines)

## Consequences

### Positive
- Morning inbox zero feeling without manual work
- Never miss bureaucratic deadlines
- Smart suggestions save hours per week
- Calendar-aware prioritization
- Safe (no auto-actions without approval)

### Negative
- Requires LLM API calls (cost ~$0.10/day estimated)
- Depends on MCP Gateway availability
- May need tuning for Hebrew email parsing

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Missing urgent email | P1 alerts sent immediately, not batched |
| Wrong classification | User feedback loop for learning |
| MCP Gateway down | Fallback to direct API calls |
| Cost overrun | Budget limits in LiteLLM Gateway |

## References

- [n8n AI Email Triage](https://n8n.io/workflows/3968-ai-email-triage-and-alert-system-with-gpt-4-and-telegram-notifications/)
- [AI-Telegram-Assistant](https://github.com/AIXerum/AI-Telegram-Assistant)
- [Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Skyvern Government Forms](https://www.skyvern.com/government)
- [MCP Guide 2026](https://generect.com/blog/what-is-mcp/)

## Update Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-23 | Initial ADR created | Claude |
| 2026-01-23 | Phase 1 completed - Core agent | Claude |
| 2026-01-23 | Phase 2 completed - Intelligence (history, drafts, research) | Claude |
| 2026-01-23 | Phase 3 completed - Advanced features (forms, deadlines, preferences, tasks) | Claude |
