"""Smart Email Agent - Intelligent email analysis with Telegram delivery.

Scans Gmail inbox daily, classifies emails, understands calendar context,
suggests actions, and delivers a friendly summary to Telegram.

ADR-014: Smart Email Agent with Telegram Integration

Phase 1 Features:
- P1-P4 priority classification with Hebrew categories
- Calendar context awareness (today's schedule)
- Smart action suggestions (drafts, not auto-send)
- Form/link extraction for bureaucracy
- Friendly Hebrew Telegram formatting

Phase 2 Features (NEW):
- Web research for bureaucracy emails (government sites, banks)
- Draft reply generator with tone matching
- Sender history lookup (past conversations)
- Enhanced action suggestions

Safety Rules (Non-Negotiable):
- NEVER sends emails automatically
- NEVER makes payments
- NEVER submits forms
- Only suggests, drafts, and presents
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import httpx

from src.agents.gmail_client import GmailClient, GmailMessage

logger = logging.getLogger(__name__)


class EmailCategory(Enum):
    """Email categories with Hebrew names."""

    BUREAUCRACY = "בירוקרטיה"  # Government, taxes, official
    FINANCE = "כספים"  # Banks, payments, invoices
    URGENT = "דחוף"  # Deadlines within 48h
    CALENDAR = "יומן"  # Meetings, appointments
    ACTION_REQUIRED = "דורש פעולה"  # Tasks, requests
    INFORMATIONAL = "מידע"  # Newsletters, updates
    PROMOTIONAL = "פרסום"  # Marketing, sales
    PERSONAL = "אישי"  # Friends, family


class Priority(Enum):
    """Email priority levels."""

    P1 = 1  # Urgent - needs attention today
    P2 = 2  # Important - needs attention this week
    P3 = 3  # Informational - nice to know
    P4 = 4  # Low - can be ignored/archived


@dataclass
class EmailItem:
    """Processed email item."""

    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    date: str
    snippet: str
    body: str = ""
    category: EmailCategory = EmailCategory.INFORMATIONAL
    priority: Priority = Priority.P3
    deadline: str | None = None
    action_required: str | None = None
    suggested_reply: str | None = None
    links: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    amount: str | None = None  # For finance emails


@dataclass
class CalendarEvent:
    """Calendar event for context."""

    id: str
    summary: str
    start: str
    end: str
    location: str = ""


@dataclass
class DailySummary:
    """Daily email summary for Telegram."""

    date: str
    total_emails: int
    p1_count: int
    p2_count: int
    p3_count: int
    p4_count: int
    emails: list[EmailItem]
    calendar_events: list[CalendarEvent]
    suggested_actions: list[str]


class EmailAgent:
    """Smart Email Agent that scans, classifies, and summarizes emails.

    Uses MCP Gateway for Gmail and Calendar access, LiteLLM for AI analysis.

    Example:
        agent = EmailAgent()
        summary = await agent.run()
        await agent.send_to_telegram(summary)
    """

    AGENT_NAME = "email_agent"

    # Patterns for classification
    BUREAUCRACY_PATTERNS = [
        r"משרד",
        r"ממשל",
        r"gov\.il",
        r"ביטוח לאומי",
        r"מס הכנסה",
        r"עירייה",
        r"משטרה",
        r"בית משפט",
        r"רשות",
        r"ministry",
        r"government",
    ]

    FINANCE_PATTERNS = [
        r"בנק",
        r"bank",
        r"חשבונית",
        r"invoice",
        r"תשלום",
        r"payment",
        r"אשראי",
        r"credit",
        r"₪",
        r"\$",
        r"€",
        r"חיוב",
        r"charge",
    ]

    URGENT_PATTERNS = [
        r"דחוף",
        r"urgent",
        r"מיידי",
        r"immediate",
        r"אחרון",
        r"last chance",
        r"deadline",
        r"expires",
        r"תוך \d+ (ימים|שעות)",
        r"within \d+ (days|hours)",
    ]

    def __init__(
        self,
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
    ):
        """Initialize EmailAgent.

        Args:
            litellm_url: URL of LiteLLM Gateway (for AI analysis)
        """
        self.litellm_url = litellm_url
        self._gmail_client: GmailClient | None = None
        self._telegram_token: str | None = None
        self._telegram_chat_id: str | None = None

    def _get_gmail_client(self) -> GmailClient:
        """Get or create Gmail client."""
        if self._gmail_client is None:
            self._gmail_client = GmailClient()
        return self._gmail_client

    def _load_telegram_config(self) -> tuple[str, str]:
        """Load Telegram bot token and chat ID.

        Returns:
            Tuple of (bot_token, chat_id)
        """
        if self._telegram_token and self._telegram_chat_id:
            return self._telegram_token, self._telegram_chat_id

        # Try environment first
        self._telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self._telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if self._telegram_token and self._telegram_chat_id:
            return self._telegram_token, self._telegram_chat_id

        # Try GCP Secret Manager
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            if not self._telegram_token:
                self._telegram_token = manager.get_secret("TELEGRAM-BOT-TOKEN")
            if not self._telegram_chat_id:
                self._telegram_chat_id = manager.get_secret("TELEGRAM-CHAT-ID")
        except Exception as e:
            logger.warning(f"Could not get Telegram config from Secret Manager: {e}")

        if not self._telegram_token or not self._telegram_chat_id:
            raise ValueError("Telegram config not found in env or Secret Manager")

        return self._telegram_token, self._telegram_chat_id

    def _fetch_emails(self, hours: int = 24) -> list[GmailMessage]:
        """Fetch unread emails from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of GmailMessage objects
        """
        try:
            gmail = self._get_gmail_client()
            return gmail.get_unread_emails(hours=hours, max_results=50)
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            return []

    def _fetch_email_body(self, message_id: str) -> str:
        """Fetch full email body.

        Args:
            message_id: Gmail message ID

        Returns:
            Email body text (using snippet for now)
        """
        # Full body fetching would require an additional API call
        # For daily summaries, snippet is sufficient
        return ""

    def _fetch_calendar_events(self) -> list[CalendarEvent]:
        """Fetch today's calendar events.

        Returns:
            List of today's events (empty for now - TODO: add CalendarClient)
        """
        # Calendar integration requires separate OAuth scope
        # TODO: Implement CalendarClient similar to GmailClient
        return []

    def _extract_sender_email(self, from_field: str) -> str:
        """Extract email address from From field.

        Args:
            from_field: Full From field (e.g., "Name <email@example.com>")

        Returns:
            Email address only
        """
        match = re.search(r"<([^>]+)>", from_field)
        if match:
            return match.group(1)
        return from_field

    def _classify_email(self, email: GmailMessage) -> tuple[EmailCategory, Priority]:
        """Classify email by category and priority.

        Args:
            email: GmailMessage object

        Returns:
            Tuple of (category, priority)
        """
        subject = email.subject.lower()
        sender = f"{email.sender} {email.sender_email}".lower()
        snippet = email.snippet.lower()
        combined = f"{subject} {sender} {snippet}"

        # P5-style filter: Skip automated/system emails (GitHub, noreply, etc.)
        system_patterns = [
            "github.com", "noreply", "notifications@", "no-reply",
            "automated", "jenkins", "gitlab", "bitbucket"
        ]
        if any(pattern in sender for pattern in system_patterns):
            return EmailCategory.INFORMATIONAL, Priority.P4

        # Check patterns in order of priority
        for pattern in self.URGENT_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return EmailCategory.URGENT, Priority.P1

        for pattern in self.BUREAUCRACY_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return EmailCategory.BUREAUCRACY, Priority.P1

        for pattern in self.FINANCE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return EmailCategory.FINANCE, Priority.P1

        # Calendar/meeting detection
        if any(
            word in combined
            for word in ["meeting", "פגישה", "calendar", "יומן", "invite", "הזמנה"]
        ):
            return EmailCategory.CALENDAR, Priority.P2

        # Action required detection
        if any(
            word in combined
            for word in [
                "please",
                "בבקשה",
                "action",
                "פעולה",
                "respond",
                "תגובה",
                "confirm",
                "אישור",
            ]
        ):
            return EmailCategory.ACTION_REQUIRED, Priority.P2

        # Promotional detection
        if any(
            word in combined
            for word in [
                "sale",
                "מבצע",
                "discount",
                "הנחה",
                "unsubscribe",
                "הסר",
                "newsletter",
            ]
        ):
            return EmailCategory.PROMOTIONAL, Priority.P4

        # Default to informational
        return EmailCategory.INFORMATIONAL, Priority.P3

    def _extract_links(self, text: str) -> list[str]:
        """Extract URLs from text.

        Args:
            text: Text to search

        Returns:
            List of URLs found
        """
        url_pattern = r"https?://[^\s<>\"']+"
        return re.findall(url_pattern, text)

    def _extract_deadline(self, text: str) -> str | None:
        """Extract deadline from text.

        Args:
            text: Text to search

        Returns:
            Deadline string if found
        """
        # Hebrew patterns
        hebrew_patterns = [
            r"עד (?:ה?)(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)",
            r"תוך (\d+) (ימים|שעות|שבועות)",
            r"דדליין[:\s]+(\d{1,2}[./]\d{1,2})",
        ]

        # English patterns
        english_patterns = [
            r"(?:by|until|before)\s+(\w+\s+\d{1,2}(?:,?\s+\d{4})?)",
            r"deadline[:\s]+(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)",
            r"within (\d+)\s+(days?|hours?|weeks?)",
        ]

        for pattern in hebrew_patterns + english_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    def _extract_amount(self, text: str) -> str | None:
        """Extract monetary amount from text.

        Args:
            text: Text to search

        Returns:
            Amount string if found
        """
        patterns = [
            r"₪\s*[\d,]+(?:\.\d{2})?",
            r"\$\s*[\d,]+(?:\.\d{2})?",
            r"€\s*[\d,]+(?:\.\d{2})?",
            r"[\d,]+(?:\.\d{2})?\s*(?:₪|\$|€|ש\"ח|שקל)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    def _process_email(self, gmail_msg: GmailMessage) -> EmailItem:
        """Process a GmailMessage into an EmailItem.

        Args:
            gmail_msg: GmailMessage from GmailClient

        Returns:
            Processed EmailItem
        """
        category, priority = self._classify_email(gmail_msg)

        combined_text = f"{gmail_msg.subject} {gmail_msg.snippet}"

        return EmailItem(
            id=gmail_msg.id,
            thread_id=gmail_msg.thread_id,
            subject=gmail_msg.subject,
            sender=gmail_msg.sender,
            sender_email=gmail_msg.sender_email,
            date=gmail_msg.date,
            snippet=gmail_msg.snippet,
            category=category,
            priority=priority,
            deadline=self._extract_deadline(combined_text),
            links=self._extract_links(combined_text),
            amount=self._extract_amount(combined_text),
        )

    async def _generate_smart_analysis(self, emails: list[EmailItem]) -> dict:
        """Use LLM to generate smart analysis and suggestions.

        Args:
            emails: List of processed emails

        Returns:
            Analysis with suggestions
        """
        from openai import AsyncOpenAI

        # Build prompt
        email_summaries = []
        for e in emails[:10]:  # Limit to top 10 for cost
            email_summaries.append(
                {
                    "subject": e.subject,
                    "from": e.sender,
                    "category": e.category.value,
                    "priority": f"P{e.priority.value}",
                    "snippet": e.snippet[:200],
                    "deadline": e.deadline,
                }
            )

        prompt = f"""אתה עוזר חכם שמנתח מיילים ומציע פעולות.

