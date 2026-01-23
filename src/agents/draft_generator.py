"""Draft Reply Generator - Creates intelligent email reply drafts.

Generates contextual reply drafts based on:
- Email content and tone
- Sender relationship (known contact, organization, etc.)
- Calendar context (availability)
- User preferences

SAFETY: NEVER sends emails automatically - only generates drafts for approval.

ADR-014 Phase 2: Draft Reply Generator
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ToneType(Enum):
    """Email tone types."""

    FORMAL = "formal"  # Official, business
    PROFESSIONAL = "professional"  # Work colleagues
    FRIENDLY = "friendly"  # Known contacts
    CASUAL = "casual"  # Friends, family


class ReplyType(Enum):
    """Types of reply actions."""

    ACKNOWLEDGE = "acknowledge"  # Simple confirmation
    ACCEPT = "accept"  # Accept invitation/request
    DECLINE = "decline"  # Politely decline
    REQUEST_INFO = "request_info"  # Ask for more details
    PROVIDE_INFO = "provide_info"  # Answer a question
    SCHEDULE = "schedule"  # Propose meeting time
    FOLLOWUP = "followup"  # Follow up on previous email


@dataclass
class DraftReply:
    """Generated email reply draft."""

    email_id: str
    reply_type: ReplyType
    tone: ToneType
    subject: str
    body_hebrew: str
    body_english: str | None
    suggested_attachments: list[str]
    calendar_conflicts: list[str]
    confidence: float  # 0-1, how confident the AI is in this draft
    alternatives: list[str]  # Alternative phrasings


# Hebrew reply templates by type
HEBREW_TEMPLATES = {
    ReplyType.ACKNOWLEDGE: [
        "תודה על הפנייה. קיבלתי את הודעתך ואטפל בה בהקדם.",
        "מאשר קבלת המייל. אחזור אליך בהמשך.",
        "שלום, קיבלתי את המייל ואעדכן בהקדם האפשרי.",
    ],
    ReplyType.ACCEPT: [
        "תודה על ההזמנה, אשמח להשתתף.",
        "מאשר את הפגישה. נתראה!",
        "בשמחה, מתאים לי.",
    ],
    ReplyType.DECLINE: [
        "תודה על הפנייה. לצערי, לא אוכל להשתתף בתאריך זה.",
        "מצטער, יש לי התחייבות אחרת באותו זמן. האם יש תאריך חלופי?",
        "מודה על ההזמנה, אך לא אוכל להגיע הפעם.",
    ],
    ReplyType.REQUEST_INFO: [
        "תודה על הפנייה. אשמח לקבל פרטים נוספים לגבי:",
        "לפני שאוכל להשיב, אצטרך מידע נוסף:",
        "האם תוכל לפרט יותר בנוגע ל:",
    ],
    ReplyType.SCHEDULE: [
        "אשמח לתאם פגישה. הזמנים הפנויים שלי הם:",
        "מוזמן לבחור מאחד הזמנים הבאים:",
        "בוא נקבע שיחה. מתאים לי ב:",
    ],
}


class DraftGenerator:
    """Generates intelligent email reply drafts.

    Uses LLM to understand email context and generate appropriate responses.
    NEVER sends emails - only creates drafts for user approval.

    Example:
        generator = DraftGenerator()
        draft = await generator.generate_reply(
            email_subject="בקשה לפגישה",
            email_body="שלום, האם נוכל להיפגש השבוע?",
            sender="colleague@company.com",
            reply_type=ReplyType.SCHEDULE,
            calendar_context=["יום ג 10:00 - פנוי", "יום ד 14:00 - פנוי"]
        )
    """

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
    ):
        """Initialize DraftGenerator.

        Args:
            litellm_url: URL of LiteLLM Gateway
        """
        self.litellm_url = litellm_url

    def _detect_tone(self, sender: str, subject: str, body: str) -> ToneType:
        """Detect the appropriate tone for reply.

        Args:
            sender: Email sender
            subject: Email subject
            body: Email body

        Returns:
            Appropriate tone type
        """
        combined = f"{sender} {subject} {body}".lower()

        # Formal indicators
        formal_patterns = [
            r"gov\.il",
            r"@bank",
            r"משרד",
            r"לכבוד",
            r"בברכה",
            r"dear sir",
            r"official",
        ]
        for pattern in formal_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return ToneType.FORMAL

        # Professional indicators
        professional_patterns = [
            r"@company",
            r"@corp",
            r"meeting",
            r"פגישה",
            r"project",
            r"פרויקט",
        ]
        for pattern in professional_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return ToneType.PROFESSIONAL

        # Casual indicators
        casual_patterns = [
            r"היי",
            r"hey",
            r"מה קורה",
            r"what's up",
            r"@gmail\.com",
            r"@hotmail",
        ]
        for pattern in casual_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return ToneType.FRIENDLY

        return ToneType.PROFESSIONAL  # Default

    def _detect_reply_type(self, subject: str, body: str) -> ReplyType:
        """Detect what type of reply is needed.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Appropriate reply type
        """
        combined = f"{subject} {body}".lower()

        # Meeting/schedule indicators
        if any(
            word in combined
            for word in ["פגישה", "meeting", "לתאם", "schedule", "זמן", "time", "יומן"]
        ):
            return ReplyType.SCHEDULE

        # Information request indicators
        if any(
            word in combined
            for word in ["?", "האם", "מה", "איך", "למה", "what", "how", "why", "can you"]
        ):
            return ReplyType.REQUEST_INFO

        # Invitation indicators
        if any(
            word in combined
            for word in ["הזמנה", "invitation", "invite", "מוזמן", "invited"]
        ):
            return ReplyType.ACCEPT  # Default to accept, user can change

        # Follow-up indicators
        if any(
            word in combined
            for word in ["המשך", "follow", "עדכון", "update", "תזכורת", "reminder"]
        ):
            return ReplyType.FOLLOWUP

        return ReplyType.ACKNOWLEDGE  # Default

    async def _generate_with_llm(
        self,
        email_subject: str,
        email_body: str,
        sender: str,
        reply_type: ReplyType,
        tone: ToneType,
        calendar_context: list[str] | None = None,
        user_notes: str | None = None,
    ) -> dict:
        """Generate reply using LLM.

        Args:
            email_subject: Original email subject
            email_body: Original email body
            sender: Email sender
            reply_type: Type of reply needed
            tone: Tone to use
            calendar_context: List of free/busy times
            user_notes: Additional notes from user

        Returns:
            Generated reply data
        """
        from openai import AsyncOpenAI

        tone_instructions = {
            ToneType.FORMAL: "רשמי ומכובד, עם פנייה מנומסת",
            ToneType.PROFESSIONAL: "מקצועי וברור, ידידותי אך עניני",
            ToneType.FRIENDLY: "ידידותי וחם, אך מכובד",
            ToneType.CASUAL: "קליל ולא רשמי, כמו לחבר",
        }

        reply_instructions = {
            ReplyType.ACKNOWLEDGE: "אשר קבלת המייל והבטח מענה בהמשך",
            ReplyType.ACCEPT: "קבל את ההזמנה/בקשה בצורה חיובית",
            ReplyType.DECLINE: "סרב בנימוס, הצע חלופה אם אפשר",
            ReplyType.REQUEST_INFO: "בקש מידע נוסף לפני מתן תשובה",
            ReplyType.PROVIDE_INFO: "ספק את המידע המבוקש בצורה ברורה",
            ReplyType.SCHEDULE: "הצע זמנים לפגישה מתוך הזמנים הפנויים",
            ReplyType.FOLLOWUP: "עקוב אחרי הנושא, בקש עדכון",
        }

        prompt = f"""אתה עוזר שכותב טיוטות מיילים בעברית.

