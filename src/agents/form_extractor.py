"""Form Extractor - Extracts and pre-fills forms from emails and websites.

Analyzes emails for form requirements, extracts form fields from URLs,
and prepares pre-filled data for the user.

SAFETY: NEVER submits forms automatically - only prepares data for user review.

ADR-014 Phase 3: Form Extraction and Pre-filling
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FormFieldType(Enum):
    """Types of form fields."""

    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    ID_NUMBER = "id_number"  # Israeli ID
    ADDRESS = "address"
    FILE_UPLOAD = "file"
    CHECKBOX = "checkbox"
    SELECT = "select"
    TEXTAREA = "textarea"


@dataclass
class FormField:
    """A single form field."""

    name: str
    field_type: FormFieldType
    label: str
    required: bool = False
    suggested_value: str | None = None
    options: list[str] = field(default_factory=list)  # For select fields
    validation_pattern: str | None = None


@dataclass
class ExtractedForm:
    """Extracted form data from email or website."""

    source_email_id: str
    form_url: str | None
    form_title: str
    organization: str
    fields: list[FormField]
    required_documents: list[str]
    deadline: str | None
    pre_filled_data: dict[str, str]
    instructions: list[str]
    estimated_time: str


# Known form patterns for Israeli government/banks
KNOWN_FORM_PATTERNS = {
    "ביטוח לאומי": {
        "common_fields": [
            FormField("id_number", FormFieldType.ID_NUMBER, "מספר זהות", required=True),
            FormField("full_name", FormFieldType.TEXT, "שם מלא", required=True),
            FormField("birth_date", FormFieldType.DATE, "תאריך לידה", required=True),
            FormField("address", FormFieldType.ADDRESS, "כתובת מגורים", required=True),
            FormField("phone", FormFieldType.PHONE, "טלפון", required=True),
            FormField("email", FormFieldType.EMAIL, "דוא\"ל"),
            FormField("bank_account", FormFieldType.TEXT, "מספר חשבון בנק"),
        ],
        "common_documents": [
            "צילום תעודת זהות",
            "אישור תושב",
            "תלושי שכר (3 אחרונים)",
        ],
    },
    "מס הכנסה": {
        "common_fields": [
            FormField("id_number", FormFieldType.ID_NUMBER, "מספר זהות", required=True),
            FormField("tax_year", FormFieldType.SELECT, "שנת מס", required=True),
            FormField("income_type", FormFieldType.SELECT, "סוג הכנסה"),
            FormField("employer_id", FormFieldType.TEXT, "מספר מעסיק"),
        ],
        "common_documents": [
            "טופס 106",
            "אישורי ניכוי מס",
            "קבלות על תרומות",
        ],
    },
    "משרד הפנים": {
        "common_fields": [
            FormField("id_number", FormFieldType.ID_NUMBER, "מספר זהות", required=True),
            FormField("full_name", FormFieldType.TEXT, "שם מלא", required=True),
            FormField("father_name", FormFieldType.TEXT, "שם האב"),
            FormField("mother_name", FormFieldType.TEXT, "שם האם"),
            FormField("birth_date", FormFieldType.DATE, "תאריך לידה", required=True),
            FormField("birth_country", FormFieldType.TEXT, "ארץ לידה"),
        ],
        "common_documents": [
            "תמונת פספורט",
            "צילום תעודת זהות",
            "אישור כתובת",
        ],
    },
    "בנק": {
        "common_fields": [
            FormField("id_number", FormFieldType.ID_NUMBER, "מספר זהות", required=True),
            FormField("account_number", FormFieldType.TEXT, "מספר חשבון", required=True),
            FormField("branch", FormFieldType.TEXT, "סניף"),
        ],
        "common_documents": [
            "תעודת זהות",
            "אסמכתא על הכנסה",
        ],
    },
}


class FormExtractor:
    """Extracts form data from emails and prepares pre-filled information.

    Analyzes email content to identify required forms, extracts field
    information, and prepares data for user review.

    SAFETY: Never submits forms - only prepares data.

    Example:
        extractor = FormExtractor()
        form = await extractor.extract_from_email(
            email_subject="דרישה להשלמת מסמכים",
            email_body="יש להגיש טופס תביעה...",
            sender="noreply@btl.gov.il",
            user_profile={"id_number": "123456789", "name": "ישראל ישראלי"}
        )
    """

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
    ):
        """Initialize FormExtractor.

        Args:
            litellm_url: URL of LiteLLM Gateway for AI analysis
        """
        self.litellm_url = litellm_url

    def _identify_organization(self, sender: str, subject: str, body: str) -> str | None:
        """Identify the organization from email content.

        Args:
            sender: Email sender
            subject: Email subject
            body: Email body

        Returns:
            Organization name if identified
        """
        combined = f"{sender} {subject} {body}".lower()

        patterns = {
            r"btl\.gov\.il|ביטוח לאומי": "ביטוח לאומי",
            r"taxes\.gov\.il|מס הכנסה": "מס הכנסה",
            r"משרד הפנים|piba\.gov\.il": "משרד הפנים",
            r"bank|בנק": "בנק",
        }

        for pattern, org in patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                return org

        return None

    def _extract_form_urls(self, text: str) -> list[str]:
        """Extract form URLs from text.

        Args:
            text: Text to search

        Returns:
            List of form URLs
        """
        # Common patterns for form URLs
        url_pattern = r'https?://[^\s<>"\']+(?:form|טופס|pdf|doc)[^\s<>"\']*'
        urls = re.findall(url_pattern, text, re.IGNORECASE)

        # Also look for general gov.il URLs
        gov_pattern = r'https?://[^\s<>"\']*gov\.il[^\s<>"\']*'
        gov_urls = re.findall(gov_pattern, text)

        return list(set(urls + gov_urls))

    def _extract_required_documents(self, text: str) -> list[str]:
        """Extract required documents from text.

        Args:
            text: Text to search

        Returns:
            List of required documents
        """
        documents = []

        # Common document patterns in Hebrew
        doc_patterns = [
            r"צילום תעודת זהות",
            r"אישור תושב",
            r"תלוש(?:י)? שכר",
            r"טופס 106",
            r"אישור(?:י)? ניכוי",
            r"קבל(?:ה|ות)",
            r"תמונ(?:ה|ות) פספורט",
            r"אסמכת(?:א|אות)",
            r"חוזה",
            r"דוח",
            r"אישור רפואי",
            r"מסמך(?:ים)?",
        ]

        for pattern in doc_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            documents.extend(matches)

        return list(set(documents))

    def _extract_deadline_from_text(self, text: str) -> str | None:
        """Extract deadline from text.

        Args:
            text: Text to search

        Returns:
            Deadline string if found
        """
        patterns = [
            r"עד (?:ה?)(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)",
            r"עד לתאריך (\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)",
            r"תוך (\d+) (ימים|שעות|שבועות)",
            r"דדליין[:\s]+(\d{1,2}[./]\d{1,2})",
            r"(?:by|until)\s+(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    async def _analyze_with_llm(
        self,
        email_subject: str,
        email_body: str,
        organization: str | None,
    ) -> dict:
        """Use LLM to analyze email and extract form requirements.

        Args:
            email_subject: Email subject
            email_body: Email body
            organization: Identified organization

        Returns:
            Analysis with form requirements
        """
        from openai import AsyncOpenAI

        prompt = f"""אתה מומחה בניתוח מיילים ממוסדות וזיהוי דרישות טפסים.

