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

### Continuous Learning (למידה מתמשכת)

**Sources**: [Mem0 Documentation](https://mem0.ai/), [AWS Feedback Loop Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-feedback-loop.html), [Anthropic AI Feedback Patterns](https://www.anthropic.com/research), [Closed-Loop AI Systems](https://arxiv.org/abs/2306.03314)

#### Why Continuous Learning?

> **Mem0 Results** (verified): 26% accuracy boost, 91% lower latency, 90% token savings
> **Funding**: $24M from enterprise customers validating the approach

The agent should:
1. **Learn user preferences** - "I don't care about LinkedIn notifications"
2. **Remember sender patterns** - "Amazon = always shipping updates"
3. **Adapt priority classification** - Improve P1/P2/P3/P4 accuracy over time
4. **Recall past interactions** - "Last time you asked to reply to דן"

#### Memory Architecture (Mem0)

```python
from mem0 import Memory

# Initialize with user context
memory = Memory.from_config({
    "vector_store": {
        "provider": "qdrant",
        "config": {"collection_name": "email_agent"}
    },
    "llm": {
        "provider": "anthropic",
        "config": {"model": "claude-3-haiku-20240307"}
    },
    "version": "v1.1"  # Pinned version
})

# Add memory with user context
memory.add(
    messages=[
        {"role": "user", "content": "סמן מיילים מ-LinkedIn כ-P4"},
        {"role": "assistant", "content": "הבנתי, אעדכן את ההעדפות"}
    ],
    user_id="or",
    metadata={"type": "preference", "category": "priority_override"}
)

# Retrieve relevant memories
relevant = memory.search(
    query="איך לסווג מייל מ-LinkedIn?",
    user_id="or",
    limit=5
)
# Returns: "המשתמש ביקש לסמן LinkedIn כ-P4"
```

#### Memory Types

| Type | What | Retention | Example |
|------|------|-----------|---------|
| **Long-term** | Persistent preferences | Forever | "I prefer brief summaries" |
| **Short-term** | Session context | Session | "We're discussing the tax form" |
| **Semantic** | Conceptual knowledge | Persistent | "Amazon emails = shipping" |
| **Episodic** | Specific events | 90 days | "On Jan 15, user marked X urgent" |
| **Self-Improving** | Model corrections | Forever | "False positive: bank ads ≠ P1" |

#### Learning Domains

##### 1. Preference Learning (העדפות)

```python
@dataclass
class UserPreference:
    """Learned user preferences."""
    # Priority overrides
    sender_priority: dict[str, Priority]  # {"linkedin.com": P4}
    keyword_priority: dict[str, Priority] # {"urgent": P1, "פרסום": P4}

    # Communication style
    summary_length: Literal["brief", "detailed"]
    language_mix: Literal["mostly_hebrew", "hebrish", "mostly_english"]
    emoji_density: Literal["minimal", "moderate", "rich"]

    # Timing
    quiet_hours: tuple[int, int]          # (22, 7) = 10PM-7AM
    preferred_summary_time: str           # "06:00"

    # Topics
    interesting_senders: list[str]        # Always highlight
    blocked_senders: list[str]            # Never show

class PreferenceLearner:
    """Learn preferences from user feedback."""

    def learn_from_correction(
        self,
        email_id: str,
        original_priority: Priority,
        corrected_priority: Priority,
        user_id: str
    ):
        """User corrected a classification."""
        # Store correction in Mem0
        self.memory.add(
            messages=[{
                "role": "system",
                "content": f"Priority correction: {original_priority} → {corrected_priority}"
            }],
            user_id=user_id,
            metadata={
                "type": "correction",
                "sender": self.get_sender(email_id),
                "keywords": self.get_keywords(email_id)
            }
        )

        # Update rules if pattern emerges
        if self._detect_pattern(user_id, threshold=3):
            self._create_rule(user_id)
```

##### 2. Content Learning (תוכן)

```python
@dataclass
class ContentPattern:
    """Learned content patterns."""
    # Sender patterns
    sender_type: dict[str, str]           # {"amazon.com": "e-commerce"}
    sender_typical_content: dict[str, str] # {"btl.gov.il": "forms"}

    # Email patterns
    newsletter_senders: list[str]
    transactional_senders: list[str]      # Orders, confirmations
    bureaucratic_senders: list[str]       # Government, banks

    # Hebrew patterns
    urgent_phrases_he: list[str]          # ["דחוף", "נדרש אישור"]
    deadline_patterns: list[str]          # ["תוך X ימים", "עד ה-"]

class ContentLearner:
    """Learn content patterns from emails."""

    def analyze_sender(self, sender: str, emails: list[Email]) -> SenderProfile:
        """Build sender profile from email history."""
        return SenderProfile(
            sender=sender,
            typical_priority=self._calculate_typical_priority(emails),
            typical_content_type=self._classify_content_type(emails),
            response_rate=self._calculate_response_rate(emails),
            average_urgency=self._calculate_urgency(emails),
            last_interaction=max(e.date for e in emails)
        )

    def detect_email_type(self, email: Email) -> EmailType:
        """Classify email using learned patterns."""
        # Check against Mem0 for similar emails
        similar = self.memory.search(
            query=f"emails from {email.sender} about {email.subject[:50]}",
            user_id=email.user_id,
            limit=5
        )

        if similar:
            # Use past classification as hint
            return self._infer_type_from_history(similar)
        else:
            # Fall back to LLM classification
            return self._llm_classify(email)
```

##### 3. Behavioral Learning (התנהגות)

```python
@dataclass
class BehavioralPattern:
    """Learned behavioral patterns."""
    # Response patterns
    emails_usually_acted_on: list[str]    # Patterns user engages with
    emails_usually_ignored: list[str]     # Patterns user ignores

    # Time patterns
    active_hours: list[int]               # Hours user typically reads
    response_delay_by_priority: dict[Priority, timedelta]

    # Action patterns
    typical_actions: dict[str, str]       # {"שכר": "forward_to_accountant"}

class BehavioralLearner:
    """Learn from user actions."""

    def track_action(
        self,
        email_id: str,
        action: EmailAction,
        time_to_action: timedelta,
        user_id: str
    ):
        """Track user action on email."""
        email = self.get_email(email_id)

        self.memory.add(
            messages=[{
                "role": "system",
                "content": f"User {action.value} email from {email.sender} in {time_to_action}"
            }],
            user_id=user_id,
            metadata={
                "type": "action",
                "action": action.value,
                "sender": email.sender,
                "priority": email.priority.value,
                "response_time_minutes": time_to_action.total_seconds() / 60
            }
        )

    def suggest_action(self, email: Email) -> ActionSuggestion | None:
        """Suggest action based on learned behavior."""
        similar_actions = self.memory.search(
            query=f"actions for emails from {email.sender}",
            user_id=email.user_id,
            limit=10
        )

        if self._has_consistent_pattern(similar_actions):
            return ActionSuggestion(
                action=self._most_common_action(similar_actions),
                confidence=self._calculate_confidence(similar_actions),
                reason=f"בעבר תמיד {self._action_to_hebrew(action)} מיילים כאלה"
            )
        return None
```

#### Feedback Loop Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                     CONTINUOUS LEARNING LOOP                            │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. OBSERVE: Email arrives                                              │
│     └─ Extract: sender, subject, content, metadata                     │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. RECALL: Query Mem0 for relevant context                            │
│     └─ User preferences                                                │
│     └─ Sender history                                                  │
│     └─ Similar past emails                                             │
│     └─ Past corrections                                                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. DECIDE: Classify with context                                       │
│     └─ Base classification (Haiku)                                     │
│     └─ Adjust with learned preferences                                 │
│     └─ Apply sender-specific rules                                     │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. PRESENT: Show to user with confidence                              │
│     └─ "סיווגתי כ-P2 (90% בטוח)"                                      │
│     └─ "בעבר סימנת מיילים מהשולח הזה כ-P3"                            │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. COLLECT FEEDBACK: User action                                       │
│     ├─ Explicit: "זה לא P2, זה P4"                                    │
│     ├─ Implicit: User ignored for 24 hours                             │
│     └─ Behavioral: User archived without reading                       │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  6. LEARN: Update memory                                                │
│     └─ Store correction in Mem0                                        │
│     └─ Update sender profile                                           │
│     └─ Adjust classification rules                                     │
│     └─ Log for analysis                                                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  └───────────► Back to step 1
```

#### Explicit Feedback Commands

```python
FEEDBACK_COMMANDS = {
    # Priority corrections
    "זה דחוף": lambda e: correct_priority(e, Priority.P1),
    "לא דחוף": lambda e: correct_priority(e, Priority.P3),
    "ספאם": lambda e: correct_priority(e, Priority.P4) and block_sender(e),

    # Preference learning
    "תמיד תראה לי מ-X": lambda e: add_to_whitelist(e.sender),
    "לא מעניין אותי X": lambda e: add_to_blacklist(e.sender),
    "סווג כ-*": lambda e, p: set_sender_default(e.sender, p),

    # Communication style
    "יותר קצר": lambda: update_preference("summary_length", "brief"),
    "יותר פרטים": lambda: update_preference("summary_length", "detailed"),

    # Special handling
    "תמיד העבר ל-Y": lambda e: create_forward_rule(e.sender, "Y"),
    "תזכיר לי על זה": lambda e: create_reminder(e, default_delay="1d"),
}
```

#### Implicit Feedback Signals

| Signal | Interpretation | Learning Action |
|--------|----------------|-----------------|
| Opened within 5 min | High interest | Increase sender priority |
| Ignored > 24 hours | Low interest | Consider downgrading |
| Replied immediately | Very important | Mark sender as VIP |
| Archived without reading | Not relevant | Suggest auto-archive |
| Marked as spam | Unwanted | Block sender pattern |
| Clicked form link | Actionable | Track form completion |

#### Self-Improvement Metrics

```python
@dataclass
class LearningMetrics:
    """Track learning effectiveness."""
    # Classification accuracy
    initial_accuracy: float           # Before corrections
    post_learning_accuracy: float     # After learning
    accuracy_delta: float             # Improvement

    # User corrections
    corrections_per_day: float
    correction_rate: float            # corrections / classifications

    # Memory effectiveness
    relevant_recall_rate: float       # Did Mem0 find relevant context?
    memory_usage_tokens_saved: int    # Tokens saved via context

    # User satisfaction (implicit)
    engagement_rate: float            # Opens + clicks / total
    response_time_trend: str          # "improving", "stable", "declining"

def calculate_learning_health(metrics: LearningMetrics) -> LearningHealth:
    """Assess if learning is working."""
    if metrics.correction_rate < 0.05:
        return LearningHealth.EXCELLENT  # <5% need correction
    elif metrics.correction_rate < 0.15:
        return LearningHealth.GOOD       # <15% need correction
    elif metrics.accuracy_delta > 0:
        return LearningHealth.IMPROVING  # Getting better
    else:
        return LearningHealth.NEEDS_ATTENTION
```

#### Privacy & Data Retention

| Data Type | Retention | User Control |
|-----------|-----------|--------------|
| **Preferences** | Permanent (until changed) | Full edit/delete |
| **Sender profiles** | 1 year rolling | Can clear |
| **Corrections** | 90 days | Can clear |
| **Email content** | Not stored | N/A |
| **Aggregated patterns** | 1 year | Export/delete |

```python
# User data control commands
PRIVACY_COMMANDS = {
    "מה אתה זוכר עליי?": show_all_memories,
    "שכח את הכל": clear_all_memories,
    "שכח את X": forget_specific_memory,
    "אל תזכור מיילים מ-X": disable_learning_for_sender,
    "ייצא את הנתונים שלי": export_user_data,
}
```

#### Integration with LangGraph

```python
from langgraph.graph import StateGraph

def recall_context_node(state: EmailState) -> EmailState:
    """Recall relevant context from Mem0."""
    memories = memory.search(
        query=f"{state['email'].sender} {state['email'].subject}",
        user_id=state['user_id'],
        limit=10
    )

    state['context'] = {
        'preferences': extract_preferences(memories),
        'sender_history': extract_sender_history(memories),
        'past_corrections': extract_corrections(memories),
    }
    return state

def learn_from_feedback_node(state: EmailState) -> EmailState:
    """Store feedback for future learning."""
    if state.get('user_feedback'):
        memory.add(
            messages=[{
                "role": "user",
                "content": state['user_feedback']
            }],
            user_id=state['user_id'],
            metadata={
                "type": "feedback",
                "email_id": state['email'].id,
                "original_classification": state['classification'],
            }
        )
    return state

# Add to graph
workflow.add_node("recall_context", recall_context_node)
workflow.add_node("learn_from_feedback", learn_from_feedback_node)

# Wire into flow
workflow.add_edge("fetch_emails", "recall_context")
workflow.add_edge("recall_context", "classify")
workflow.add_edge("await_feedback", "learn_from_feedback")
```

### Thread Context & History Search (הקשר שרשורי וחיפוש היסטוריה)

**Sources**: [Gmail API Threads](https://developers.google.com/workspace/gmail/api/guides/threads), [Conversational RAG](https://haystack.deepset.ai/cookbook/conversational_rag_using_memory), [GAM Memory Architecture](https://venturebeat.com/ai/gam-takes-aim-at-context-rot-a-dual-agent-memory-architecture/), [LLM Memory Design](https://www.datacamp.com/blog/how-does-llm-memory-work)

#### Why Thread Context Matters

> "Context rot" - when AI loses the thread in multi-step reasoning tasks.
> Traditional RAG breaks down when information stretches across multiple sessions.

**Without context**:
```
📧 מייל חדש מ-דני:
   "מה עם התשובה?"

🤖 סוכן רגיל: "יש לך מייל מדני ששואל על תשובה"
   ❌ חסר הקשר - על מה הוא מדבר?
```

**With context**:
```
📧 מייל חדש מ-דני:
   "מה עם התשובה?"

🤖 סוכן חכם:
   "דני שואל על ההצעה לשיתוף פעולה ששלח לפני 3 ימים.
    בהצעה הוא הציע: X, Y, Z.
    עדיין לא ענית."
   ✅ הקשר מלא
```

#### Gmail Thread API Integration

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class ThreadContextRetriever:
    """Retrieve full thread context from Gmail."""

    def __init__(self, credentials: Credentials):
        self.service = build('gmail', 'v1', credentials=credentials)

    def get_thread_context(self, thread_id: str) -> ThreadContext:
        """Fetch entire thread with all messages."""
        thread = self.service.users().threads().get(
            userId='me',
            id=thread_id,
            format='full'  # Get full message content
        ).execute()

        messages = []
        for msg in thread.get('messages', []):
            messages.append(self._parse_message(msg))

        return ThreadContext(
            thread_id=thread_id,
            message_count=len(messages),
            messages=messages,
            participants=self._extract_participants(messages),
            date_range=(messages[0].date, messages[-1].date),
            subject=messages[0].subject
        )

    def get_sender_history(
        self,
        sender_email: str,
        max_results: int = 20
    ) -> list[EmailSummary]:
        """Get recent emails from same sender."""
        query = f"from:{sender_email}"

        results = self.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        history = []
        for msg_ref in results.get('messages', []):
            msg = self.service.users().messages().get(
                userId='me',
                id=msg_ref['id'],
                format='metadata',
                metadataHeaders=['Subject', 'Date', 'From']
            ).execute()
            history.append(self._to_summary(msg))

        return history
```

#### Context Types

| סוג הקשר | מה כולל | מתי משתמשים |
|----------|---------|-------------|
| **Thread Context** | כל ההודעות בשרשור | מייל הוא תגובה/המשך |
| **Sender History** | מיילים קודמים מאותו שולח | זיהוי דפוסים |
| **Topic History** | מיילים על אותו נושא | "הזמנה #123" |
| **Time Context** | מיילים מאותו יום/שבוע | "הפגישה של מחר" |

#### Semantic Search with RAG

```python
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

class EmailRAG:
    """RAG for semantic email search."""

    def __init__(self):
        self.encoder = SentenceTransformer('intfloat/multilingual-e5-large')
        self.qdrant = QdrantClient(path="./email_vectors")

    def index_email(self, email: Email) -> None:
        """Index email for semantic search."""
        # Combine fields for embedding
        text = f"{email.subject} {email.sender} {email.snippet}"

        # Generate embedding
        embedding = self.encoder.encode(text)

        # Store in Qdrant
        self.qdrant.upsert(
            collection_name="emails",
            points=[{
                "id": email.id,
                "vector": embedding.tolist(),
                "payload": {
                    "subject": email.subject,
                    "sender": email.sender,
                    "date": email.date.isoformat(),
                    "thread_id": email.thread_id,
                }
            }]
        )

    def search_similar(
        self,
        query: str,
        limit: int = 5,
        sender_filter: str | None = None
    ) -> list[EmailSummary]:
        """Find similar emails by semantic meaning."""
        query_vector = self.encoder.encode(query)

        filter_conditions = None
        if sender_filter:
            filter_conditions = {
                "must": [{"key": "sender", "match": {"value": sender_filter}}]
            }

        results = self.qdrant.search(
            collection_name="emails",
            query_vector=query_vector.tolist(),
            limit=limit,
            query_filter=filter_conditions
        )

        return [self._to_summary(r) for r in results]

    def find_related_threads(self, email: Email) -> list[ThreadContext]:
        """Find threads related to this email's topic."""
        # Search by subject keywords
        subject_keywords = self._extract_keywords(email.subject)

        related = self.search_similar(
            query=f"{email.subject} {email.snippet}",
            limit=10
        )

        # Group by thread_id
        thread_ids = set(r.thread_id for r in related)
        return [self.get_thread(tid) for tid in thread_ids]
```

#### Context Injection Pattern

```python
@dataclass
class EnrichedEmail:
    """Email with all relevant context."""
    email: Email
    thread_context: ThreadContext | None
    sender_history: list[EmailSummary]
    related_emails: list[EmailSummary]
    context_summary: str  # AI-generated summary

class ContextInjector:
    """Inject context before classification."""

    def __init__(self, thread_retriever: ThreadContextRetriever, rag: EmailRAG):
        self.threads = thread_retriever
        self.rag = rag

    def enrich(self, email: Email) -> EnrichedEmail:
        """Enrich email with all available context."""

        # 1. Get thread context (if reply)
        thread_context = None
        if self._is_reply(email):
            thread_context = self.threads.get_thread_context(email.thread_id)

        # 2. Get sender history
        sender_history = self.threads.get_sender_history(
            sender_email=email.sender_email,
            max_results=10
        )

        # 3. Find related emails (semantic)
        related_emails = self.rag.search_similar(
            query=email.subject,
            limit=5
        )

        # 4. Generate context summary
        context_summary = self._generate_summary(
            email, thread_context, sender_history, related_emails
        )

        return EnrichedEmail(
            email=email,
            thread_context=thread_context,
            sender_history=sender_history,
            related_emails=related_emails,
            context_summary=context_summary
        )

    def _generate_summary(self, email, thread, history, related) -> str:
        """Generate human-readable context summary."""
        parts = []

        # Thread context
        if thread and thread.message_count > 1:
            parts.append(
                f"📧 זה חלק משרשור עם {thread.message_count} הודעות "
                f"שהתחיל ב-{thread.date_range[0].strftime('%d/%m')}"
            )

        # Sender history
        if history:
            last_email = history[0]
            days_ago = (datetime.now() - last_email.date).days
            parts.append(
                f"👤 {email.sender} שלח לך {len(history)} מיילים. "
                f"האחרון לפני {days_ago} ימים על: {last_email.subject[:30]}"
            )

        # Related topics
        if related:
            topics = set(r.subject[:20] for r in related[:3])
            parts.append(f"🔗 נושאים קשורים: {', '.join(topics)}")

        return "\n".join(parts) if parts else "אין הקשר נוסף"
```

#### Thread-Aware Classification

```python
def classify_with_context(
    email: Email,
    context: EnrichedEmail,
    classifier: Classifier
) -> tuple[Priority, str]:
    """Classify considering full context."""

    # Build context-aware prompt
    prompt = f"""
    סווג את המייל הבא לפי עדיפות (P1-P4).

    📧 מייל נוכחי:
    - מאת: {email.sender}
    - נושא: {email.subject}
    - תוכן: {email.snippet}

    📋 הקשר:
    {context.context_summary}

    🔍 היסטוריית שולח:
    - סה"כ מיילים: {len(context.sender_history)}
    - עדיפות טיפוסית: {_typical_priority(context.sender_history)}
    - נושאים נפוצים: {_common_topics(context.sender_history)}

    📝 שרשור:
    {_thread_summary(context.thread_context) if context.thread_context else "מייל חדש (לא תגובה)"}

    החלט:
    - P1 (דחוף): דורש תשובה מיידית, דד-ליין קרוב
    - P2 (חשוב): דורש תשובה, אבל לא דחוף
    - P3 (מידע): כדאי לדעת, לא דורש פעולה
    - P4 (נמוך): ניתן להתעלם או לקבץ
    """

    result = classifier.classify(prompt)

    return result.priority, result.reasoning
```

#### Thread Summary in Telegram

```
📧 מייל חדש מ-דני כהן

📋 *הקשר:*
├─ 🔄 חלק משרשור (5 הודעות, התחיל 20/01)
├─ 👤 מייל 8 מדני החודש (עדיפות טיפוסית: P2)
└─ 🔗 קשור ל: "הצעת מחיר לפרויקט X"

📝 *סיכום שרשור:*
• 20/01 - דני: שלח הצעה ראשונית (₪15,000)
• 21/01 - אתה: ביקשת הנחה
• 22/01 - דני: הציע ₪13,000
• היום - דני: "מה עם התשובה?"

💡 *המלצה:* זה follow-up על הצעת המחיר.
   צריך להחליט אם להמשיך או לסרב.
```

#### Privacy Considerations

| Data | Where Stored | Retention |
|------|--------------|-----------|
| Email vectors | Local Qdrant | 90 days |
| Thread cache | SQLite | 7 days |
| Sender profiles | Mem0 | 1 year |
| Full email content | **Not stored** | Gmail only |

```python
# Privacy-safe: Store only metadata, not content
EMAIL_INDEXED_FIELDS = [
    "id", "thread_id", "sender", "sender_email",
    "subject", "date", "labels"
]
# ❌ Never indexed: body, attachments, recipients
```

#### Integration with LangGraph

```python
def context_retrieval_node(state: EmailState) -> EmailState:
    """Node that retrieves all relevant context."""
    email = state['email']

    # Get thread context
    if email.thread_id:
        state['thread_context'] = thread_retriever.get_thread_context(
            email.thread_id
        )

    # Get sender history
    state['sender_history'] = thread_retriever.get_sender_history(
        email.sender_email,
        max_results=10
    )

    # Semantic search for related
    state['related_emails'] = rag.search_similar(
        query=email.subject,
        limit=5
    )

    # Generate context summary
    state['context_summary'] = generate_context_summary(state)

    return state

# Add to graph
workflow.add_node("context_retrieval", context_retrieval_node)
workflow.add_edge("fetch_emails", "context_retrieval")
workflow.add_edge("context_retrieval", "recall_memory")  # Then Mem0
workflow.add_edge("recall_memory", "classify")
```

### Proactive Problem-Solving Research (חקירות פתרון בעיות)

**Sources**: [ביטוח לאומי - זכויות והטבות](https://www.btl.gov.il/English%20Homepage/Benefits/), [Israel Tax Changes 2026](https://www.cwsisrael.com/israeli-tax-changes-2026-complete-guide/), [Consumer Rights Israel](https://www.jdsupra.com/topics/artificial-intelligence/consumer-protection-laws/israel/), [Kol Zchut - כל זכות](https://www.kolzchut.org.il/)

#### הרעיון המרכזי

כשמגיע מייל "לא נעים" (דוח, חיוב, דרישה ממשלתית), הסוכן לא רק מדווח - הוא **מחפש פתרונות**:

```
📧 מייל נכנס: "דוח חניה - ₪500"

🤖 סוכן רגיל:
   "יש לך דוח חניה על ₪500. תשלם עד 15/02."
   ❌ סתם מביא בשורות רעות

🤖 סוכן חכם:
   "יש לך דוח חניה על ₪500.

   💡 מצאתי כמה אפשרויות:
   1. ⏰ תשלום מוקדם (תוך 30 יום): הנחה 20% → ₪400
   2. 📝 ערעור: המקום מסומן לא ברור (הצלחה ~40%)
   3. 💳 פריסה: עד 3 תשלומים ללא ריבית

   🔗 מקורות: עיריית ת"א, כל זכות, חוות דעת משפטית"
   ✅ מביא פתרונות יצירתיים
```

#### סוגי בעיות נתמכות

| קטגוריה | סוג מייל | מה הסוכן מחפש |
|---------|----------|---------------|
| **דוחות** | חניה, מהירות, אי-חגירה | הנחות, ערעורים, פריסה |
| **ביטוח לאומי** | דרישות תשלום, דחיות | זכאויות לא מנוצלות, פטורים |
| **מיסים** | שומות, דרישות | זיכויים, ניכויים, הקלות |
| **חשבונות** | חשמל, מים, ארנונה | הנחות לזכאים, תעריפים |
| **בנקים** | עמלות, חיובים | ביטול עמלות, משא ומתן |
| **ביטוחים** | דחיות תביעות | ערעורים, הממונה על הביטוח |
| **ממשלתי** | אגרות, היטלים | פטורים, הנחות, ערר |

#### ארכיטקטורת החקירה

```python
from enum import Enum
from dataclasses import dataclass

class ProblemCategory(Enum):
    FINE = "fine"                    # דוחות
    NATIONAL_INSURANCE = "btl"       # ביטוח לאומי
    TAX = "tax"                      # מס הכנסה
    MUNICIPAL = "municipal"          # עירייה (ארנונה, מים)
    UTILITY = "utility"              # חשמל, גז
    BANK = "bank"                    # בנקים
    INSURANCE = "insurance"          # ביטוח פרטי
    GOVERNMENT = "government"        # ממשלתי אחר

@dataclass
class ProblemEmail:
    """Email identified as containing a problem to solve."""
    category: ProblemCategory
    amount: float | None             # סכום אם רלוונטי
    deadline: datetime | None        # דד-ליין לתשלום/תגובה
    institution: str                 # הגוף הדורש
    reference_number: str | None     # מספר אסמכתא
    original_email: Email

@dataclass
class Solution:
    """A potential solution found for the problem."""
    solution_type: str               # "discount", "appeal", "exemption", etc.
    description_he: str              # תיאור בעברית
    potential_savings: float | None  # חיסכון פוטנציאלי
    success_probability: str         # "high", "medium", "low"
    effort_required: str             # "easy", "moderate", "complex"
    deadline: datetime | None        # עד מתי אפשר לנצל
    steps: list[str]                 # צעדים לביצוע
    sources: list[str]               # מקורות מידע
    verified: bool                   # האם מאומת מגוף רשמי

@dataclass
class ProblemAnalysis:
    """Complete analysis of a problem email."""
    problem: ProblemEmail
    solutions: list[Solution]
    recommended_action: str
    research_summary: str
    sources_consulted: list[str]
    research_time_seconds: float
```

#### מקורות מידע לחיפוש

```python
RESEARCH_SOURCES = {
    # מקורות רשמיים (עדיפות גבוהה)
    "official": [
        {"name": "כל זכות", "url": "kolzchut.org.il", "type": "rights_database"},
        {"name": "ביטוח לאומי", "url": "btl.gov.il", "type": "government"},
        {"name": "רשות המיסים", "url": "taxes.gov.il", "type": "government"},
        {"name": "gov.il", "url": "gov.il", "type": "government_portal"},
    ],

    # מקורות משפטיים
    "legal": [
        {"name": "נבו", "url": "nevo.co.il", "type": "legal_database"},
        {"name": "פסקדין", "url": "psakdin.co.il", "type": "court_decisions"},
    ],

    # מקורות קהילתיים (אימות נדרש)
    "community": [
        {"name": "פייסבוק קבוצות", "type": "social", "verify": True},
        {"name": "פורומים", "type": "forums", "verify": True},
        {"name": "Reddit Israel", "type": "social", "verify": True},
    ],

    # מקורות פיננסיים
    "financial": [
        {"name": "בנק ישראל", "url": "boi.org.il", "type": "regulator"},
        {"name": "הממונה על הביטוח", "url": "mof.gov.il", "type": "regulator"},
        {"name": "כלכליסט", "url": "calcalist.co.il", "type": "news"},
    ],
}
```

#### לוגיקת חקירה לפי קטגוריה

##### 1. דוחות (חניה, תנועה)

```python
async def research_fine_solutions(fine: ProblemEmail) -> list[Solution]:
    """Find solutions for traffic/parking fines."""
    solutions = []

    # 1. בדוק הנחת תשלום מוקדם
    if fine.deadline and (fine.deadline - datetime.now()).days > 30:
        solutions.append(Solution(
            solution_type="early_payment",
            description_he="תשלום מוקדם תוך 30 יום - הנחה 20%",
            potential_savings=fine.amount * 0.20,
            success_probability="high",
            effort_required="easy",
            steps=["שלם באתר העירייה תוך 30 יום"],
            sources=["אתר עיריית " + fine.institution],
            verified=True
        ))

    # 2. בדוק אפשרות ערעור
    appeal_grounds = await check_appeal_grounds(fine)
    if appeal_grounds:
        solutions.append(Solution(
            solution_type="appeal",
            description_he=f"ערעור: {appeal_grounds.reason}",
            potential_savings=fine.amount,
            success_probability=appeal_grounds.success_rate,
            effort_required="moderate",
            steps=appeal_grounds.steps,
            sources=["כל זכות - ערעור על דוח"],
            verified=True
        ))

    # 3. בדוק פריסה
    solutions.append(Solution(
        solution_type="installments",
        description_he="פריסה לתשלומים",
        potential_savings=0,  # לא חוסך, אבל מקל
        success_probability="high",
        effort_required="easy",
        steps=["פנה לעירייה לבקשת פריסה"],
        sources=["עירייה"],
        verified=True
    ))

    return solutions
```

##### 2. ביטוח לאומי

```python
async def research_btl_solutions(btl_email: ProblemEmail) -> list[Solution]:
    """Find solutions for National Insurance issues."""
    solutions = []

    # 1. בדוק זכאויות לא מנוצלות
    user_profile = await get_user_profile()
    potential_benefits = await check_btl_eligibility(user_profile)

    for benefit in potential_benefits:
        if not benefit.currently_claimed:
            solutions.append(Solution(
                solution_type="unclaimed_benefit",
                description_he=f"זכאות לא מנוצלת: {benefit.name}",
                potential_savings=benefit.monthly_amount * 12,
                success_probability="high" if benefit.eligible else "medium",
                effort_required="moderate",
                steps=[f"הגש בקשה ל{benefit.name} באתר ביטוח לאומי"],
                sources=["btl.gov.il", "kolzchut.org.il"],
                verified=True
            ))

    # 2. בדוק פטורים
    exemptions = await check_btl_exemptions(user_profile, btl_email)
    for exemption in exemptions:
        solutions.append(Solution(
            solution_type="exemption",
            description_he=f"פטור אפשרי: {exemption.name}",
            potential_savings=exemption.savings,
            success_probability=exemption.probability,
            effort_required=exemption.effort,
            steps=exemption.steps,
            sources=["ביטוח לאומי - פטורים"],
            verified=True
        ))

    # 3. בדוק הסדרי חוב
    if btl_email.amount and btl_email.amount > 1000:
        solutions.append(Solution(
            solution_type="debt_arrangement",
            description_he="הסדר חוב - פריסה לתשלומים",
            potential_savings=0,
            success_probability="high",
            effort_required="moderate",
            steps=[
                "פנה לסניף ביטוח לאומי",
                "הגש בקשה להסדר חוב",
                "צרף מסמכים על מצב כלכלי"
            ],
            sources=["btl.gov.il/hesderei-chov"],
            verified=True
        ))

    return solutions
```

##### 3. מיסים

```python
async def research_tax_solutions(tax_email: ProblemEmail) -> list[Solution]:
    """Find solutions for tax issues."""
    solutions = []

    # 1. בדוק זיכויים והחזרים
    user_profile = await get_user_profile()

    # זיכוי מילואים (חדש 2026!)
    if user_profile.reserve_days_2025 and user_profile.reserve_days_2025 > 0:
        credit = calculate_reserve_credit(user_profile.reserve_days_2025)
        solutions.append(Solution(
            solution_type="tax_credit",
            description_he=f"זיכוי מס מילואים - עד ₪{credit:,}",
            potential_savings=credit,
            success_probability="high",
            effort_required="easy",
            steps=["הגש טופס 101 מעודכן למעסיק"],
            sources=["taxes.gov.il", "CWS Israel Tax Guide 2026"],
            verified=True
        ))

    # 2. נקודות זיכוי לא מנוצלות
    unused_credits = await check_unused_tax_credits(user_profile)
    for credit in unused_credits:
        solutions.append(Solution(
            solution_type="unused_credit",
            description_he=f"נקודת זיכוי: {credit.name}",
            potential_savings=credit.value * 2904,  # ערך נקודה 2026
            success_probability="high",
            effort_required="easy",
            steps=credit.claim_steps,
            sources=["רשות המיסים"],
            verified=True
        ))

    # 3. ערר על שומה
    if tax_email.category == "assessment":
        solutions.append(Solution(
            solution_type="appeal",
            description_he="ערר על שומה",
            potential_savings=tax_email.amount * 0.3,  # הערכה
            success_probability="medium",
            effort_required="complex",
            steps=[
                "הגש השגה תוך 30 יום",
                "צרף מסמכים תומכים",
                "שקול ייצוג מקצועי"
            ],
            sources=["taxes.gov.il/ערר-על-שומה"],
            verified=True
        ))

    return solutions
```

##### 4. ארנונה ומים

```python
async def research_municipal_solutions(municipal: ProblemEmail) -> list[Solution]:
    """Find solutions for municipal charges."""
    solutions = []
    user_profile = await get_user_profile()

    # הנחות ארנונה
    ARNONA_DISCOUNTS = [
        {"name": "הנחת הכנסה", "criteria": "income_based", "discount": "עד 90%"},
        {"name": "אזרח ותיק", "criteria": "age >= 65", "discount": "25%"},
        {"name": "נכה", "criteria": "disability >= 90%", "discount": "80%"},
        {"name": "עולה חדש", "criteria": "aliyah_years < 2", "discount": "90%"},
        {"name": "הורה יחיד", "criteria": "single_parent", "discount": "20%"},
        {"name": "מקבל קצבת נכות", "criteria": "btl_disability", "discount": "80%"},
    ]

    for discount in ARNONA_DISCOUNTS:
        if await check_eligibility(user_profile, discount["criteria"]):
            solutions.append(Solution(
                solution_type="discount",
                description_he=f"הנחת ארנונה - {discount['name']}",
                potential_savings=municipal.amount * 0.5,  # הערכה ממוצעת
                success_probability="high",
                effort_required="moderate",
                steps=[
                    "פנה למחלקת ארנונה בעירייה",
                    "הגש בקשה להנחה עם מסמכים",
                ],
                sources=["אתר העירייה", "כל זכות - הנחות ארנונה"],
                verified=True
            ))

    return solutions
```

#### זרימת החקירה ב-LangGraph

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROBLEM-SOLVING RESEARCH FLOW                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. DETECT PROBLEM: Is this a "negative" email?                          │
│     └─ Keywords: "חיוב", "דרישה", "דוח", "שומה", "תשלום"               │
│     └─ Senders: btl.gov.il, taxes.gov.il, עיריית *                     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. CATEGORIZE: What type of problem?                                    │
│     └─ Extract: amount, deadline, institution, reference                │
│     └─ Classify: FINE, BTL, TAX, MUNICIPAL, etc.                        │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. RESEARCH: Search for solutions (parallel)                            │
│     ├─ Official sources: gov.il, btl.gov.il, taxes.gov.il              │
│     ├─ Rights database: kolzchut.org.il                                 │
│     ├─ Legal precedents: nevo.co.il (if relevant)                       │
│     └─ Community knowledge: verified forum posts                         │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. EVALUATE: Rank solutions                                             │
│     └─ By potential savings                                              │
│     └─ By success probability                                            │
│     └─ By effort required                                                │
│     └─ By deadline urgency                                               │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. PRESENT: Show solutions to user                                      │
│     └─ Top 3 solutions with details                                      │
│     └─ Clear action items                                                │
│     └─ Source links for verification                                     │
│     └─ ⚠️ Disclaimer: "מידע כללי, לא ייעוץ משפטי"                       │
└─────────────────────────────────────────────────────────────────────────┘
```

#### תבנית תצוגה בטלגרם

```
📧 קיבלת דרישת תשלום מביטוח לאומי

💰 סכום: ₪2,340
📅 לתשלום עד: 15/02/2026
📋 אסמכתא: 123456789

━━━━━━━━━━━━━━━━━━━━━━

💡 *מצאתי 3 פתרונות אפשריים:*

1️⃣ *פטור חלקי - הכנסה נמוכה*
   💵 חיסכון: עד ₪1,872 (80%)
   📊 סיכוי: גבוה
   📝 מה לעשות: הגש בקשה לפטור + אישור הכנסה
   🔗 [מידע נוסף](https://www.btl.gov.il/...)

2️⃣ *הסדר חוב - פריסה ל-12 תשלומים*
   💵 חיסכון: ₪0 (אבל מקל על התזרים)
   📊 סיכוי: גבוה מאוד
   📝 מה לעשות: פנה לסניף או התקשר *6050
   🔗 [טופס בקשה](https://www.btl.gov.il/...)

3️⃣ *ערעור - טענת התיישנות*
   💵 חיסכון: ₪2,340 (מלא)
   📊 סיכוי: בינוני (תלוי בתאריכים)
   📝 מה לעשות: בדוק מתי נוצר החוב
   🔗 [כל זכות - ערעור](https://www.kolzchut.org.il/...)

━━━━━━━━━━━━━━━━━━━━━━

⚠️ _מידע כללי בלבד, לא מהווה ייעוץ משפטי או פיננסי._
📊 _חקרתי 4 מקורות ב-8 שניות_

[🔍 פרטים נוספים] [📞 רוצה עזרה?]
```

#### גבולות אתיים

| מותר ✅ | אסור ❌ |
|---------|---------|
| הנחות חוקיות | העלמת מס |
| ערעורים לגיטימיים | מסמכים מזויפים |
| זכאויות לא מנוצלות | הונאה |
| משא ומתן על חובות | שוחד |
| ייעוץ כללי | ייעוץ משפטי ספציפי |
| הפניה למומחה | החלטה בשם המשתמש |

```python
# Ethical boundaries check
def validate_solution_ethics(solution: Solution) -> bool:
    """Ensure solution is ethical and legal."""
    FORBIDDEN_PATTERNS = [
        "העלמת", "הסתרת", "מזויף", "שקר", "הונאה",
        "בריחה מ", "להימנע מדיווח", "לא לדווח"
    ]

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in solution.description_he.lower():
            return False

    # Must have verifiable source
    if not solution.sources or not solution.verified:
        solution.description_he += " (⚠️ לא מאומת)"

    return True
```

#### Disclaimer (חובה)

כל הודעה עם פתרונות חייבת לכלול:

```python
DISCLAIMER_HE = """
⚠️ *הבהרה חשובה*
המידע לעיל הוא מידע כללי בלבד ואינו מהווה ייעוץ משפטי, מיסויי או פיננסי.
לפני קבלת החלטות, מומלץ להתייעץ עם בעל מקצוע מתאים.
המקורות מסופקים לנוחיותך - אמת אותם בעצמך.
"""

DISCLAIMER_EN = """
⚠️ *Important Disclaimer*
The above is general information only and does not constitute legal, tax, or financial advice.
Consult a professional before making decisions.
"""
```

### Google Calendar Integration (אינטגרציית לוח שנה)

**Sources**: [Google Calendar API](https://developers.google.com/calendar/api), [AI Calendar Assistant with n8n](https://medium.com/@naveen_15/building-an-ai-powered-calendar-assistant-how-i-automated-my-scheduling-workflow-with-n8n-and-6073462febbe), [Reclaim.ai](https://reclaim.ai), [FlowHunt Calendar Awareness](https://www.flowhunt.io/ai-flow-templates/personal-ai-assistant-with-google-calendar-schedule-awareness/)

#### למה חיבור ללוח שנה?

> "AI analyzes meeting context, attendees, and historical data to automatically prepare relevant documents and suggest optimal meeting durations."
> — [FlowHunt](https://www.flowhunt.io/ai-flow-templates/personal-ai-assistant-with-google-calendar-schedule-awareness/)

הסוכן צריך להבין את **ההקשר הזמני** של המשתמש:

```
📧 מייל: "נפגש מחר בצהריים?"

❌ ללא לוח שנה:
   "קיבלת בקשה לפגישה מחר בצהריים"

✅ עם לוח שנה:
   "דני מבקש להיפגש מחר 12:00.
    ⚠️ יש לך כבר פגישה 12:00-13:00 עם לקוח.
    💡 אפשרויות פנויות: 10:00, 14:00, 16:00
    [הצע 14:00] [הצע שעה אחרת] [דחה]"
```

#### יכולות האינטגרציה

| יכולת | תיאור | דוגמה |
|-------|-------|-------|
| **Schedule Awareness** | הבנת הלוז | "מחר אתה עסוק מ-9 עד 14" |
| **Conflict Detection** | זיהוי התנגשויות | "יש פגישה באותה שעה" |
| **Meeting Context** | הקשר מהפגישות | "מייל מדני - יש לך פגישה איתו מחר" |
| **Auto-Event Creation** | יצירת אירועים | "הוספתי תזכורת לדד-ליין" |
| **Preparation Alerts** | התראות הכנה | "מחר פגישה עם X - יש 3 מיילים פתוחים איתו" |
| **Time Blocking** | הגנה על זמן | "אל תפריע - שעת Focus" |

#### ארכיטקטורה

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class CalendarEvent:
    """Google Calendar event."""
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str]
    location: str | None
    description: str | None
    is_all_day: bool
    status: str  # "confirmed", "tentative", "cancelled"

@dataclass
class ScheduleContext:
    """User's schedule context for email processing."""
    # Current state
    current_event: CalendarEvent | None      # פגישה עכשיו?
    next_event: CalendarEvent | None         # פגישה הבאה
    is_busy_now: bool
    is_focus_time: bool                      # שעת ריכוז

    # Today's overview
    events_today: list[CalendarEvent]
    free_slots_today: list[tuple[datetime, datetime]]
    busy_percentage_today: float             # % מהיום תפוס

    # This week
    events_this_week: list[CalendarEvent]
    busiest_day: str
    most_free_day: str

    # Related to email
    meetings_with_sender: list[CalendarEvent]  # פגישות עם שולח המייל
    upcoming_deadlines: list[CalendarEvent]    # דד-ליינים קרובים

class CalendarClient:
    """Google Calendar integration."""

    def __init__(self, credentials: Credentials):
        self.service = build('calendar', 'v3', credentials=credentials)

    def get_schedule_context(
        self,
        sender_email: str | None = None,
        days_ahead: int = 7
    ) -> ScheduleContext:
        """Get full schedule context for email processing."""
        now = datetime.now()
        end = now + timedelta(days=days_ahead)

        # Fetch events
        events_result = self.service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = [self._parse_event(e) for e in events_result.get('items', [])]

        # Calculate context
        return ScheduleContext(
            current_event=self._get_current_event(events, now),
            next_event=self._get_next_event(events, now),
            is_busy_now=self._is_busy(events, now),
            is_focus_time=self._is_focus_time(events, now),
            events_today=self._filter_today(events),
            free_slots_today=self._find_free_slots(events, now),
            busy_percentage_today=self._calc_busy_percentage(events),
            events_this_week=events,
            busiest_day=self._find_busiest_day(events),
            most_free_day=self._find_most_free_day(events),
            meetings_with_sender=self._find_meetings_with(events, sender_email) if sender_email else [],
            upcoming_deadlines=self._find_deadlines(events)
        )

    def find_available_slots(
        self,
        duration_minutes: int = 60,
        days_ahead: int = 7,
        working_hours: tuple[int, int] = (9, 18)
    ) -> list[tuple[datetime, datetime]]:
        """Find available time slots."""
        context = self.get_schedule_context(days_ahead=days_ahead)
        available = []

        for day_offset in range(days_ahead):
            day = datetime.now().date() + timedelta(days=day_offset)
            day_events = [e for e in context.events_this_week
                         if e.start.date() == day]

            # Find gaps in working hours
            slots = self._find_gaps(
                day, day_events, duration_minutes, working_hours
            )
            available.extend(slots)

        return available[:10]  # Top 10 options

    def create_event_from_email(
        self,
        email: Email,
        event_type: str,  # "meeting", "deadline", "reminder"
        suggested_time: datetime | None = None
    ) -> CalendarEvent:
        """Create calendar event from email content."""
        if event_type == "deadline":
            # Extract deadline from email
            deadline = self._extract_deadline(email)
            event = {
                'summary': f"📅 דד-ליין: {email.subject[:50]}",
                'description': f"מייל מ: {email.sender}\n\n{email.snippet}",
                'start': {'date': deadline.strftime('%Y-%m-%d')},
                'end': {'date': deadline.strftime('%Y-%m-%d')},
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 24 * 60},  # יום לפני
                        {'method': 'popup', 'minutes': 60},       # שעה לפני
                    ],
                },
            }
        elif event_type == "meeting":
            # Create meeting event
            event = {
                'summary': f"פגישה: {email.sender_name}",
                'description': f"בעקבות: {email.subject}",
                'start': {'dateTime': suggested_time.isoformat()},
                'end': {'dateTime': (suggested_time + timedelta(hours=1)).isoformat()},
                'attendees': [{'email': email.sender_email}],
            }
        else:  # reminder
            event = {
                'summary': f"🔔 תזכורת: {email.subject[:30]}",
                'description': email.snippet,
                'start': {'dateTime': suggested_time.isoformat()},
                'end': {'dateTime': (suggested_time + timedelta(minutes=15)).isoformat()},
            }

        result = self.service.events().insert(
            calendarId='primary',
            body=event
        ).execute()

        return self._parse_event(result)
```

#### Email-Calendar Correlation

```python
class EmailCalendarCorrelator:
    """Correlate emails with calendar events."""

    def __init__(self, calendar: CalendarClient, gmail: GmailClient):
        self.calendar = calendar
        self.gmail = gmail

    def enrich_email_with_calendar(self, email: Email) -> EnrichedEmail:
        """Add calendar context to email."""
        context = self.calendar.get_schedule_context(
            sender_email=email.sender_email
        )

        # Find related meetings
        related_meetings = self._find_related_meetings(email, context)

        # Check for scheduling requests
        scheduling_request = self._detect_scheduling_request(email)

        # Check deadline proximity
        deadline_alert = self._check_deadline_proximity(email, context)

        return EnrichedEmail(
            email=email,
            calendar_context=context,
            related_meetings=related_meetings,
            scheduling_request=scheduling_request,
            deadline_alert=deadline_alert
        )

    def _find_related_meetings(
        self,
        email: Email,
        context: ScheduleContext
    ) -> list[RelatedMeeting]:
        """Find meetings related to this email."""
        related = []

        # 1. Meetings with same sender
        for meeting in context.meetings_with_sender:
            related.append(RelatedMeeting(
                event=meeting,
                relation="same_sender",
                relevance="high"
            ))

        # 2. Meetings with similar subject
        for event in context.events_this_week:
            if self._subjects_similar(email.subject, event.title):
                related.append(RelatedMeeting(
                    event=event,
                    relation="similar_topic",
                    relevance="medium"
                ))

        # 3. Meetings mentioned in email
        mentioned = self._extract_mentioned_meetings(email.body)
        for mention in mentioned:
            matching = self._find_matching_event(mention, context)
            if matching:
                related.append(RelatedMeeting(
                    event=matching,
                    relation="mentioned_in_email",
                    relevance="high"
                ))

        return related

    def _detect_scheduling_request(self, email: Email) -> SchedulingRequest | None:
        """Detect if email is asking to schedule something."""
        SCHEDULING_PATTERNS = [
            r"נפגש ב?(.+)",
            r"בוא נקבע (.+)",
            r"מתי נוח לך",
            r"האם (.+) מתאים",
            r"let'?s meet",
            r"schedule a (call|meeting)",
            r"are you free",
        ]

        for pattern in SCHEDULING_PATTERNS:
            match = re.search(pattern, email.body, re.IGNORECASE)
            if match:
                return SchedulingRequest(
                    type="meeting_request",
                    suggested_time=self._parse_time_mention(match.group(1)),
                    extracted_text=match.group(0)
                )

        return None
```

#### Smart Scheduling Assistant

```python
class SchedulingAssistant:
    """AI-powered scheduling from emails."""

    def __init__(self, calendar: CalendarClient, llm: LLMClient):
        self.calendar = calendar
        self.llm = llm

    async def handle_scheduling_request(
        self,
        email: Email,
        request: SchedulingRequest
    ) -> SchedulingResponse:
        """Handle a scheduling request from email."""

        # Get availability
        available_slots = self.calendar.find_available_slots(
            duration_minutes=60,
            days_ahead=14
        )

        # Get context
        context = self.calendar.get_schedule_context(
            sender_email=email.sender_email
        )

        # Check for conflicts with suggested time
        conflict = None
        if request.suggested_time:
            conflict = self._check_conflict(request.suggested_time, context)

        # Generate response options
        if conflict:
            return SchedulingResponse(
                status="conflict",
                conflict_event=conflict,
                alternatives=available_slots[:5],
                suggested_message=self._generate_conflict_message(
                    conflict, available_slots[:3]
                )
            )
        elif request.suggested_time:
            return SchedulingResponse(
                status="available",
                suggested_time=request.suggested_time,
                suggested_message=self._generate_accept_message(
                    request.suggested_time
                )
            )
        else:
            return SchedulingResponse(
                status="propose",
                alternatives=available_slots[:5],
                suggested_message=self._generate_propose_message(
                    available_slots[:3]
                )
            )

    def _generate_conflict_message(
        self,
        conflict: CalendarEvent,
        alternatives: list[tuple[datetime, datetime]]
    ) -> str:
        """Generate Hebrew message for conflict."""
        alt_times = ", ".join([
            f"{s.strftime('%d/%m %H:%M')}"
            for s, e in alternatives
        ])

        return f"""היי,

השעה הזו לא מתאימה לי (יש לי משהו).
אולי אחת מהשעות האלה?
{alt_times}

מה נוח לך?"""

    def _generate_propose_message(
        self,
        slots: list[tuple[datetime, datetime]]
    ) -> str:
        """Generate Hebrew message proposing times."""
        options = "\n".join([
            f"• {s.strftime('%A %d/%m')} ב-{s.strftime('%H:%M')}"
            for s, e in slots
        ])

        return f"""היי,

בטח, בוא נקבע. אני פנוי ב:
{options}

מה הכי נוח לך?"""
```

#### Calendar-Aware Priority Boost

```python
def adjust_priority_by_calendar(
    email: Email,
    base_priority: Priority,
    calendar_context: ScheduleContext
) -> tuple[Priority, str]:
    """Adjust email priority based on calendar context."""

    # Boost if meeting with sender is soon
    if calendar_context.meetings_with_sender:
        next_meeting = min(
            calendar_context.meetings_with_sender,
            key=lambda e: e.start
        )
        days_until = (next_meeting.start.date() - datetime.now().date()).days

        if days_until <= 1:
            return (
                Priority.P1,
                f"📅 יש לך פגישה עם {email.sender_name} מחר!"
            )
        elif days_until <= 3:
            return (
                max(Priority.P2, base_priority),
                f"📅 פגישה עם {email.sender_name} בעוד {days_until} ימים"
            )

    # Boost if email mentions upcoming event
    for event in calendar_context.events_this_week:
        if event.title.lower() in email.subject.lower():
            return (
                max(Priority.P2, base_priority),
                f"📅 קשור לאירוע: {event.title}"
            )

    # Boost if deadline is soon
    if calendar_context.upcoming_deadlines:
        for deadline in calendar_context.upcoming_deadlines:
            if deadline.title in email.subject:
                days_until = (deadline.start.date() - datetime.now().date()).days
                if days_until <= 2:
                    return (Priority.P1, f"⏰ דד-ליין בעוד {days_until} ימים!")

    return (base_priority, None)
```

#### Telegram Display with Calendar Context

```
📧 מייל מ-דני כהן

📋 *תוכן:*
"היי, נפגש מחר ב-12:00?"

📅 *הקשר מהלוח שנה:*
├─ ⚠️ מחר 12:00 יש לך: "פגישת צוות"
├─ 👤 יש לך פגישה עם דני ביום ג' 15:00
└─ 📊 מחר: 60% תפוס (4 פגישות)

💡 *אפשרויות פנויות מחר:*
• 10:00-11:00
• 14:00-15:00
• 16:00-17:00

━━━━━━━━━━━━━━━━━━━━━━

[✅ הצע 14:00] [📅 הצע שעה אחרת] [❌ דחה]
```

#### Meeting Preparation Alerts

```python
async def generate_meeting_prep_alert(
    event: CalendarEvent,
    gmail: GmailClient,
    hours_before: int = 24
) -> MeetingPrepAlert | None:
    """Generate preparation alert before meeting."""

    # Get attendees
    attendees = event.attendees

    # Search for related emails
    related_emails = []
    for attendee in attendees:
        emails = await gmail.search(
            query=f"from:{attendee}",
            max_results=5
        )
        related_emails.extend(emails)

    # Find unresolved threads
    unresolved = [e for e in related_emails if not e.replied]

    # Find relevant attachments
    attachments = []
    for email in related_emails:
        if email.has_attachments:
            attachments.extend(email.attachments)

    if unresolved or attachments:
        return MeetingPrepAlert(
            event=event,
            unresolved_emails=unresolved,
            relevant_attachments=attachments,
            message=f"""
🔔 *תזכורת: פגישה עם {event.title} בעוד {hours_before} שעות*

📧 יש לך {len(unresolved)} מיילים פתוחים עם המשתתפים:
{chr(10).join(f"• {e.subject[:30]}" for e in unresolved[:3])}

📎 קבצים רלוונטיים:
{chr(10).join(f"• {a.name}" for a in attachments[:3])}

[📖 צפה במיילים] [✅ סמן כמוכן]
"""
        )

    return None
```

#### Focus Time Protection

```python
class FocusTimeProtector:
    """Protect focus time from interruptions."""

    def should_interrupt(
        self,
        email: Email,
        context: ScheduleContext
    ) -> tuple[bool, str]:
        """Decide if email should interrupt focus time."""

        if not context.is_focus_time:
            return (True, "")  # Not in focus time

        # Only P1 interrupts focus time
        if email.priority == Priority.P1:
            return (True, "⚠️ הודעה דחופה בזמן Focus Time")

        # Otherwise, queue for later
        focus_end = context.current_event.end
        return (
            False,
            f"🎯 אתה ב-Focus Time עד {focus_end.strftime('%H:%M')}. "
            f"אעדכן אותך אחרי."
        )

    def get_notification_mode(
        self,
        context: ScheduleContext
    ) -> NotificationMode:
        """Get appropriate notification mode based on schedule."""

        if context.is_focus_time:
            return NotificationMode.SILENT  # P1 only
        elif context.current_event:
            return NotificationMode.QUIET   # P1, P2 only
        else:
            return NotificationMode.NORMAL  # All priorities
```

#### LangGraph Integration

```python
def calendar_context_node(state: EmailState) -> EmailState:
    """Node that adds calendar context to email processing."""
    email = state['email']

    # Get calendar context
    calendar_context = calendar_client.get_schedule_context(
        sender_email=email.sender_email,
        days_ahead=7
    )

    state['calendar_context'] = calendar_context

    # Detect scheduling request
    scheduling_request = correlator._detect_scheduling_request(email)
    if scheduling_request:
        state['scheduling_request'] = scheduling_request

    # Adjust priority based on calendar
    adjusted_priority, reason = adjust_priority_by_calendar(
        email,
        state.get('base_priority', Priority.P3),
        calendar_context
    )

    if reason:
        state['priority'] = adjusted_priority
        state['priority_reason'] = reason

    return state

# Add to graph
workflow.add_node("calendar_context", calendar_context_node)
workflow.add_edge("fetch_emails", "calendar_context")
workflow.add_edge("calendar_context", "context_retrieval")
```

#### Auto-Actions

| טריגר | פעולה אוטומטית | דורש אישור? |
|-------|---------------|-------------|
| מייל עם דד-ליין | יצירת תזכורת בלוח | לא |
| בקשה לפגישה + זמן פנוי | הצעת אישור | כן |
| בקשה לפגישה + התנגשות | הצעת חלופות | כן |
| פגישה מחר | התראת הכנה | לא |
| שעת Focus | השתקת P2-P4 | לא |

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