## המייל המקורי
נושא: {email_subject}
מאת: {sender}
תוכן:
{email_body}

## סוג התשובה הנדרש
{reply_instructions.get(reply_type, "תשובה כללית")}

## טון נדרש
{tone_instructions.get(tone, "מקצועי")}

{f"## הקשר יומן (זמנים פנויים){chr(10)}" + chr(10).join(calendar_context) if calendar_context else ""}

{f"## הערות נוספות{chr(10)}{user_notes}" if user_notes else ""}

## המשימה שלך
כתוב טיוטת תשובה למייל. התשובה צריכה להיות:
1. בעברית (אלא אם המייל המקורי באנגלית)
2. בטון המתאים
3. קצרה וממוקדת
4. מנומסת ומקצועית

## פורמט התשובה (JSON)
{{
  "subject": "RE: נושא מתאים",
  "body": "תוכן התשובה בעברית",
  "body_english": "English version if original was in English, null otherwise",
  "key_points": ["נקודה 1", "נקודה 2"],
  "suggested_attachments": ["מסמך שכדאי לצרף"],
  "alternative_phrases": ["ניסוח חלופי 1", "ניסוח חלופי 2"],
  "confidence": 0.85,
  "warnings": ["אזהרה אם יש משהו שצריך לשים לב אליו"]
}}

