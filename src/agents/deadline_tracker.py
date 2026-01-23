"""Deadline Tracker - Tracks deadlines from emails and sends reminders.

Extracts deadlines from emails, stores them, and sends proactive
reminders via Telegram before deadlines expire.

ADR-014 Phase 3: Deep Deadline Tracking with Reminders
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class DeadlineUrgency(Enum):
    """Urgency level of a deadline."""

    OVERDUE = "overdue"  # Past deadline
    TODAY = "today"  # Due today
    TOMORROW = "tomorrow"  # Due tomorrow
    THIS_WEEK = "this_week"  # Due within 7 days
    NEXT_WEEK = "next_week"  # Due within 14 days
    LATER = "later"  # More than 2 weeks away


class DeadlineStatus(Enum):
    """Status of a deadline."""

    PENDING = "pending"  # Not yet addressed
    IN_PROGRESS = "in_progress"  # Working on it
    COMPLETED = "completed"  # Done
    DISMISSED = "dismissed"  # User dismissed


@dataclass
class Deadline:
    """A tracked deadline."""

    id: str
    source_email_id: str
    title: str
    description: str
    organization: str
    due_date: datetime
    status: DeadlineStatus = DeadlineStatus.PENDING
    urgency: DeadlineUrgency = DeadlineUrgency.LATER
    action_required: str | None = None
    form_url: str | None = None
    documents_needed: list[str] = field(default_factory=list)
    reminders_sent: list[datetime] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def days_until_due(self) -> int:
        """Calculate days until deadline."""
        now = datetime.now(UTC)
        delta = self.due_date - now
        return delta.days

    def update_urgency(self) -> None:
        """Update urgency based on current date."""
        days = self.days_until_due()

        if days < 0:
            self.urgency = DeadlineUrgency.OVERDUE
        elif days == 0:
            self.urgency = DeadlineUrgency.TODAY
        elif days == 1:
            self.urgency = DeadlineUrgency.TOMORROW
        elif days <= 7:
            self.urgency = DeadlineUrgency.THIS_WEEK
        elif days <= 14:
            self.urgency = DeadlineUrgency.NEXT_WEEK
        else:
            self.urgency = DeadlineUrgency.LATER


@dataclass
class ReminderConfig:
    """Configuration for deadline reminders."""

    # Days before deadline to send reminders
    reminder_days: list[int] = field(default_factory=lambda: [7, 3, 1, 0])

    # Time of day to send reminders (UTC)
    reminder_hour: int = 7  # 07:00 UTC = 09:00 Israel

    # Maximum reminders per deadline
    max_reminders: int = 5

    # Urgency emoji mapping
    urgency_emoji: dict = field(
        default_factory=lambda: {
            DeadlineUrgency.OVERDUE: "🔴",
            DeadlineUrgency.TODAY: "🔴",
            DeadlineUrgency.TOMORROW: "🟠",
            DeadlineUrgency.THIS_WEEK: "🟡",
            DeadlineUrgency.NEXT_WEEK: "🟢",
            DeadlineUrgency.LATER: "⚪",
        }
    )


class DeadlineTracker:
    """Tracks deadlines from emails and manages reminders.

    Extracts deadlines, stores them persistently, and sends
    proactive reminders via Telegram.

    Example:
        tracker = DeadlineTracker()

        # Add deadline from email
        deadline = await tracker.extract_deadline(
            email_id="123",
            email_subject="דרישה להשלמת מסמכים",
            email_body="עד 30/01/2026",
            sender="btl.gov.il"
        )

        # Check for reminders to send
        reminders = await tracker.get_due_reminders()
        for reminder in reminders:
            await tracker.send_reminder(reminder)
    """

    def __init__(
        self,
        storage_path: str | None = None,
        telegram_bot_url: str = "https://telegram-bot-production-053d.up.railway.app",
        config: ReminderConfig | None = None,
    ):
        """Initialize DeadlineTracker.

        Args:
            storage_path: Path to JSON storage file
            telegram_bot_url: URL of Telegram bot for reminders
            config: Reminder configuration
        """
        self.storage_path = Path(storage_path or "/tmp/deadlines.json")
        self.telegram_bot_url = telegram_bot_url
        self.config = config or ReminderConfig()
        self._deadlines: dict[str, Deadline] = {}
        self._load_deadlines()

    def _load_deadlines(self) -> None:
        """Load deadlines from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for item in data.get("deadlines", []):
                    deadline = Deadline(
                        id=item["id"],
                        source_email_id=item["source_email_id"],
                        title=item["title"],
                        description=item["description"],
                        organization=item["organization"],
                        due_date=datetime.fromisoformat(item["due_date"]),
                        status=DeadlineStatus(item.get("status", "pending")),
                        action_required=item.get("action_required"),
                        form_url=item.get("form_url"),
                        documents_needed=item.get("documents_needed", []),
                        reminders_sent=[
                            datetime.fromisoformat(r)
                            for r in item.get("reminders_sent", [])
                        ],
                        created_at=datetime.fromisoformat(
                            item.get("created_at", datetime.now(UTC).isoformat())
                        ),
                    )
                    deadline.update_urgency()
                    self._deadlines[deadline.id] = deadline
                logger.info(f"Loaded {len(self._deadlines)} deadlines")
            except Exception as e:
                logger.error(f"Failed to load deadlines: {e}")

    def _save_deadlines(self) -> None:
        """Save deadlines to storage."""
        try:
            data = {
                "deadlines": [
                    {
                        "id": d.id,
                        "source_email_id": d.source_email_id,
                        "title": d.title,
                        "description": d.description,
                        "organization": d.organization,
                        "due_date": d.due_date.isoformat(),
                        "status": d.status.value,
                        "action_required": d.action_required,
                        "form_url": d.form_url,
                        "documents_needed": d.documents_needed,
                        "reminders_sent": [r.isoformat() for r in d.reminders_sent],
                        "created_at": d.created_at.isoformat(),
                    }
                    for d in self._deadlines.values()
                ],
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            logger.info(f"Saved {len(self._deadlines)} deadlines")
        except Exception as e:
            logger.error(f"Failed to save deadlines: {e}")

    def _parse_date(self, text: str) -> datetime | None:
        """Parse date from various formats.

        Args:
            text: Text containing date

        Returns:
            Parsed datetime or None
        """
        # Israeli date formats
        patterns = [
            # DD/MM/YYYY or DD.MM.YYYY
            (r"(\d{1,2})[./](\d{1,2})[./](\d{4})", "%d/%m/%Y"),
            # DD/MM/YY
            (r"(\d{1,2})[./](\d{1,2})[./](\d{2})", "%d/%m/%y"),
            # Hebrew months
            (
                r"(\d{1,2})\s+ב?(ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|"
                r"אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)",
                None,
            ),
        ]

        for pattern, date_format in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if date_format:
                        date_str = match.group(0).replace(".", "/")
                        return datetime.strptime(date_str, date_format).replace(tzinfo=UTC)
                    else:
                        # Handle Hebrew month names
                        day = int(match.group(1))
                        month_name = match.group(2)
                        month_map = {
                            "ינואר": 1, "פברואר": 2, "מרץ": 3, "אפריל": 4,
                            "מאי": 5, "יוני": 6, "יולי": 7, "אוגוסט": 8,
                            "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
                        }
                        month = month_map.get(month_name, 1)
                        year = datetime.now().year
                        return datetime(year, month, day, tzinfo=UTC)
                except ValueError:
                    continue

        # Relative dates
        relative_patterns = [
            (r"תוך (\d+) ימים?", lambda d: datetime.now(UTC) + timedelta(days=int(d))),
            (r"תוך (\d+) שבועות?", lambda d: datetime.now(UTC) + timedelta(weeks=int(d))),
            (r"within (\d+) days?", lambda d: datetime.now(UTC) + timedelta(days=int(d))),
        ]

        for pattern, calc_func in relative_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return calc_func(match.group(1))

        return None

    def _generate_id(self, email_id: str, due_date: datetime) -> str:
        """Generate unique deadline ID."""
        date_str = due_date.strftime("%Y%m%d")
        return f"dl_{email_id[:8]}_{date_str}"

    def _identify_organization(self, sender: str, subject: str) -> str:
        """Identify organization from sender/subject."""
        combined = f"{sender} {subject}".lower()

        patterns = {
            r"btl\.gov\.il|ביטוח לאומי": "ביטוח לאומי",
            r"taxes\.gov\.il|מס הכנסה": "מס הכנסה",
            r"משרד הפנים|piba": "משרד הפנים",
            r"עירי|municipality": "עירייה",
            r"bank|בנק": "בנק",
        }

        for pattern, org in patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                return org

        return "אחר"

    async def extract_deadline(
        self,
        email_id: str,
        email_subject: str,
        email_body: str,
        sender: str,
    ) -> Deadline | None:
        """Extract deadline from email.

        Args:
            email_id: Email ID
            email_subject: Email subject
            email_body: Email body
            sender: Email sender

        Returns:
            Extracted Deadline or None if no deadline found
        """
        combined_text = f"{email_subject} {email_body}"

        # Try to parse date
        due_date = self._parse_date(combined_text)
        if not due_date:
            logger.info(f"No deadline found in email {email_id}")
            return None

        # Check if we already have this deadline
        deadline_id = self._generate_id(email_id, due_date)
        if deadline_id in self._deadlines:
            logger.info(f"Deadline {deadline_id} already exists")
            return self._deadlines[deadline_id]

        # Extract additional info
        organization = self._identify_organization(sender, email_subject)

        # Extract documents
        doc_patterns = [
            r"צילום תעודת זהות",
            r"אישור תושב",
            r"תלוש(?:י)? שכר",
            r"מסמך(?:ים)?",
        ]
        documents = []
        for pattern in doc_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match:
                    documents.append(match.group(0))

        # Create deadline
        deadline = Deadline(
            id=deadline_id,
            source_email_id=email_id,
            title=email_subject[:100],
            description=email_body[:300],
            organization=organization,
            due_date=due_date,
            documents_needed=documents,
        )
        deadline.update_urgency()

        # Store
        self._deadlines[deadline_id] = deadline
        self._save_deadlines()

        logger.info(f"Created deadline {deadline_id}: {deadline.title} due {due_date}")
        return deadline

    def get_all_deadlines(self, include_completed: bool = False) -> list[Deadline]:
        """Get all tracked deadlines.

        Args:
            include_completed: Whether to include completed/dismissed deadlines

        Returns:
            List of deadlines sorted by due date
        """
        deadlines = list(self._deadlines.values())

        if not include_completed:
            deadlines = [
                d for d in deadlines
                if d.status not in [DeadlineStatus.COMPLETED, DeadlineStatus.DISMISSED]
            ]

        # Update urgency and sort
        for d in deadlines:
            d.update_urgency()

        deadlines.sort(key=lambda d: d.due_date)
        return deadlines

    def get_urgent_deadlines(self) -> list[Deadline]:
        """Get deadlines that need attention (today, tomorrow, overdue).

        Returns:
            List of urgent deadlines
        """
        deadlines = self.get_all_deadlines()
        return [
            d for d in deadlines
            if d.urgency in [
                DeadlineUrgency.OVERDUE,
                DeadlineUrgency.TODAY,
                DeadlineUrgency.TOMORROW,
            ]
        ]

    def get_due_reminders(self) -> list[Deadline]:
        """Get deadlines that need reminders sent.

        Returns:
            List of deadlines needing reminders
        """
        now = datetime.now(UTC)
        reminders_needed = []

        for deadline in self.get_all_deadlines():
            days_until = deadline.days_until_due()

            # Check if we should send a reminder
            for reminder_day in self.config.reminder_days:
                if days_until == reminder_day:
                    # Check if we already sent this reminder
                    already_sent = any(
                        r.date() == now.date() for r in deadline.reminders_sent
                    )
                    max_not_reached = len(deadline.reminders_sent) < self.config.max_reminders
                    if not already_sent and max_not_reached:
                        reminders_needed.append(deadline)
                        break

        return reminders_needed

    def mark_reminder_sent(self, deadline_id: str) -> None:
        """Mark that a reminder was sent for a deadline.

        Args:
            deadline_id: Deadline ID
        """
        if deadline_id in self._deadlines:
            self._deadlines[deadline_id].reminders_sent.append(datetime.now(UTC))
            self._save_deadlines()

    def update_status(self, deadline_id: str, status: DeadlineStatus) -> None:
        """Update deadline status.

        Args:
            deadline_id: Deadline ID
            status: New status
        """
        if deadline_id in self._deadlines:
            self._deadlines[deadline_id].status = status
            if status == DeadlineStatus.COMPLETED:
                self._deadlines[deadline_id].completed_at = datetime.now(UTC)
            self._save_deadlines()

    async def send_reminder(
        self,
        deadline: Deadline,
        chat_id: int | None = None,
    ) -> dict:
        """Send reminder to Telegram.

        Args:
            deadline: Deadline to remind about
            chat_id: Telegram chat ID

        Returns:
            Send result
        """
        import os

        chat_id = chat_id or int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

        if not chat_id:
            return {"success": False, "error": "TELEGRAM_CHAT_ID not configured"}

        # Format message
        message = self.format_reminder(deadline)

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
                    self.mark_reminder_sent(deadline.id)
                    return {"success": True}
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")
            return {"success": False, "error": str(e)}

    def format_reminder(self, deadline: Deadline) -> str:
        """Format deadline as reminder message.

        Args:
            deadline: Deadline to format

        Returns:
            Formatted Telegram message
        """
        emoji = self.config.urgency_emoji.get(deadline.urgency, "⚪")
        days = deadline.days_until_due()

        # Urgency text
        if deadline.urgency == DeadlineUrgency.OVERDUE:
            urgency_text = f"*עבר הדדליין לפני {abs(days)} ימים!*"
        elif deadline.urgency == DeadlineUrgency.TODAY:
            urgency_text = "*היום הדדליין!*"
        elif deadline.urgency == DeadlineUrgency.TOMORROW:
            urgency_text = "*מחר הדדליין!*"
        else:
            urgency_text = f"*עוד {days} ימים לדדליין*"

        lines = [
            f"{emoji} *תזכורת: {deadline.title}*",
            "",
            urgency_text,
            f"📅 תאריך יעד: {deadline.due_date.strftime('%d/%m/%Y')}",
            f"🏢 {deadline.organization}",
            "",
        ]

        if deadline.action_required:
            lines.append(f"📋 נדרש: {deadline.action_required}")
            lines.append("")

        if deadline.documents_needed:
            lines.append("📎 *מסמכים:*")
            for doc in deadline.documents_needed[:3]:
                lines.append(f"  • {doc}")
            lines.append("")

        if deadline.form_url:
            lines.append(f"🔗 [פתח טופס]({deadline.form_url})")
            lines.append("")

        lines.append("_שלח /done להשלמה | /snooze לדחייה_")

        return "\n".join(lines)

    def format_summary(self) -> str:
        """Format all deadlines as summary.

        Returns:
            Formatted Telegram message
        """
        deadlines = self.get_all_deadlines()

        if not deadlines:
            return "✅ *אין דדליינים פתוחים!*\n\n_הכל בסדר._"

        # Group by urgency
        urgent_levels = [
            DeadlineUrgency.OVERDUE, DeadlineUrgency.TODAY, DeadlineUrgency.TOMORROW
        ]
        urgent = [d for d in deadlines if d.urgency in urgent_levels]
        this_week = [d for d in deadlines if d.urgency == DeadlineUrgency.THIS_WEEK]
        later_levels = [DeadlineUrgency.NEXT_WEEK, DeadlineUrgency.LATER]
        later = [d for d in deadlines if d.urgency in later_levels]

        lines = [
            f"📅 *דדליינים ({len(deadlines)} פתוחים)*",
            "",
        ]

        if urgent:
            lines.append("🔴 *דחוף:*")
            for d in urgent:
                days = d.days_until_due()
                if days < 0:
                    time_text = f"איחור {abs(days)} ימים!"
                elif days == 0:
                    time_text = "היום!"
                else:
                    time_text = "מחר!"
                lines.append(f"  • {d.title[:40]} ({time_text})")
            lines.append("")

        if this_week:
            lines.append("🟡 *השבוע:*")
            for d in this_week:
                lines.append(f"  • {d.title[:40]} ({d.due_date.strftime('%d/%m')})")
            lines.append("")

        if later:
            lines.append(f"🟢 *בהמשך:* {len(later)} פריטים")

        return "\n".join(lines)


async def main() -> None:
    """Test DeadlineTracker."""
    logging.basicConfig(level=logging.INFO)

    tracker = DeadlineTracker(storage_path="/tmp/test_deadlines.json")

    # Test extraction
    deadline = await tracker.extract_deadline(
        email_id="test123",
        email_subject="דרישה להשלמת מסמכים - ביטוח לאומי",
        email_body="עליך להגיש את המסמכים עד 30/01/2026. נדרש: צילום תעודת זהות, אישור תושב.",
        sender="noreply@btl.gov.il",
    )

    if deadline:
        print("\n=== Extracted Deadline ===")
        print(f"ID: {deadline.id}")
        print(f"Title: {deadline.title}")
        print(f"Due: {deadline.due_date}")
        print(f"Urgency: {deadline.urgency.value}")
        print(f"Days until: {deadline.days_until_due()}")

        print("\n=== Reminder Format ===")
        print(tracker.format_reminder(deadline))

    print("\n=== All Deadlines Summary ===")
    print(tracker.format_summary())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
