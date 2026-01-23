# ADR-014: Smart Email Agent Architecture

**Status**: Proposed
**Date**: 2026-01-23
**Deciders**: @edri2or
**Research Sources**: Deep Research x3 (verified against external sources)

## Context and Problem Statement

The current email agent (`src/agents/email_agent.py`) is "עלוב ביותר" (very poor) according to user feedback. It functions as a dry notification system rather than a "smart friend" that:
- Deeply understands email content
- Actively researches context (visits websites, investigates senders)
- Communicates in natural "Hebrish" (Hebrew + English code-switching)
- Reports what investigation it performed
- Works hard behind the scenes while being cost-efficient

**User Quote**: "אני רוצה לעשות את זה הכי מקצועי. חזק. בטוח. מתוחכם. חדשני. חכם. יצירתי. ויזואלי. עובד קשה מאחורי הקלעים. חסכוני. והכי טוב ואטרקטיבי ל 2026."

## Decision Drivers

1. **Professional & Sophisticated**: Enterprise-grade architecture
2. **Secure**: PII protection, audit trails
3. **Smart & Creative**: Active research, context understanding
4. **Cost-Efficient**: Intelligent model routing, caching
5. **Visual**: Rich formatting, PDF reports
6. **Hebrew-First**: Native RTL support, "Hebrish" persona
7. **2026-Ready**: Latest frameworks and patterns

## Research Synthesis (Verified Claims)

### Verified Technologies