## המייל
נושא: {email_subject}
תוכן:
{email_body[:2000]}

## מקור זוהה
{organization or "לא זוהה"}

## המשימה שלך
נתח את המייל וזהה:
1. אילו טפסים צריך למלא?
2. אילו שדות נדרשים בכל טופס?
3. אילו מסמכים צריך לצרף?
4. מה הדדליין?
5. הוראות ספציפיות

## פורמט התשובה (JSON)
{{
  "forms_needed": [
    {{
      "name": "שם הטופס",
      "url": "קישור אם יש",
      "purpose": "מטרת הטופס"
    }}
  ],
  "fields_required": [
    {{
      "name": "שם השדה",
      "type": "text|email|phone|date|id_number|address|file|select",
      "label": "תווית בעברית",
      "required": true
    }}
  ],
  "documents_needed": ["מסמך 1", "מסמך 2"],
  "deadline": "DD/MM/YYYY או null",
  "instructions": ["הוראה 1", "הוראה 2"],
  "estimated_time_minutes": 15,
  "difficulty": "easy|medium|hard"
}}

ענה רק ב-JSON."""

        try:
            client = AsyncOpenAI(base_url=self.litellm_url, api_key="dummy")

            response = await client.chat.completions.create(
                model="claude-sonnet",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1500,
            )

            content = response.choices[0].message.content

            # Clean markdown
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]

            return json.loads(content.strip())

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "forms_needed": [],
                "fields_required": [],
                "documents_needed": [],
                "deadline": None,
                "instructions": [],
                "estimated_time_minutes": 30,
                "difficulty": "unknown",
            }

    def _create_pre_filled_data(
        self,
        fields: list[FormField],
        user_profile: dict[str, str],
    ) -> dict[str, str]:
        """Create pre-filled data from user profile.

        Args:
            fields: Form fields
            user_profile: User's saved profile data

        Returns:
            Dict of field_name -> pre-filled value
        """
        pre_filled = {}

        # Mapping from field names to profile keys
        field_mapping = {
            "id_number": ["id_number", "id", "teudat_zehut"],
            "full_name": ["name", "full_name", "שם"],
            "email": ["email", "mail"],
            "phone": ["phone", "mobile", "טלפון"],
            "address": ["address", "כתובת"],
            "birth_date": ["birth_date", "birthday", "תאריך_לידה"],
        }

        for field_obj in fields:
            # Check if we have this field in profile
            possible_keys = field_mapping.get(field_obj.name, [field_obj.name])

            for key in possible_keys:
                if key in user_profile and user_profile[key]:
                    pre_filled[field_obj.name] = user_profile[key]
                    break

        return pre_filled

    async def extract_from_email(
        self,
        email_id: str,
        email_subject: str,
        email_body: str,
        sender: str,
        user_profile: dict[str, str] | None = None,
    ) -> ExtractedForm | None:
        """Extract form data from an email.

        Args:
            email_id: Email ID
            email_subject: Email subject
            email_body: Email body/snippet
            sender: Email sender
            user_profile: User's saved profile for pre-filling

        Returns:
            ExtractedForm with all extracted data, or None if no form found
        """
        user_profile = user_profile or {}

        # Identify organization
        organization = self._identify_organization(sender, email_subject, email_body)

        if not organization:
            logger.info("No known organization identified in email")
            return None

        # Extract URLs
        form_urls = self._extract_form_urls(email_body)

        # Extract documents from text
        text_documents = self._extract_required_documents(email_body)

        # Extract deadline
        deadline = self._extract_deadline_from_text(email_body)

        # LLM analysis for detailed extraction
        analysis = await self._analyze_with_llm(email_subject, email_body, organization)

        # Get known fields for this organization
        known_patterns = KNOWN_FORM_PATTERNS.get(organization, {})
        known_fields = known_patterns.get("common_fields", [])
        known_documents = known_patterns.get("common_documents", [])

        # Build fields list from LLM + known patterns
        fields = []
        for field_data in analysis.get("fields_required", []):
            field_type = FormFieldType.TEXT
            try:
                field_type = FormFieldType(field_data.get("type", "text"))
            except ValueError:
                pass

            fields.append(
                FormField(
                    name=field_data.get("name", ""),
                    field_type=field_type,
                    label=field_data.get("label", ""),
                    required=field_data.get("required", False),
                )
            )

        # Add known fields that aren't already present
        existing_names = {f.name for f in fields}
        for known_field in known_fields:
            if known_field.name not in existing_names:
                fields.append(known_field)

        # Combine documents
        all_documents = list(
            set(text_documents + analysis.get("documents_needed", []) + known_documents)
        )

        # Create pre-filled data
        pre_filled = self._create_pre_filled_data(fields, user_profile)

        # Build form title
        forms_needed = analysis.get("forms_needed", [])
        form_title = forms_needed[0]["name"] if forms_needed else f"טופס {organization}"

        # Estimated time
        est_minutes = analysis.get("estimated_time_minutes", 30)
        estimated_time = f"{est_minutes} דקות" if est_minutes < 60 else f"{est_minutes // 60} שעות"

        return ExtractedForm(
            source_email_id=email_id,
            form_url=form_urls[0] if form_urls else None,
            form_title=form_title,
            organization=organization,
            fields=fields,
            required_documents=all_documents,
            deadline=deadline or analysis.get("deadline"),
            pre_filled_data=pre_filled,
            instructions=analysis.get("instructions", []),
            estimated_time=estimated_time,
        )

    def format_for_telegram(self, form: ExtractedForm) -> str:
        """Format extracted form for Telegram display.

        Args:
            form: Extracted form data

        Returns:
            Formatted Telegram message
        """
        lines = [
            f"📝 *{form.form_title}*",
            f"🏢 {form.organization}",
            "",
        ]

        if form.deadline:
            lines.append(f"⏰ *דדליין:* {form.deadline}")
            lines.append("")

        lines.append(f"⏱️ *זמן משוער:* {form.estimated_time}")
        lines.append("")

        # Required fields
        required_fields = [f for f in form.fields if f.required]
        if required_fields:
            lines.append("📋 *שדות חובה:*")
            for field_obj in required_fields[:5]:
                status = "✅" if field_obj.name in form.pre_filled_data else "⬜"
                lines.append(f"  {status} {field_obj.label}")
            lines.append("")

        # Pre-filled data
        if form.pre_filled_data:
            lines.append(f"✨ *מידע מוכן ({len(form.pre_filled_data)} שדות):*")
            for name, value in list(form.pre_filled_data.items())[:3]:
                # Mask sensitive data
                if "id" in name.lower():
                    display_value = value[:3] + "***" + value[-2:]
                else:
                    display_value = value[:20] + "..." if len(value) > 20 else value
                lines.append(f"  • {display_value}")
            lines.append("")

        # Required documents
        if form.required_documents:
            lines.append("📎 *מסמכים נדרשים:*")
            for doc in form.required_documents[:5]:
                lines.append(f"  • {doc}")
            lines.append("")

        # Instructions
        if form.instructions:
            lines.append("📌 *הוראות:*")
            for i, instruction in enumerate(form.instructions[:3], 1):
                lines.append(f"  {i}. {instruction[:50]}...")
            lines.append("")

        # Link
        if form.form_url:
            lines.append(f"🔗 [פתח טופס]({form.form_url})")
        else:
            lines.append("🔗 _קישור לטופס לא זמין_")

        lines.append("")
        lines.append("_⚠️ הטופס לא נשלח - רק הוכן עבורך!_")

        return "\n".join(lines)


async def main() -> None:
    """Test FormExtractor."""
    logging.basicConfig(level=logging.INFO)

    extractor = FormExtractor()

    # Test with a sample email
    form = await extractor.extract_from_email(
        email_id="test123",
        email_subject="דרישה להשלמת מסמכים - ביטוח לאומי",
        email_body="""
        שלום,

        עליך להגיש את המסמכים הבאים עד 30/01/2026:
        - צילום תעודת זהות
        - אישור תושב
        - תלושי שכר 3 חודשים אחרונים

        למילוי הטופס: https://www.btl.gov.il/forms/unemployment

        בברכה,
        ביטוח לאומי
        """,
        sender="noreply@btl.gov.il",
        user_profile={
            "id_number": "123456789",
            "name": "ישראל ישראלי",
            "email": "israel@example.com",
            "phone": "050-1234567",
        },
    )

    if form:
        print("\n=== Extracted Form ===")
        print(f"Title: {form.form_title}")
        print(f"Organization: {form.organization}")
        print(f"Deadline: {form.deadline}")
        print(f"Fields: {len(form.fields)}")
        print(f"Documents: {form.required_documents}")
        print(f"Pre-filled: {list(form.pre_filled_data.keys())}")

        print("\n=== Telegram Format ===")
        print(extractor.format_for_telegram(form))
    else:
        print("No form extracted")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
