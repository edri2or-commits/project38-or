# ADR-014: Smart Email Agent with Telegram Integration

## Status
**APPROVED** - 2026-01-23
**Phase 4 IN PROGRESS** - 2026-01-24

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

### v2.0 LangGraph Refactor ✅ COMPLETE (2026-01-23)
New architecture using LangGraph state machine:
- [x] `src/agents/smart_email/graph.py` - LangGraph state machine (FETCH→CLASSIFY→FORMAT→SEND)
- [x] `src/agents/smart_email/state.py` - TypedDict state, Priority/Category enums
- [x] `src/agents/smart_email/persona.py` - Hebrish prompts and templates
- [x] `src/agents/smart_email/nodes/classify.py` - Haiku LLM + regex classification
- [x] `src/agents/smart_email/nodes/format_rtl.py` - RTL Telegram formatting
- [x] `src/agents/smart_email/nodes/research.py` - Web research for P1/P2 emails
- [x] `src/agents/smart_email/nodes/history.py` - Sender history lookup
- [x] `src/agents/smart_email/nodes/draft.py` - Draft reply generation
- [x] Dependencies: `langgraph>=0.2.0`, `openai>=1.0.0`

### Tests & CI ✅ COMPLETE (2026-01-24)
- [x] `tests/test_smart_email.py` - 38 tests covering all nodes and graph
- [x] `.github/workflows/daily-email-agent.yml` - Updated to use v2.0 LangGraph
- [x] Workflow triggered successfully via `workflow_dispatch` (Run #21312936232)

### Phase 4: Full Capabilities 🔄 IN PROGRESS (2026-01-24)

**Goal**: Make the agent production-ready with zero missed emails and full interactivity.

#### 4.1 Proof of Completeness (Anti-Miss System) ✅ COMPLETE
- [x] `src/agents/smart_email/nodes/verify.py` - Verification node (153 lines)
  - Gmail count vs processed count comparison
  - Audit log with every email ID (all_fetched_ids, all_processed_ids)
  - Report: "Processed X of Y, missed: [list]"
  - is_complete property and summary_hebrew() method
- [x] `EmailState.verification` field with:
  ```python
  @dataclass
  class VerificationResult:
      gmail_total: int          # Total emails from Gmail API
      processed_count: int      # Actually processed
      skipped_system: int       # System emails filtered
      skipped_duplicates: int   # Duplicate emails skipped
      missed_ids: list[str]     # IDs that weren't processed
      verified: bool            # True if gmail_total == processed + skipped
  ```
- [x] Telegram footer: "🔍 ✅ 23/23 מיילים נסרקו (0 פוספסו)"
- [x] 10 unit tests in `tests/test_smart_email.py::TestVerificationNode`

#### 4.2 Full Email Body Reading
- [ ] Add `gmail_get_message(id)` tool to MCP Gateway
- [ ] Read full body instead of snippet (500 chars → full)
- [ ] Update `classify.py` to use full body for classification
- [ ] Better context for research and drafts

#### 4.3 Attachment Handling
- [ ] `src/agents/smart_email/nodes/attachments.py` - New node
- [ ] Extend `EmailItem` with:
  ```python
  attachments: list[AttachmentInfo] = field(default_factory=list)

  @dataclass
  class AttachmentInfo:
      id: str
      filename: str
      mime_type: str
      size: int
      download_url: str  # Pre-signed or MCP tool call
  ```
- [ ] Add `gmail_get_attachment(message_id, attachment_id)` to MCP Gateway
- [ ] List attachments in Telegram output with download buttons

#### 4.4 PDF & Document Processing
- [ ] Add `pdfplumber` or `PyPDF2` to requirements
- [ ] Extract text from PDF attachments
- [ ] Identify forms (שדות למילוי, checkboxes)
- [ ] Extract deadlines from document text

#### 4.5 OCR for Images & Scanned Documents
- [ ] Integrate Google Vision API (already have GCP access)
- [ ] Or use `pytesseract` for local OCR
- [ ] Process image attachments (JPG, PNG)
- [ ] Extract text from scanned forms

#### 4.6 Telegram Inline Keyboard (Interactive Buttons)
- [ ] Update Telegram bot to support inline keyboards
- [ ] Per-email buttons:
  ```
  [📖 הצג עוד] [✏️ טיוטה] [📥 ארכיון] [🔗 קבצים]
  ```
- [ ] Callback handlers for each button
- [ ] Expand email → show full body + history + research
- [ ] Draft button → show pre-written reply for approval
- [ ] Files button → list attachments with download links

#### 4.7 Sender History Display
- [ ] Add history summary to Telegram output:
  ```
  🔄 שולח מוכר: 15 מיילים קודמים
  📅 אחרון: לפני 3 ימים
  📌 נושאים: חשבוניות, תשלומים
  ```
- [ ] Relationship badge: 🆕 חדש | 🔄 חוזר | ⭐ תכוף

#### 4.8 Smart Form Assistance
- [ ] Identify fillable forms in attachments
- [ ] Extract form fields and their types
- [ ] Pre-fill with known user data (from preferences)
- [ ] Present as interactive Telegram message:
  ```
  📝 טופס 101 - ביטוח לאומי
  ├── שם: [אור ישראלי] ✅
  ├── ת.ז: [*****1234] ✅
  ├── תאריך: [למלא]
  └── [📤 פתח טופס מלא]
  ```

#### 4.9 Verification Tests
- [ ] `tests/test_email_completeness.py` - Integration tests
  - Mock Gmail with 50 emails
  - Verify all 50 processed or explicitly skipped
  - Zero in `missed_ids`
- [ ] `tests/test_attachments.py` - Attachment handling tests
- [ ] `tests/test_telegram_buttons.py` - Interactive button tests

#### 4.10 Sender Intelligence (Long-term Memory) ✅ COMPLETE
- [x] `src/agents/smart_email/memory/` - Memory layer module (3 files, 500+ lines)
  - `types.py` - Memory dataclasses:
    - `SenderProfile`: Complete sender understanding (relationship, patterns, notes)
    - `InteractionRecord`: Individual email interaction history
    - `ThreadSummary`: Email thread summaries
    - `ConversationContext`: Telegram conversation state
    - `MemoryType`: Semantic/Episodic/Procedural (based on CoALA paper)
    - `RelationshipType`: new/occasional/recurring/frequent/vip
  - `store.py` - PostgreSQL-backed memory store (300+ lines):
    - 5 tables: sender_profiles, interaction_records, thread_summaries, conversation_contexts, action_rules
    - Full CRUD operations with asyncpg
    - Pattern learning (typical_priority, typical_urgency)
    - Context building for LLM prompts
  - `__init__.py` - Module exports
- [x] `src/agents/smart_email/nodes/memory.py` - Memory nodes (200+ lines)
  - `memory_enrich_node`: Enriches emails with sender context before classification
  - `memory_record_node`: Records interactions after processing
  - `get_sender_badge()`: Emoji badges per relationship type
  - `format_sender_context_hebrew()`: Hebrew context for Telegram
- [x] Graph integration:
  - New flow: FETCH → MEMORY_ENRICH → CLASSIFY → ... → VERIFY → MEMORY_RECORD → FORMAT → SEND
  - `enable_memory` parameter for SmartEmailGraph
  - Graceful fallback when DATABASE_URL not set
- [x] Memory works without breaking existing functionality (disabled without PostgreSQL)

#### 4.11 Conversational Telegram Interface ✅ COMPLETE
- [x] `src/agents/smart_email/conversation/` - Conversation module (3 files, 800+ lines)
  - `intents.py` - Intent classification (300+ lines):
    - 7 intent types: EMAIL_QUERY, SENDER_QUERY, ACTION_REQUEST, SUMMARY_REQUEST, HELP_REQUEST, INBOX_STATUS, GENERAL
    - 10 action types: REPLY, FORWARD, ARCHIVE, MARK_READ, MARK_IMPORTANT, SNOOZE, LABEL, DELETE, APPROVE, REJECT
    - Hebrew-aware regex patterns with entity extraction
    - Confidence scoring and entity extraction
  - `handler.py` - Conversation handler (400+ lines):
    - `ConversationHandler` class with memory integration
    - Intent routing to specialized handlers
    - Action confirmation flow with pending actions
    - Context-aware responses using memory layer
  - `__init__.py` - Module exports
- [x] Natural language queries: "מה עם המייל מדני?" → Looks up sender in memory
- [x] Action requests: "שלח לו שאני מאשר" → Queues for confirmation
- [x] Context persistence via memory layer (ConversationContext)
- [x] 20 unit tests in `tests/test_smart_email.py::TestConversation`

#### 4.12 Action System with Approval (Complete)
- [x] `src/agents/smart_email/actions/types.py` - ActionRequest, ActionResult, AuditRecord types
- [x] `src/agents/smart_email/actions/executor.py` - Gmail API action execution via MCP Gateway
- [x] `src/agents/smart_email/actions/approval.py` - ApprovalManager with timeout, keyboard options
- [x] Supported actions: reply, forward, archive, label, snooze, star, trash, delete
- [x] Approval flow: AI proposes → User sees Hebrew proposal → Telegram buttons → Execute
- [x] Audit log for compliance (AuditRecord, to_log_entry, format_audit_log_hebrew)
- [x] Undo capability for reversible actions (archive, label, star)
- [x] 24 unit tests in `tests/test_smart_email.py::TestActionSystem`

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
| 2026-01-24 | Added 38 unit tests (`tests/test_smart_email.py`) | Claude |
| 2026-01-24 | Updated workflow to use v2.0 LangGraph SmartEmailGraph | Claude |
| 2026-01-24 | Verified workflow runs successfully (Run #21312936232) | Claude |
| 2026-01-24 | Fixed GCP Tunnel integration (PRs #535-#541) | Claude |
| 2026-01-24 | Fixed MCP content[].text response parsing | Claude |
| 2026-01-24 | ✅ Phase 4.10 COMPLETE - Sender Intelligence (memory layer, 700+ lines) | Claude |
| 2026-01-24 | Removed unsupported unread_only parameter | Claude |
| 2026-01-24 | Added graceful SecretManager fallback | Claude |
| 2026-01-24 | Production verified (Run #21316555022) ✅ | Claude |
| 2026-01-24 | Added Phase 4: Full Capabilities - attachments, OCR, buttons, proof of completeness | Claude |
| 2026-01-24 | ✅ Phase 4.1 COMPLETE - Proof of Completeness (verify.py, VerificationResult, 10 tests) | Claude |
| 2026-01-24 | ✅ Phase 4.11 COMPLETE - Conversational Telegram (conversation module, 800+ lines, 20 tests) | Claude |