| Technology | Verification | Source |
|------------|--------------|--------|
| **LangGraph** | ✅ `interrupt_before` for human-in-the-loop | [LangChain Docs](https://docs.langchain.com/oss/python/langgraph/interrupts) |
| **Presidio** | ✅ Microsoft PII detection framework | [GitHub](https://github.com/microsoft/presidio) |
| **Unicode RLM** | ✅ U+200F for RTL text mixing | [W3C](https://www.w3.org/TR/WCAG20-TECHS/H34.html) |
| **Tavily** | ✅ AI search API, $25M funding, 800K+ devs | [Tavily Docs](https://docs.tavily.com/documentation/api-credits) |
| **Mem0** | ✅ Memory layer, AWS partnership | [Mem0.ai](https://mem0.ai) |
| **DictaLM 2.0** | ✅ Hebrew LLM, HuggingFace | [HuggingFace](https://huggingface.co/dicta-il) |
| **GLiNER** | ✅ Zero-shot NER | [GitHub](https://github.com/urchade/GLiNER) |
| **WeasyPrint** | ✅ HTML to PDF, BSD license | [WeasyPrint.org](https://weasyprint.org/) |
| **LiteLLM** | ✅ Already deployed in project | `services/litellm-gateway/` |

### Key Insights from Research

1. **n8n = Nervous System, Not Brain**: Use n8n for I/O (triggers, webhooks) but Python for logic
2. **LangGraph > CrewAI/AutoGen**: Production-ready, state persistence, human-in-the-loop
3. **Hebrish Pattern**: Natural Israeli tech communication (מעולה → let me check the API)
4. **RTL Sandwich**: Wrap English in RLM characters for proper Telegram display
5. **Cost Routing**: Haiku for classification, Sonnet for generation, Opus for complex reasoning

## Decision

### Architecture: LangGraph State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    Smart Email Agent v2.0                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  FETCH   │───▶│ CLASSIFY │───▶│ RESEARCH │───▶│ GENERATE │  │
│  │  Emails  │    │  P1-P4   │    │  Active  │    │  Message │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │          │
│       ▼               ▼               ▼               ▼          │
│  Gmail API      LLM (Haiku)     Tavily API      LLM (Sonnet)   │
│                 + DictaLM       + MCP Tools                     │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   PII    │───▶│  FORMAT  │───▶│  VISUAL  │───▶│  SEND    │  │
│  │  Redact  │    │ Hebrish  │    │   PDF    │    │ Telegram │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │          │
│       ▼               ▼               ▼               ▼          │
│   Presidio       RTL/LRM        WeasyPrint      Telegram API   │
│   + GLiNER       + Hebrish                                      │
│                                                                  │
│  ╔══════════════════════════════════════════════════════════╗   │
│  ║  MEMORY LAYER (Mem0)                                     ║   │
│  ║  - Sender history                                        ║   │
│  ║  - User preferences                                      ║   │
│  ║  - Past decisions                                        ║   │
│  ╚══════════════════════════════════════════════════════════╝   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. Email Fetching (Existing)
- **Source**: `src/agents/gmail_client.py`
- **Status**: ✅ Already working
- **Enhancement**: Add incremental sync via Gmail History API

#### 2. Classification Node
- **Model**: Claude Haiku (cost-efficient)
- **Fallback**: DictaLM 2.0 for Hebrew-heavy content
- **Output**: P1 (Urgent) / P2 (Important) / P3 (Info) / P4 (Low/System)
- **Routing**:
  - P1 → Full research pipeline
  - P2 → Light research
  - P3-P4 → Summary only

#### 3. Active Research Node
- **Primary**: Tavily API for web searches
- **Secondary**: MCP tools for specific domains
- **Actions**:
  - Extract URLs from email → fetch via WebFetch
  - Identify sender → research company/person
  - Check attachments → summarize documents
- **Output**: Investigation report with sources

#### 4. Message Generation Node
- **Model**: Claude Sonnet (balanced quality/cost)
- **Persona**: "Smart Friend" in Hebrish
- **Template**:
  ```
  היי! 👋

  סרקתי את התיבה שלך ויש כמה דברים שחשוב שתדע:

  🔴 **דחוף**: [כותרת]
  [תקציר בעברית + פרטים באנגלית אם רלוונטי]
  📊 חקרתי ומצאתי: [investigation results]

  🟠 **חשוב**: [...]

  💡 **המלצה שלי**: [actionable advice]

  ---
  עבדתי על זה [X] שניות, בדקתי [Y] מקורות.
  ```

#### 5. PII Redaction Node
- **Primary**: Presidio (Microsoft)
- **Secondary**: GLiNER for Hebrew entities
- **Entities**: Phone, ID, credit card, address, email signatures
- **Mode**: Anonymize before logging, original for display

#### 6. RTL Formatting Node
- **Strategy**: Unicode RLM (U+200F) wrapping
- **Pattern**:
  ```python
  RLM = "\u200F"
  def hebrish_format(text):
      # Wrap English terms in RLM for proper display
      return f"{RLM}{text}{RLM}"
  ```

#### 7. Visual Report Node (Optional)
- **Tool**: WeasyPrint
- **Output**: PDF summary for archiving
- **Template**: HTML with RTL CSS

#### 8. Memory Layer
- **Tool**: Mem0 (or SQLite for MVP)
- **Stores**:
  - Sender → company mapping
  - User feedback on priorities
  - Past email patterns
  - Investigation results cache

### Typography & Accessibility (טיפוגרפיה והנגשה)

**Sources**: [Medium RTL Fix](https://medium.com/@python-javascript-php-html-css/fixing-hebrew-text-alignment-in-telegram-bot-api-e951f9039b72), [Smashing Magazine Typography](https://www.smashingmagazine.com/2022/10/typographic-hierarchies/), [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/)

#### RTL Alignment in Telegram

**Problem**: Telegram defaults to LTR, causing Hebrew text misalignment.

**Solution**: Use HTML mode with explicit `dir="rtl"`:

```python
def format_rtl_message(text: str) -> str:
    """Wrap message in RTL container for Telegram HTML mode."""
    # Use HTML parse_mode instead of Markdown
    return f'<div dir="rtl">{text}</div>'

# When sending:
response = httpx.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",  # Not Markdown!
    }
)
```

#### Visual Hierarchy Pattern

Based on [typographic hierarchy principles](https://www.smashingmagazine.com/2022/10/typographic-hierarchies/):

```
┌─────────────────────────────────────────────────────────┐
│  🌅 סיכום מיילים - 23/01/2026                          │  ← H1: Emoji + Bold
│                                                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │  ← Visual separator
│                                                         │
│  🔴 דחוף (P1)                                          │  ← H2: Color emoji + Bold
│  ┃                                                      │
│  ┃  📍 ביטוח לאומי                                     │  ← H3: Sender (bold)
│  ┃     נדרש אישור תוך 7 ימים                           │  ← Body: Subject (regular)
│  ┃     💡 חקרתי: זה טופס 101 לחידוש...                 │  ← Insight: Italic
│  ┃                                                      │
│  🟠 חשוב (P2)                                          │  ← H2
│  ┃                                                      │
│  ┃  📍 בנק לאומי                                       │
│  ┃     עדכון פרטים נדרש                                │
│  ┃                                                      │
│  🟡 מידע (P3)                                          │  ← H2
│  ┃                                                      │
│  ┃  • Amazon - הזמנה נשלחה                             │  ← Compact list
│  ┃  • LinkedIn - 3 צפיות בפרופיל                       │
│  ┃                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                         │
│  📊 עבדתי 12 שניות | בדקתי 3 מקורות                    │  ← Footer: Stats
│  _Smart Email Agent v2.0_                               │  ← Branding: Italic
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### Accessibility Standards (WCAG 2.1)

| Principle | Implementation |
|-----------|----------------|
| **Perceivable** | Color + emoji for priority (🔴🟠🟡⚪) - not color alone |
| **Understandable** | Hebrew-first, English terms in context |
| **Distinguishable** | 4.5:1 contrast ratio (Telegram dark mode safe) |
| **Screen Reader** | Structured hierarchy with H1→H2→Body flow |

#### Emoji as Visual Hierarchy

Strategic emoji usage (not decoration):

| Emoji | Semantic Meaning | Screen Reader |
|-------|------------------|---------------|
| 🔴 | P1 Urgent | "אזהרה" |
| 🟠 | P2 Important | "חשוב" |
| 🟡 | P3 Info | "מידע" |
| ⚪ | P4 Low | "נמוך" |
| 📍 | Sender marker | "מאת" |
| 💡 | AI insight | "תובנה" |
| 📊 | Statistics | "סטטיסטיקה" |
| ⏰ | Deadline | "דד-ליין" |

#### Font Considerations for PDF Reports

When generating PDF via WeasyPrint:

```css
/* RTL-first CSS */
body {
    direction: rtl;
    text-align: right;
    font-family: 'Heebo', 'Arial Hebrew', sans-serif;
    font-size: 16px; /* WCAG minimum */
    line-height: 1.6; /* Readability */
}

/* English inline */
.english-term {
    direction: ltr;
    unicode-bidi: embed;
    font-family: 'Inter', sans-serif;
}

/* Visual hierarchy */
h1 { font-size: 24px; font-weight: 700; }
h2 { font-size: 18px; font-weight: 600; color: #333; }
.insight { font-style: italic; color: #666; }
```

#### Hebrish Typography Rules

1. **Hebrew wrapper, English inline**:
   ```
   ✅ "בדקתי את ה-API ויש בעיה ב-authentication"
   ❌ "I checked the API ויש בעיה in authentication"
   ```

2. **Technical terms stay English**:
   - API, OAuth, webhook, deploy, commit
   - Never translate: "ממשק תכנות יישומים" ❌

3. **Numbers in context**:
   ```
   ✅ "יש לך 3 מיילים חדשים"
   ✅ "נותרו 7 ימים לדד-ליין"
   ```

4. **RLM sandwiching for mixed content**:
   ```python
   RLM = "\u200F"
   text = f"{RLM}בדקתי את {RLM}Railway{RLM} והכל תקין{RLM}"
   ```

### Automated Form Filling (מילוי טפסים אוטומטי)

**Sources**: [Seraphic Security - Agentic Browsers](https://seraphicsecurity.com/learn/ai-browser/top-5-agentic-browsers-in-2026-capabilities-and-security-risks/), [Playwright MCP Security](https://www.awesome-testing.com/2025/11/playwright-mcp-security), [Israel Tax Authority API](https://www.gov.il/BlobFolder/generalpage/israel-invoice-160723/he/IncomeTax_software-houses-en-040723.pdf)

#### Security Philosophy: Human-in-the-Loop (MANDATORY)

> ⚠️ **CRITICAL SAFETY RULE**: The agent NEVER submits forms automatically.
> Every form submission requires explicit human approval.

**Sources verified this is industry standard**:
- [OpenAI Operator](https://openai.com/index/introducing-operator/): "Takeover mode" for sensitive inputs
- [ChatGPT Atlas](https://seraphicsecurity.com/learn/ai-browser/top-5-agentic-browsers-in-2026-capabilities-and-security-risks/): "Watch Mode" for sensitive sites
- [Playwright MCP Security](https://www.awesome-testing.com/2025/11/playwright-mcp-security): "Human hand on the wheel" principle

```python
# LangGraph interrupt pattern for form approval
from langgraph.prebuilt import interrupt

def form_filling_node(state: EmailState) -> EmailState:
    """Extract form fields and prepare for human approval."""
    form_data = extract_form_fields(state["email"])
    pre_filled = apply_user_profile(form_data, state["user_profile"])

    # MANDATORY: Interrupt for human approval
    approval = interrupt({
        "type": "form_approval",
        "form_url": form_data["url"],
        "fields": pre_filled,
        "message": "אני מוכן למלא את הטופס הזה. לאשר?",
        "options": ["✅ אשר ושלח", "✏️ ערוך לפני שליחה", "❌ בטל"]
    })

    if approval == "approve":
        return submit_form(pre_filled)  # Only after explicit approval
    elif approval == "edit":
        return open_form_for_edit(pre_filled)
    else:
        return cancel_form(state)
```

#### Threat Model (2026 Agentic Browsers)

Based on [CyberScoop analysis](https://cyberscoop.com/agentic-ai-browsers-security-enterprise-risk/):

| Threat | Mitigation |
|--------|------------|
| **Prompt Injection** | Never trust form field names from external sources |
| **Over-Privileged Automation** | Explicit approval for every submission |
| **Hallucination-Driven Actions** | Validate all fields before showing to user |
| **Identity Mesh Vulnerabilities** | Sandboxed browser session (Browserbase) |

#### Supported Form Types

**Israeli Government Forms**:

| מוסד | Domain | API Status | Approach |
|------|--------|------------|----------|
| מס הכנסה | taxes.gov.il | ✅ OAuth2 API | Direct API if available |
| ביטוח לאומי | btl.gov.il | ❌ No API | Browser automation |
| משרד הפנים | gov.il | Partial | Hybrid |
| עיריות | Various | ❌ No API | Browser automation |

**Banks** (extra caution required):

| בנק | Approach | Safety Level |
|-----|----------|--------------|
| לאומי | View only, no actions | 🔴 Read-only |
| הפועלים | View only, no actions | 🔴 Read-only |
| דיסקונט | View only, no actions | 🔴 Read-only |

> ⚠️ **Banking forms**: Agent can ONLY read and summarize. Never fill or submit.

#### Form Field Detection

```python
from dataclasses import dataclass
from enum import Enum

class FieldType(Enum):
    TEXT = "text"
    DATE = "date"          # Hebrew date picker
    FILE = "file"          # Document upload
    CHECKBOX = "checkbox"
    ID_NUMBER = "id"       # תעודת זהות (9 digits)
    PHONE = "phone"        # Israeli format
    EMAIL = "email"
    ADDRESS = "address"    # Israeli address format
    AMOUNT = "amount"      # ₪ currency

@dataclass
class FormField:
    name: str
    field_type: FieldType
    required: bool
    value: str | None = None
    confidence: float = 0.0  # How confident we are in pre-fill

@dataclass
class DetectedForm:
    url: str
    title: str
    institution: str        # e.g., "ביטוח לאומי"
    deadline: str | None    # If mentioned in email
    fields: list[FormField]
    pre_fillable: bool      # Can we pre-fill from profile?
```

#### User Profile for Pre-filling

```python
@dataclass
class UserProfile:
    """Stored securely, used for form pre-filling."""
    # Identity
    full_name_hebrew: str       # שם מלא בעברית
    full_name_english: str      # Full name in English
    id_number: str              # תעודת זהות (encrypted)

    # Contact
    phone: str                  # 05X-XXX-XXXX
    email: str

    # Address
    city: str                   # עיר
    street: str                 # רחוב
    house_number: str           # מספר בית
    apartment: str | None       # דירה
    zip_code: str               # מיקוד

    # Banking (read-only reference, not for automation)
    bank_name: str | None       # שם הבנק
    bank_branch: str | None     # סניף
    account_number: str | None  # חשבון (encrypted)
```

#### Browser Automation Safety (Playwright MCP)

Based on [Playwright MCP Security Best Practices](https://www.awesome-testing.com/2025/11/playwright-mcp-security):

```python
# Safe Playwright configuration
playwright_config = {
    # Run in container
    "container": True,
    "image": "mcr.microsoft.com/playwright:v1.42.0",

    # Minimal permissions
    "filesystem_access": "read_only",
    "network_egress": ["gov.il", "btl.gov.il", "taxes.gov.il"],

    # No secrets in prompts
    "secrets_via_env": True,

    # Approval required
    "yolo_mode": False,  # NEVER enable in production

    # Pin version
    "mcp_version": "1.2.3",  # Not @latest
}
```

#### Form Filling Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    FORM FILLING FLOW                              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. DETECT: Email contains form link                            │
│     └─ Pattern: gov.il, btl.gov.il, taxes.gov.il               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. EXTRACT: Identify form fields                               │
│     └─ Playwright: Navigate, analyze DOM                        │
│     └─ LLM: Classify field types                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. PRE-FILL: Match with user profile                           │
│     └─ High confidence: Auto-fill                               │
│     └─ Low confidence: Suggest only                             │
│     └─ Sensitive: Show asterisks (****)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. PRESENT: Show to user in Telegram                           │
│     └─ "מצאתי טופס של ביטוח לאומי"                            │
│     └─ "מילאתי מראש: שם, ת.ז., טלפון"                         │
│     └─ "חסר: מסמך צרוף (תלוש משכורת)"                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. AWAIT APPROVAL (interrupt_before)                           │
│     └─ ✅ "אשר ושלח"                                           │
│     └─ ✏️ "פתח לעריכה" → Opens browser for manual review       │
│     └─ ❌ "בטל"                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │ User approves         │
                    ▼                       ▼
┌─────────────────────────────┐ ┌─────────────────────────────────┐
│  6a. SUBMIT (automated)     │ │  6b. OPEN BROWSER (manual)      │
│  └─ Playwright fills form   │ │  └─ Pre-filled form in browser  │
│  └─ Captures confirmation   │ │  └─ User reviews and submits    │
│  └─ Logs action             │ │  └─ Agent monitors completion   │
└───────────────────┬─────────┘ └───────────────────┬─────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. CONFIRM: Report to Telegram                                 │
│     └─ "✅ הטופס נשלח בהצלחה"                                  │
│     └─ "📋 מספר אישור: 12345678"                               │
│     └─ "📅 שמרתי תזכורת למעקב"                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Audit Trail (Mandatory)

Every form interaction is logged:

```python
@dataclass
class FormAuditEntry:
    timestamp: datetime
    form_url: str
    institution: str
    action: Literal["detected", "pre_filled", "presented", "approved", "submitted", "cancelled"]
    user_decision: str | None
    fields_filled: list[str]  # Field names only, not values
    confirmation_number: str | None
    screenshot_path: str | None  # Before submission screenshot
```

#### What We DON'T Do (Safety Boundaries)

| Action | Policy | Reason |
|--------|--------|--------|
| Submit without approval | ❌ NEVER | Core safety rule |
| Fill bank transfer forms | ❌ NEVER | Financial risk |
| Store passwords | ❌ NEVER | Security risk |
| Auto-login to sites | ❌ NEVER | Credential exposure |
| Fill medical forms | ⚠️ Read-only | Privacy sensitivity |
| Upload documents | ⚠️ Approval required | Data exposure |

### Attachment Processing (קבצים מצורפים)

**Sources**: [Google Document AI](https://cloud.google.com/document-ai), [Azure Document Intelligence](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence), [Reducto AI](https://reducto.ai/), [Mistral OCR](https://mistral.ai/news/mistral-ocr)

#### Document Types Supported

| סוג מסמך | עיבוד | שימוש |
|----------|-------|-------|
| **תעודת זהות** | OCR + Validation | Pre-fill ת.ז. field |
| **תלוש משכורת** | Table extraction | Income verification |
| **חשבונית** | Field extraction | Amount, date, vendor |
| **טופס ממולא** | Form recognition | Copy existing data |
| **מכתב ממשלתי** | Entity extraction | Deadline, reference # |
| **צילום מסמך** | Image OCR | General text |

#### Technology Stack

```python
from enum import Enum
from dataclasses import dataclass

class DocumentProcessor(Enum):
    """Choose processor based on document type and privacy."""
    GOOGLE_DOCUMENT_AI = "google"      # Best for Hebrew, cloud
    AZURE_DOCUMENT_INTEL = "azure"     # Good for forms
    MISTRAL_OCR = "mistral"            # Privacy-first, on-device option
    TESSERACT_LOCAL = "tesseract"      # Fully local, free

@dataclass
class ExtractedDocument:
    """Result of document processing."""
    document_type: str              # "teudat_zehut", "payslip", etc.
    confidence: float               # 0.0 - 1.0
    extracted_fields: dict          # {"id_number": "...", "name": "..."}
    raw_text: str                   # Full OCR text
    language: str                   # "he", "en", "mixed"
    bounding_boxes: list | None     # For visual verification
```

#### Israeli Document Patterns

```python
# תעודת זהות (Israeli ID)
ID_PATTERNS = {
    "id_number": r"\b\d{9}\b",                    # 9 digits
    "name_hebrew": r"[\u0590-\u05FF]+\s+[\u0590-\u05FF]+",
    "birth_date": r"\d{2}[./]\d{2}[./]\d{4}",
    "issue_date": r"\d{2}[./]\d{2}[./]\d{4}",
}

# תלוש משכורת (Payslip)
PAYSLIP_PATTERNS = {
    "gross_salary": r"(?:משכורת ברוטו|שכר ברוטו)[:\s]*([₪\d,\.]+)",
    "net_salary": r"(?:נטו לתשלום|סה\"?כ נטו)[:\s]*([₪\d,\.]+)",
    "employer": r"(?:מעסיק|שם החברה)[:\s]*([\u0590-\u05FF\s]+)",
    "month": r"(?:חודש|לחודש)[:\s]*(\d{1,2}[./]\d{2,4})",
}

# חשבונית (Invoice)
INVOICE_PATTERNS = {
    "invoice_number": r"(?:מס['\"]?\s*חשבונית|invoice)[:\s#]*(\d+)",
    "total": r"(?:סה\"?כ|total)[:\s]*([₪\d,\.]+)",
    "date": r"\d{2}[./]\d{2}[./]\d{4}",
    "vat": r"(?:מע\"?מ|VAT)[:\s]*([₪\d,\.]+)",
}
```

#### Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                  ATTACHMENT PROCESSING FLOW                       │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. DETECT: Email has attachment                                 │
│     └─ Check MIME type: PDF, image, document                    │
│     └─ Size check: max 10MB                                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. CLASSIFY: What document type?                               │
│     └─ Filename hints: "תלוש", "חשבונית", "ת.ז."               │
│     └─ Visual classification via LLM                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. EXTRACT: Run appropriate OCR                                │
│     └─ Hebrew: Google Document AI (best accuracy)               │
│     └─ Privacy mode: Mistral OCR (local/on-device)             │
│     └─ Tables: Azure Document Intelligence                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. VALIDATE: Check extracted data                              │
│     └─ ID number: Luhn check for Israeli ת.ז.                  │
│     └─ Dates: Parse Hebrew/Gregorian formats                    │
│     └─ Amounts: Handle ₪ and comma formatting                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. STORE: Save for form pre-fill                               │
│     └─ Encrypted storage (never plain text for PII)            │
│     └─ Link to email thread                                     │
│     └─ Expiration: 30 days                                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. PRESENT: Tell user what was found                           │
│     └─ "מצאתי תלוש משכורת - נטו: ₪8,500"                       │
│     └─ "שמרתי לשימוש בטפסים עתידיים"                           │
│     └─ "רוצה שאמחק את המסמך?"                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Privacy & Security

| Concern | Mitigation |
|---------|------------|
| **PII in cloud** | Option for local OCR (Mistral/Tesseract) |
| **Storage** | Encrypted at rest, 30-day expiration |
| **Consent** | User approves each extraction |
| **Audit** | Log what was extracted (field names only) |
| **Deletion** | User can delete extracted data anytime |

### ADHD-Friendly Design (עיצוב מותאם ADHD)

**Sources**: [UX for ADHD Students](https://din-studio.com/ui-ux-for-adhd-designing-interfaces-that-actually-help-students/), [Neurodivergent UX](https://medium.com/design-bootcamp/inclusive-ux-ui-for-neurodivergent-users-best-practices-and-challenges-488677ed2c6e), [Cognitive Load UX](https://startup-house.com/blog/cognitive-overload-ux), [ADHD Software Accessibility](https://uxdesign.cc/software-accessibility-for-users-with-attention-deficit-disorder-adhd-f32226e6037c)

#### Core Principles

> "Don't let your application cover the clock of the device... it really doesn't help when you are already having problems with time blindness."
> — [Software Accessibility for ADHD](https://uxdesign.cc/software-accessibility-for-users-with-attention-deficit-disorder-adhd-f32226e6037c)

| עיקרון | יישום |
|--------|-------|
| **צמצום עומס קוגניטיבי** | מקסימום 3 פריטים להחלטה |
| **תזכורות עדינות** | "יש משהו שממתין" לא "אתה מפגר!" |
| **מצב רגוע (Calm Mode)** | פחות צבעים, פחות אנימציות |
| **Time Blindness** | תמיד להציג שעון ומשך זמן |
| **Hyperfocus Protection** | "כבר שעה שאתה כאן" |
| **פעולה אחת ברורה** | CTA בולט אחד בכל הודעה |

#### Message Structure (ADHD-Optimized)

**Before (Overwhelming)**:
```
🌅 סיכום מיילים - 23/01/2026 09:00

📊 סטטיסטיקה:
• 15 מיילים (8 התראות מערכת הוסתרו)
• 🔴 דחוף: 2 | 🟠 חשוב: 3 | 🟡 מידע: 7 | ⚪ פרסום: 3

🔴 דחוף (P1):
  • [בירוקרטיה] ביטוח לאומי
    נדרש אישור תוך 7 ימים - טופס 101 לחידוש...
  • [כספים] בנק לאומי
    עדכון פרטים נדרש - אישור הפקדה...

🟠 חשוב (P2):
  • Amazon: הזמנה נשלחה - מספר מעקב...
  • LinkedIn: 3 הזמנות לחיבור
  • GitHub: PR needs review

🟡 מידע (P3):
... (7 more items)

⚪ פרסום: 3 מיילים

━━━━━━━━━━━━━━━━━━━━━━
עבדתי 12 שניות | בדקתי 3 מקורות
```

**After (ADHD-Friendly)**:
```
⏰ 09:00 | יש לך דבר אחד דחוף

🔴 ביטוח לאומי רוצה תשובה תוך 7 ימים
   💡 זה טופס 101 פשוט. אני יכול למלא בשבילך.

   [מלא עכשיו] או [תזכיר מחר]

━━━━━━━━━━━━

📬 עוד 14 מיילים (שום דבר דחוף נוסף)
   [הראה הכל] או [סמן כנקרא]
```

#### Key Differences

| Aspect | Standard | ADHD-Friendly |
|--------|----------|---------------|
| **Information density** | All at once | Progressive disclosure |
| **CTAs** | Multiple | One primary action |
| **Statistics** | Detailed numbers | "יש דבר אחד דחוף" |
| **Time reference** | Date/time | "תוך 7 ימים" |
| **Tone** | Neutral | Encouraging, calm |
| **Length** | Comprehensive | Scannable |

#### Notification Modes

```python
from enum import Enum

class NotificationMode(Enum):
    """User preference for notification style."""
    STANDARD = "standard"           # Full details
    ADHD_FRIENDLY = "adhd"          # Simplified, one action
    MINIMAL = "minimal"             # Just urgent items
    DIGEST = "digest"               # Once daily summary

@dataclass
class ADHDFriendlyMessage:
    """Structured message for ADHD users."""
    # Primary focus (ONE thing)
    primary_action: str             # "ביטוח לאומי רוצה תשובה"
    deadline_human: str             # "תוך 7 ימים"
    ai_insight: str                 # "זה טופס פשוט"

    # Single CTA
    primary_cta: str                # "מלא עכשיו"
    secondary_cta: str              # "תזכיר מחר"

    # Hidden details (expandable)
    other_count: int                # 14
    other_urgent: bool              # False

    # Time context
    current_time: str               # "09:00"
    reading_time_estimate: str      # "30 שניות"
```

#### Telegram Implementation

```python
def format_adhd_message(summary: DailySummary) -> str:
    """Format message for ADHD users."""

    # Find the ONE most urgent item
    p1_items = [e for e in summary.emails if e.priority == Priority.P1]

    if p1_items:
        urgent = p1_items[0]
        lines = [
            f"⏰ {datetime.now().strftime('%H:%M')} | יש לך דבר אחד דחוף",
            "",
            f"🔴 {urgent.sender} רוצה תשובה",
        ]

        if urgent.deadline:
            lines.append(f"   ⏳ {urgent.deadline}")

        if urgent.ai_insight:
            lines.append(f"   💡 {urgent.ai_insight}")

        lines.extend([
            "",
            "   [טפל עכשיו] או [תזכיר מחר]",
            "",
            "━━━━━━━━━━━━",
            "",
        ])
    else:
        lines = [
            f"⏰ {datetime.now().strftime('%H:%M')} | אין שום דבר דחוף 🎉",
            "",
        ]

    # Other items (collapsed)
    other_count = len(summary.emails) - len(p1_items[:1])
    if other_count > 0:
        lines.append(f"📬 עוד {other_count} מיילים")
        lines.append("   [הראה הכל] או [סמן כנקרא]")

    return "\n".join(lines)
```

#### Time Blindness Helpers

```python
def add_time_context(message: str, start_time: datetime) -> str:
    """Add time context to help with time blindness."""
    elapsed = datetime.now() - start_time
    minutes = int(elapsed.total_seconds() / 60)

    if minutes > 30:
        return message + f"\n\n⏰ _כבר {minutes} דקות שאתה כאן_"
    return message

def humanize_deadline(deadline: datetime) -> str:
    """Convert deadline to human-friendly format."""
    now = datetime.now()
    diff = deadline - now

    if diff.days == 0:
        return "היום!"
    elif diff.days == 1:
        return "מחר"
    elif diff.days < 7:
        return f"תוך {diff.days} ימים"
    elif diff.days < 30:
        weeks = diff.days // 7
        return f"תוך {weeks} שבועות"
    else:
        return deadline.strftime("%d/%m")
```

#### User Preference Storage

```python
@dataclass
class UserADHDPreferences:
    """ADHD-specific preferences."""
    notification_mode: NotificationMode = NotificationMode.ADHD_FRIENDLY

    # Cognitive load
    max_items_per_message: int = 3
    show_statistics: bool = False

    # Time blindness
    show_clock: bool = True
    session_time_reminders: bool = True
    humanize_deadlines: bool = True

    # Focus
    one_cta_per_message: bool = True
    progressive_disclosure: bool = True

    # Tone
    use_encouraging_language: bool = True
    avoid_guilt_messaging: bool = True

    # Calm mode
    reduce_emojis: bool = False       # Some find emojis helpful
    reduce_animations: bool = True
    muted_colors: bool = False
```

#### A/B Testing Metrics

| Metric | Standard | ADHD Mode | Target |
|--------|----------|-----------|--------|
| **Message open rate** | Baseline | +20% | Measure engagement |
| **Action completion** | Baseline | +40% | Key metric |
| **Time to action** | Baseline | -30% | Faster decisions |
| **Abandonment rate** | Baseline | -50% | Less overwhelm |
| **User satisfaction** | Baseline | +30% | Survey NPS |

### Model Routing Strategy (ADR-013)

| Task | Model | Cost/1M tokens | Rationale |
|------|-------|----------------|-----------|
| Classification | Haiku | $0.25 in / $1.25 out | Fast, cheap, sufficient |
| Hebrew Detection | DictaLM 2.0 | Local | Best Hebrew understanding |
| Research Summary | Sonnet | $3 in / $15 out | Quality for user-facing |
| Complex Analysis | Opus | $15 in / $75 out | Only for P1 emergencies |
| Entity Extraction | GLiNER | Local | Zero-shot, fast |

**Estimated Cost**: ~$0.02-0.05 per email run (vs $0.50+ with Opus-only)

### n8n Integration

n8n remains the "nervous system" for:
- ⏰ Scheduled triggers (6:00 AM Israel time)
- 📲 Telegram webhook handling
- 🔔 Alert routing
- 📊 Metrics collection

**NOT used for**:
- ❌ LLM orchestration
- ❌ Complex logic
- ❌ State management

### File Structure

```
src/agents/
├── gmail_client.py          # ✅ Existing
├── email_agent.py           # Refactor to orchestrator
├── smart_email/
│   ├── __init__.py
│   ├── graph.py             # LangGraph state machine
│   ├── nodes/
│   │   ├── classify.py      # Classification node
│   │   ├── research.py      # Active research node
│   │   ├── generate.py      # Message generation node
│   │   ├── pii_redact.py    # PII redaction node
│   │   └── format_rtl.py    # RTL formatting node
│   ├── memory.py            # Mem0 integration
│   ├── persona.py           # Hebrish personality prompts
│   └── report.py            # WeasyPrint PDF generation
```

## Implementation Phases

### Phase 1: Foundation (MVP)
- [ ] Create LangGraph state machine skeleton
- [ ] Implement classification node with Haiku
- [ ] Add basic Hebrish formatting
- [ ] Test with existing Gmail client

### Phase 2: Intelligence
- [ ] Add Tavily research integration
- [ ] Implement PII redaction with Presidio
- [ ] Add sender history (SQLite)
- [ ] Expand Hebrish persona prompts

### Phase 3: Polish
- [ ] Add WeasyPrint PDF reports
- [ ] Implement Mem0 for memory
- [ ] Add investigation transparency
- [ ] Create visual templates

### Phase 4: Production
- [ ] Deploy via n8n triggers
- [ ] Add monitoring and metrics
- [ ] User feedback loop
- [ ] Cost optimization

## Consequences

### Positive
- **Smart**: Active research, context understanding
- **Personal**: Hebrish persona, remembers patterns
- **Efficient**: 60-80% cost reduction via model routing
- **Secure**: PII redaction, audit trails
- **Visual**: Rich formatting, optional PDFs

### Negative
- **Complexity**: More moving parts than current simple agent
- **Dependencies**: Tavily API, Presidio, potentially Mem0
- **Latency**: Research adds 5-15 seconds per high-priority email

### Neutral
- **Migration**: Gradual migration from v1 to v2
- **Testing**: Requires comprehensive test suite

## Alternatives Considered

### 1. CrewAI Multi-Agent
**Rejected**: Experimental, less production-ready than LangGraph

### 2. AutoGen with Memory
**Rejected**: Microsoft-focused, less flexible

### 3. Pure n8n Workflow
**Rejected**: n8n excels at I/O, not LLM orchestration

### 4. Antigravity Platform
**Rejected**: Not verified as production-ready, unclear pricing

## Related Decisions

- [ADR-010: Multi-LLM Routing Strategy](ADR-010-multi-llm-routing-strategy.md)
- [ADR-013: Smart Model Routing](ADR-013-smart-model-routing-implementation.md)

## References

### External Sources (Verified)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Microsoft Presidio](https://github.com/microsoft/presidio)
- [W3C RTL Marks](https://www.w3.org/TR/WCAG20-TECHS/H34.html)
- [Tavily API](https://docs.tavily.com/)
- [WeasyPrint](https://weasyprint.org/)
- [Mem0](https://mem0.ai/)
- [GLiNER](https://github.com/urchade/GLiNER)
- [DictaLM](https://huggingface.co/dicta-il)

### Internal Sources
- User feedback session (2026-01-23)
- Deep Research results x3 (verified)
- Existing `src/agents/email_agent.py`

## Update Log

| Date | Update | By |
|------|--------|------|
| 2026-01-23 | Initial proposal | Claude Agent |
