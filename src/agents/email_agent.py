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
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import httpx

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
        mcp_gateway_url: str = "https://or-infra.com/mcp",
        litellm_url: str = "https://litellm-gateway-production-0339.up.railway.app",
        telegram_bot_url: str = "https://telegram-bot-production-053d.up.railway.app",
    ):
        """Initialize EmailAgent.

        Args:
            mcp_gateway_url: URL of MCP Gateway (for Gmail/Calendar)
            litellm_url: URL of LiteLLM Gateway (for AI analysis)
            telegram_bot_url: URL of Telegram Bot service
        """
        self.mcp_gateway_url = mcp_gateway_url
        self.litellm_url = litellm_url
        self.telegram_bot_url = telegram_bot_url
        self._mcp_token: str | None = None

    async def _get_mcp_token(self) -> str:
        """Get MCP Gateway token from environment or Secret Manager."""
        import os

        if self._mcp_token:
            return self._mcp_token

        # Try environment first
        token = os.environ.get("MCP_GATEWAY_TOKEN")
        if token:
            self._mcp_token = token
            return token

        # Try GCP Secret Manager
        try:
            from src.secrets_manager import SecretManager

            manager = SecretManager()
            token = manager.get_secret("MCP-GATEWAY-TOKEN")
            if token:
                self._mcp_token = token
                return token
        except Exception as e:
            logger.warning(f"Could not get MCP token from Secret Manager: {e}")

        raise ValueError("MCP_GATEWAY_TOKEN not found in env or Secret Manager")

    async def _call_mcp_tool(self, tool_name: str, params: dict) -> dict:
        """Call an MCP Gateway tool.

        Args:
            tool_name: Name of the tool (e.g., "gmail_search")
            params: Tool parameters

        Returns:
            Tool response
        """
        token = await self._get_mcp_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.mcp_gateway_url}/tools/{tool_name}",
                headers={"Authorization": f"Bearer {token}"},
                json=params,
            )

            if response.status_code != 200:
                logger.error(f"MCP tool {tool_name} failed: {response.text}")
                return {"success": False, "error": response.text}

            return response.json()

    async def _fetch_emails(self, hours: int = 24) -> list[dict]:
        """Fetch unread emails from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of raw email data
        """
        # Search for unread emails from last N hours
        query = f"is:unread newer_than:{hours}h"
        result = await self._call_mcp_tool("gmail_search", {"query": query, "max_results": 50})

        if not result.get("success"):
            logger.error(f"Failed to fetch emails: {result.get('error')}")
            return []

        return result.get("messages", [])

    async def _fetch_email_body(self, message_id: str) -> str:
        """Fetch full email body.

        Args:
            message_id: Gmail message ID

        Returns:
            Email body text
        """
        # For now, use snippet - full body requires additional API call
        # TODO: Implement full body fetch via MCP
        return ""

    async def _fetch_calendar_events(self) -> list[CalendarEvent]:
        """Fetch today's calendar events.

        Returns:
            List of today's events
        """
        result = await self._call_mcp_tool(
            "calendar_list_events", {"max_results": 10, "calendar_id": "primary"}
        )

        if not result.get("success"):
            logger.warning(f"Failed to fetch calendar: {result.get('error')}")
            return []

        events = []
        for item in result.get("events", []):
            events.append(
                CalendarEvent(
                    id=item.get("id", ""),
                    summary=item.get("summary", ""),
                    start=item.get("start", ""),
                    end=item.get("end", ""),
                    location=item.get("location", ""),
                )
            )

        return events

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

    def _classify_email(self, email: dict) -> tuple[EmailCategory, Priority]:
        """Classify email by category and priority.

        Args:
            email: Raw email data

        Returns:
            Tuple of (category, priority)
        """
        subject = email.get("subject", "").lower()
        sender = email.get("from", "").lower()
        snippet = email.get("snippet", "").lower()
        combined = f"{subject} {sender} {snippet}"

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

    async def _process_email(self, raw_email: dict) -> EmailItem:
        """Process a raw email into an EmailItem.

        Args:
            raw_email: Raw email data from Gmail

        Returns:
            Processed EmailItem
        """
        category, priority = self._classify_email(raw_email)

        subject = raw_email.get("subject", "")
        snippet = raw_email.get("snippet", "")
        combined_text = f"{subject} {snippet}"

        return EmailItem(
            id=raw_email.get("id", ""),
            thread_id=raw_email.get("thread_id", ""),
            subject=subject,
            sender=raw_email.get("from", ""),
            sender_email=self._extract_sender_email(raw_email.get("from", "")),
            date=raw_email.get("date", ""),
            snippet=snippet,
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

    async def send_to_telegram(self, message: str, chat_id: int | None = None) -> dict:
        """Send message to Telegram.

        Args:
            message: Message to send (Markdown format)
            chat_id: Telegram chat ID (uses env var if not provided)

        Returns:
            Send result
        """
        import os

        chat_id = chat_id or int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

        if not chat_id:
            return {"success": False, "error": "TELEGRAM_CHAT_ID not configured"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.telegram_bot_url}/send",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                )

                if response.status_code == 200:
                    return {"success": True}
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            return {"success": False, "error": str(e)}

    async def run(self, hours: int = 24, send_telegram: bool = True) -> dict:
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
            # Fetch emails and calendar in parallel
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

            # Generate smart analysis (only if we have P1/P2 emails)
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

            # Format message
            message = self._format_telegram_message(summary, analysis)

            # Send to Telegram
            telegram_result = {"success": False, "error": "Not sent"}
            if send_telegram:
                telegram_result = await self.send_to_telegram(message)

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "run_id": run_id,
                "duration_ms": duration_ms,
                "emails_processed": len(processed_emails),
                "p1_count": p1_count,
                "p2_count": p2_count,
                "calendar_events": len(calendar_events),
                "telegram_sent": telegram_result.get("success", False),
                "message": message,  # For debugging
            }

        except Exception as e:
            logger.error(f"EmailAgent failed: {e}")
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


async def main() -> None:
    """Run EmailAgent for testing."""
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Check for required env vars
    if not os.environ.get("MCP_GATEWAY_TOKEN"):
        print("Warning: MCP_GATEWAY_TOKEN not set, will try Secret Manager")

    agent = EmailAgent()

    # Test Phase 1
    print("=== Testing Phase 1 ===")
    result = await agent.run(hours=24, send_telegram=False)
    print(json.dumps({k: v for k, v in result.items() if k != "message"}, indent=2))

    # Test Phase 2
    print("\n=== Testing Phase 2 ===")
    result_v2 = await agent.run_with_research(hours=24, send_telegram=False)
    print(json.dumps({k: v for k, v in result_v2.items() if k not in ["message", "drafts"]}, indent=2))

    if result_v2.get("drafts"):
        print("\n=== Draft Replies ===")
        for draft in result_v2["drafts"]:
            print(f"  • {draft['subject']} (confidence: {draft['confidence']})")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