ענה רק ב-JSON."""

        try:
            client = AsyncOpenAI(base_url=self.litellm_url, api_key="dummy")

            response = await client.chat.completions.create(
                model="claude-sonnet",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
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
            logger.error(f"LLM draft generation failed: {e}")

            # Fallback to template
            templates = HEBREW_TEMPLATES.get(reply_type, HEBREW_TEMPLATES[ReplyType.ACKNOWLEDGE])
            return {
                "subject": f"RE: {email_subject}",
                "body": templates[0],
                "body_english": None,
                "key_points": [],
                "suggested_attachments": [],
                "alternative_phrases": templates[1:],
                "confidence": 0.3,
                "warnings": ["נוצר מתבנית עקב שגיאה"],
            }

    async def generate_reply(
        self,
        email_id: str,
        email_subject: str,
        email_body: str,
        sender: str,
        reply_type: ReplyType | None = None,
        tone: ToneType | None = None,
        calendar_context: list[str] | None = None,
        user_notes: str | None = None,
    ) -> DraftReply:
        """Generate a reply draft for an email.

        Args:
            email_id: ID of the email being replied to
            email_subject: Original email subject
            email_body: Original email body/snippet
            sender: Email sender
            reply_type: Type of reply (auto-detected if None)
            tone: Tone to use (auto-detected if None)
            calendar_context: Free/busy times for scheduling
            user_notes: Additional context from user

        Returns:
            DraftReply with the generated draft
        """
        # Auto-detect if not specified
        if tone is None:
            tone = self._detect_tone(sender, email_subject, email_body)

        if reply_type is None:
            reply_type = self._detect_reply_type(email_subject, email_body)

        logger.info(f"Generating {reply_type.value} reply with {tone.value} tone")

        # Generate with LLM
        result = await self._generate_with_llm(
            email_subject=email_subject,
            email_body=email_body,
            sender=sender,
            reply_type=reply_type,
            tone=tone,
            calendar_context=calendar_context,
            user_notes=user_notes,
        )

        return DraftReply(
            email_id=email_id,
            reply_type=reply_type,
            tone=tone,
            subject=result.get("subject", f"RE: {email_subject}"),
            body_hebrew=result.get("body", ""),
            body_english=result.get("body_english"),
            suggested_attachments=result.get("suggested_attachments", []),
            calendar_conflicts=result.get("warnings", []),
            confidence=result.get("confidence", 0.5),
            alternatives=result.get("alternative_phrases", []),
        )

    async def generate_batch(
        self,
        emails: list[dict],
        calendar_context: list[str] | None = None,
    ) -> list[DraftReply]:
        """Generate drafts for multiple emails.

        Args:
            emails: List of email dicts
            calendar_context: Shared calendar context

        Returns:
            List of DraftReply objects
        """
        drafts = []

        for email in emails:
            draft = await self.generate_reply(
                email_id=email.get("id", ""),
                email_subject=email.get("subject", ""),
                email_body=email.get("snippet", ""),
                sender=email.get("from", ""),
                calendar_context=calendar_context,
            )
            drafts.append(draft)

        return drafts

    def format_draft_for_telegram(self, draft: DraftReply) -> str:
        """Format a draft for Telegram display.

        Args:
            draft: The generated draft

        Returns:
            Formatted Telegram message
        """
        confidence_emoji = "🟢" if draft.confidence > 0.7 else "🟡" if draft.confidence > 0.4 else "🔴"

        lines = [
            f"✉️ *טיוטת תשובה*",
            f"",
            f"*נושא:* {draft.subject}",
            f"*סוג:* {draft.reply_type.value} | *טון:* {draft.tone.value}",
            f"*ביטחון:* {confidence_emoji} {int(draft.confidence * 100)}%",
            f"",
            f"━━━━━━━━━━━━━━━",
            f"",
            f"{draft.body_hebrew}",
            f"",
            f"━━━━━━━━━━━━━━━",
        ]

        if draft.suggested_attachments:
            lines.append("")
            lines.append("📎 *מומלץ לצרף:*")
            for att in draft.suggested_attachments:
                lines.append(f"• {att}")

        if draft.alternatives:
            lines.append("")
            lines.append("🔄 *ניסוחים חלופיים:*")
            for i, alt in enumerate(draft.alternatives[:2], 1):
                lines.append(f"{i}. {alt[:100]}...")

        lines.append("")
        lines.append("_⚠️ זו טיוטה בלבד - לא נשלחה!_")

        return "\n".join(lines)


async def main() -> None:
    """Test DraftGenerator."""
    logging.basicConfig(level=logging.INFO)

    generator = DraftGenerator()

    # Test with a meeting request
    draft = await generator.generate_reply(
        email_id="test123",
        email_subject="בקשה לפגישה",
        email_body="שלום, האם נוכל לתאם פגישה השבוע לדון בפרויקט החדש?",
        sender="colleague@company.com",
        calendar_context=[
            "יום ג 10:00-11:00 - פנוי",
            "יום ד 14:00-15:00 - פנוי",
            "יום ה 09:00-10:00 - פנוי",
        ],
    )

    print("\n=== Generated Draft ===")
    print(f"Subject: {draft.subject}")
    print(f"Type: {draft.reply_type.value}")
    print(f"Tone: {draft.tone.value}")
    print(f"Confidence: {draft.confidence}")
    print(f"\nBody:\n{draft.body_hebrew}")

    print("\n=== Telegram Format ===")
    print(generator.format_draft_for_telegram(draft))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