## המיילים שהתקבלו
{json.dumps(email_summaries, ensure_ascii=False, indent=2)}

## המשימה שלך
1. זהה את 3 הדברים הכי חשובים לטפל בהם היום
2. הצע פעולות ספציפיות לכל מייל דחוף
3. זהה מיילים שאפשר להתעלם מהם
4. אם יש מייל בירוקרטי - הסבר מה נדרש בפשטות

## פורמט התשובה (JSON)
{{
  "top_3_priorities": [
    {{"email_subject": "...", "reason": "...", "suggested_action": "..."}}
  ],
  "can_ignore": ["subject1", "subject2"],
  "bureaucracy_explained": [
    {{"subject": "...", "what_needed": "...", "deadline": "..."}}
  ],
  "smart_tips": ["טיפ 1", "טיפ 2"]
}}

ענה רק ב-JSON, בלי markdown."""

        try:
            client = AsyncOpenAI(base_url=self.litellm_url, api_key="dummy")

            response = await client.chat.completions.create(
                model="claude-sonnet",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )

            content = response.choices[0].message.content
            # Clean markdown if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]

            return json.loads(content.strip())

        except Exception as e:
            logger.error(f"Smart analysis failed: {e}")
            return {
                "top_3_priorities": [],
                "can_ignore": [],
                "bureaucracy_explained": [],
                "smart_tips": [],
            }

    def _format_simple_message(self, summary: DailySummary, system_count: int) -> str:
        """Format summary as simple Telegram message (no LLM).

        Args:
            summary: Daily summary data
            system_count: Number of filtered system emails

        Returns:
            Formatted Telegram message (Markdown)
        """
        now = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")
        real_count = summary.total_emails

        lines = [
            f"🌅 *סיכום מיילים - {now}*",
            "",
            f"📊 *סטטיסטיקה:*",
            f"• {real_count} מיילים ({system_count} התראות מערכת הוסתרו)",
            f"• 🔴 דחוף: {summary.p1_count} | 🟠 חשוב: {summary.p2_count}",
            f"• 🟡 מידע: {summary.p3_count} | ⚪ פרסום: {summary.p4_count}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        # P1 - Urgent
        p1_emails = [e for e in summary.emails if e.priority == Priority.P1]
        if p1_emails:
            lines.append("")
            lines.append("🔴 *דחוף (P1):*")
            for email in p1_emails[:5]:
                subject = email.subject[:40] + ("..." if len(email.subject) > 40 else "")
                lines.append(f"  • [{email.category.value}] *{email.sender}*")
                lines.append(f"    {subject}")

        # P2 - Important
        p2_emails = [e for e in summary.emails if e.priority == Priority.P2]
        if p2_emails:
            lines.append("")
            lines.append("🟠 *חשוב (P2):*")
            for email in p2_emails[:5]:
                subject = email.subject[:40] + ("..." if len(email.subject) > 40 else "")
                lines.append(f"  • *{email.sender}*: {subject}")

        # P3 - Info (show details)
        p3_emails = [e for e in summary.emails if e.priority == Priority.P3]
        if p3_emails:
            lines.append("")
            lines.append("🟡 *מידע (P3):*")
            for email in p3_emails[:7]:
                sender_name = email.sender[:25]
                subject = email.subject[:35] + ("..." if len(email.subject) > 35 else "")
                lines.append(f"  • {sender_name}")
                lines.append(f"    _{subject}_")

        # P4 - Low priority (summary only)
        p4_emails = [e for e in summary.emails if e.priority == Priority.P4]
        if p4_emails:
            lines.append("")
            lines.append(f"⚪ *פרסום:* {len(p4_emails)} מיילים")

        # No emails case
        if real_count == 0:
            lines = [
                f"🌅 *סיכום מיילים - {now}*",
                "",
                "✅ *אין מיילים חדשים!*",
            ]
            if system_count > 0:
                lines.append(f"_({system_count} התראות מערכת הוסתרו)_")
            else:
                lines.append("_תיבה נקייה - יום טוב!_")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("_Smart Email Agent v2 (Fixed)_")

        return "\n".join(lines)

    def _format_telegram_message(
        self, summary: DailySummary, analysis: dict
    ) -> str:
        """Format summary as Telegram message.

        Args:
            summary: Daily summary data
            analysis: Smart analysis from LLM

        Returns:
            Formatted Telegram message (Markdown)
        """
        # Header
        lines = [
            f"🌅 *סיכום מיילים - {summary.date}*",
            "",
            f"📊 *סטטיסטיקה:*",
            f"• {summary.total_emails} מיילים חדשים",
            f"• 🔴 דחוף: {summary.p1_count} | 🟡 חשוב: {summary.p2_count}",
            f"• 🟢 מידע: {summary.p3_count} | ⚪ נמוך: {summary.p4_count}",
        ]

        # Calendar context
        if summary.calendar_events:
            lines.append("")
            lines.append(f"📅 *לו\"ז היום:*")
            for event in summary.calendar_events[:3]:
                start_time = event.start.split("T")[1][:5] if "T" in event.start else event.start
                lines.append(f"• {start_time} - {event.summary}")

        lines.append("")
        lines.append("━" * 20)

        # P1 emails (urgent)
        p1_emails = [e for e in summary.emails if e.priority == Priority.P1]
        if p1_emails:
            lines.append("")
            lines.append("🔴 *דחוף (P1):*")
            for i, email in enumerate(p1_emails, 1):
                lines.append("")
                lines.append(f"{i}️⃣ *{email.subject}*")
                lines.append(f"   📧 מאת: {email.sender_email}")
                lines.append(f"   🏷️ קטגוריה: {email.category.value}")
                if email.deadline:
                    lines.append(f"   ⏰ דדליין: {email.deadline}")
                if email.amount:
                    lines.append(f"   💰 סכום: {email.amount}")
                if email.links:
                    lines.append(f"   🔗 {len(email.links)} קישורים")

        # P2 emails (important)
        p2_emails = [e for e in summary.emails if e.priority == Priority.P2]
        if p2_emails:
            lines.append("")
            lines.append("━" * 20)
            lines.append("")
            lines.append("🟡 *דורש פעולה (P2):*")
            for i, email in enumerate(p2_emails[:5], 1):  # Limit to 5
                lines.append(f"{i}. {email.subject} ({email.category.value})")

        # Smart tips from analysis
        if analysis.get("smart_tips"):
            lines.append("")
            lines.append("━" * 20)
            lines.append("")
            lines.append("💡 *טיפים חכמים:*")
            for tip in analysis["smart_tips"][:3]:
                lines.append(f"• {tip}")

        # Bureaucracy explained
        if analysis.get("bureaucracy_explained"):
            lines.append("")
            lines.append("━" * 20)
            lines.append("")
            lines.append("📋 *בירוקרטיה בפשטות:*")
            for item in analysis["bureaucracy_explained"][:2]:
                lines.append(f"• *{item.get('subject', '')}*")
                lines.append(f"  נדרש: {item.get('what_needed', '')}")
                if item.get("deadline"):
                    lines.append(f"  עד: {item.get('deadline')}")

        # Footer
        lines.append("")
        lines.append("━" * 20)
        p34_count = summary.p3_count + summary.p4_count
        if p34_count > 0:
            lines.append(f"📬 *עוד {p34_count} מיילים בעדיפות נמוכה*")

        lines.append("")
        lines.append("_נשלח אוטומטית על ידי Email Agent_")

        return "\n".join(lines)

    def send_to_telegram(self, message: str) -> dict:
        """Send message to Telegram using direct API.

        Args:
            message: Message to send (Markdown format)

        Returns:
            Send result
        """
        try:
            token, chat_id = self._load_telegram_config()

            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=30,
            )

            if response.status_code == 200:
                logger.info("✅ Telegram message sent successfully")
                return {"success": True}
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            return {"success": False, "error": str(e)}

    def run(self, hours: int = 24, send_telegram: bool = True) -> dict:
        """Execute the email agent.

        Args:
            hours: Number of hours to look back for emails
            send_telegram: Whether to send summary to Telegram

        Returns:
            Execution result with summary
        """
        start_time = time.time()
        run_id = f"email_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting EmailAgent run {run_id}")

        try:
            # Fetch emails
            gmail_messages = self._fetch_emails(hours)
            calendar_events = self._fetch_calendar_events()

            logger.info(f"Fetched {len(gmail_messages)} emails, {len(calendar_events)} events")

            # Filter out system/automated emails (P5 equivalent)
            system_patterns = [
                "github.com", "noreply", "notifications@", "no-reply",
                "automated", "jenkins", "gitlab", "bitbucket"
            ]

            real_emails = []
            system_count = 0
            for msg in gmail_messages:
                sender_lower = f"{msg.sender} {msg.sender_email}".lower()
                if any(pattern in sender_lower for pattern in system_patterns):
                    system_count += 1
                else:
                    real_emails.append(msg)

            logger.info(f"Filtered: {len(real_emails)} real emails, {system_count} system notifications")

            # Process emails
            processed_emails = []
            for msg in real_emails:
                email_item = self._process_email(msg)
                processed_emails.append(email_item)

            # Sort by priority
            processed_emails.sort(key=lambda e: e.priority.value)

            # Count by priority
            p1_count = sum(1 for e in processed_emails if e.priority == Priority.P1)
            p2_count = sum(1 for e in processed_emails if e.priority == Priority.P2)
            p3_count = sum(1 for e in processed_emails if e.priority == Priority.P3)
            p4_count = sum(1 for e in processed_emails if e.priority == Priority.P4)

            # Build summary
            summary = DailySummary(
                date=datetime.now(UTC).strftime("%d/%m/%Y"),
                total_emails=len(processed_emails),
                p1_count=p1_count,
                p2_count=p2_count,
                p3_count=p3_count,
                p4_count=p4_count,
                emails=processed_emails,
                calendar_events=calendar_events,
                suggested_actions=[],
            )

            # Format message (simplified - no LLM analysis for now)
            message = self._format_simple_message(summary, system_count)

            # Send to Telegram
            telegram_result = {"success": False, "error": "Not sent"}
            if send_telegram:
                telegram_result = self.send_to_telegram(message)

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "run_id": run_id,
                "duration_ms": duration_ms,
                "emails_processed": len(processed_emails),
                "system_filtered": system_count,
                "p1_count": p1_count,
                "p2_count": p2_count,
                "p3_count": p3_count,
                "p4_count": p4_count,
                "telegram_sent": telegram_result.get("success", False),
                "message": message,
            }

        except Exception as e:
            logger.error(f"EmailAgent failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "run_id": run_id,
                "error": str(e),
            }


    async def run_with_research(
        self,
        hours: int = 24,
        send_telegram: bool = True,
        include_drafts: bool = True,
        include_history: bool = True,
    ) -> dict:
        """Execute the email agent with Phase 2 features.

        Enhanced run that includes:
        - Web research for bureaucracy emails
        - Draft reply generation
        - Sender history lookup

        Args:
            hours: Number of hours to look back for emails
            send_telegram: Whether to send summary to Telegram
            include_drafts: Whether to generate reply drafts
            include_history: Whether to lookup sender history

        Returns:
            Execution result with enhanced data
        """
        from src.agents.draft_generator import DraftGenerator
        from src.agents.email_history import EmailHistoryLookup
        from src.agents.web_researcher import WebResearcher

        start_time = time.time()
        run_id = f"email_v2_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting EmailAgent Phase 2 run {run_id}")

        try:
            # Phase 1: Basic email processing
            raw_emails = await self._fetch_emails(hours)
            calendar_events = await self._fetch_calendar_events()

            logger.info(f"Fetched {len(raw_emails)} emails, {len(calendar_events)} events")

            # Process emails
            processed_emails = []
            for raw in raw_emails:
                email_item = await self._process_email(raw)
                processed_emails.append(email_item)

            # Sort by priority
            processed_emails.sort(key=lambda e: e.priority.value)

            # Count by priority
            p1_count = sum(1 for e in processed_emails if e.priority == Priority.P1)
            p2_count = sum(1 for e in processed_emails if e.priority == Priority.P2)
            p3_count = sum(1 for e in processed_emails if e.priority == Priority.P3)
            p4_count = sum(1 for e in processed_emails if e.priority == Priority.P4)

            # Phase 2: Enhanced features
            research_results = {}
            draft_replies = []
            sender_histories = {}

            # Web research for P1 bureaucracy emails
            bureaucracy_emails = [
                e for e in processed_emails
                if e.priority == Priority.P1 and e.category == EmailCategory.BUREAUCRACY
            ]

            if bureaucracy_emails:
                logger.info(f"Researching {len(bureaucracy_emails)} bureaucracy emails")
                researcher = WebResearcher(litellm_url=self.litellm_url)

                for email in bureaucracy_emails[:3]:  # Limit to 3 for cost
                    result = await researcher.research_email(
                        subject=email.subject,
                        sender=email.sender,
                        snippet=email.snippet,
                    )
                    if result:
                        research_results[email.id] = result

            # Generate draft replies for P1/P2 emails
            if include_drafts and (p1_count > 0 or p2_count > 0):
                logger.info("Generating draft replies")
                generator = DraftGenerator(litellm_url=self.litellm_url)

                # Calendar context for scheduling
                calendar_context = [
                    f"{e.start} - {e.summary}" for e in calendar_events[:5]
                ]

                for email in processed_emails[:5]:  # Top 5 emails
                    if email.priority in [Priority.P1, Priority.P2]:
                        draft = await generator.generate_reply(
                            email_id=email.id,
                            email_subject=email.subject,
                            email_body=email.snippet,
                            sender=email.sender_email,
                            calendar_context=calendar_context,
                        )
                        draft_replies.append(draft)

            # Lookup sender history
            if include_history:
                logger.info("Looking up sender histories")
                history_lookup = EmailHistoryLookup(mcp_gateway_url=self.mcp_gateway_url)

                # Get unique senders from P1/P2 emails
                important_senders = list(set(
                    e.sender_email for e in processed_emails
                    if e.priority in [Priority.P1, Priority.P2]
                ))[:5]  # Limit to 5

                sender_histories = await history_lookup.get_batch_history(important_senders)

            # Generate smart analysis with enhanced context
            analysis = {}
            if p1_count > 0 or p2_count > 0:
                analysis = await self._generate_smart_analysis(processed_emails)

            # Build summary
            summary = DailySummary(
                date=datetime.now(UTC).strftime("%d/%m/%Y"),
                total_emails=len(processed_emails),
                p1_count=p1_count,
                p2_count=p2_count,
                p3_count=p3_count,
                p4_count=p4_count,
                emails=processed_emails,
                calendar_events=calendar_events,
                suggested_actions=analysis.get("smart_tips", []),
            )

            # Format main message
            message = self._format_telegram_message(summary, analysis)

            # Add Phase 2 content to message
            phase2_lines = []

            # Add research findings
            if research_results:
                phase2_lines.append("\n" + "━" * 20)
                phase2_lines.append("\n🔍 *מחקר בירוקרטי:*\n")
                for email_id, research in list(research_results.items())[:2]:
                    phase2_lines.append(f"• *{research.source_name}*")
                    phase2_lines.append(f"  {research.relevant_info[:100]}...")
                    if research.forms_found:
                        phase2_lines.append(f"  📝 טפסים: {', '.join(research.forms_found[:2])}")

            # Add draft indicators
            if draft_replies:
                phase2_lines.append("\n" + "━" * 20)
                phase2_lines.append(f"\n✉️ *{len(draft_replies)} טיוטות תשובה מוכנות*")
                phase2_lines.append("_שלח /drafts לצפייה בטיוטות_")

            if phase2_lines:
                message = message.replace(
                    "_נשלח אוטומטית על ידי Email Agent_",
                    "\n".join(phase2_lines) + "\n\n_נשלח אוטומטית על ידי Email Agent v2_"
                )

            # Send to Telegram
            telegram_result = {"success": False, "error": "Not sent"}
            if send_telegram:
                telegram_result = await self.send_to_telegram(message)

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "run_id": run_id,
                "version": "2.0",
                "duration_ms": duration_ms,
                "emails_processed": len(processed_emails),
                "p1_count": p1_count,
                "p2_count": p2_count,
                "calendar_events": len(calendar_events),
                "research_count": len(research_results),
                "drafts_generated": len(draft_replies),
                "histories_loaded": len(sender_histories),
                "telegram_sent": telegram_result.get("success", False),
                "message": message,
                "drafts": [
                    {
                        "email_id": d.email_id,
                        "subject": d.subject,
                        "body": d.body_hebrew[:200] + "...",
                        "confidence": d.confidence,
                    }
                    for d in draft_replies
                ],
            }

        except Exception as e:
            logger.error(f"EmailAgent Phase 2 failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "run_id": run_id,
                "version": "2.0",
                "error": str(e),
            }


def main() -> None:
    """Run EmailAgent for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("📧 Smart Email Agent - Direct Test")
    print("=" * 50)

    agent = EmailAgent()

    # Test run (no Telegram send for dry run)
    print("\n=== Testing Email Fetch ===")
    result = agent.run(hours=24, send_telegram=False)

    print(f"\n✅ Success: {result.get('success')}")
    print(f"📬 Emails processed: {result.get('emails_processed', 0)}")
    print(f"🔇 System filtered: {result.get('system_filtered', 0)}")
    print(f"🔴 P1: {result.get('p1_count', 0)}")
    print(f"🟠 P2: {result.get('p2_count', 0)}")
    print(f"🟡 P3: {result.get('p3_count', 0)}")
    print(f"⚪ P4: {result.get('p4_count', 0)}")

    if result.get("message"):
        print("\n" + "-" * 40)
        print("📝 Message preview:")
        print("-" * 40)
        print(result["message"])
        print("-" * 40)

    if result.get("error"):
        print(f"\n❌ Error: {result['error']}")


if __name__ == "__main__":
    main()
