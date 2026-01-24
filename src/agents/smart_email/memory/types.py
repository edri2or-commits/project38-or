"""Memory types for Smart Email Agent.

Defines the data structures for long-term memory:
- SenderProfile: Complete understanding of a sender
- InteractionRecord: Single interaction history
- ThreadSummary: Summary of email thread
- ActionOutcome: What happened when action was taken
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryType(Enum):
    """Types of memory (based on cognitive science)."""
    SEMANTIC = "semantic"      # Facts: "דני הוא רואה החשבון"
    EPISODIC = "episodic"      # Events: "בפעם האחרונה ביקש אישור"
    PROCEDURAL = "procedural"  # Actions: "למיילים מהבנק - לבדוק דדליין"


class RelationshipType(Enum):
    """Type of relationship with sender."""
    NEW = "new"                    # First contact
    OCCASIONAL = "occasional"      # 2-5 interactions
    RECURRING = "recurring"        # 6-15 interactions
    FREQUENT = "frequent"          # 15+ interactions
    VIP = "vip"                    # Marked as important

    # Specific roles
    ACCOUNTANT = "accountant"      # רואה חשבון
    LAWYER = "lawyer"              # עורך דין
    SUPPLIER = "supplier"          # ספק
    CLIENT = "client"              # לקוח
    GOVERNMENT = "government"      # ממשלה/רשויות
    BANK = "bank"                  # בנק
    FAMILY = "family"              # משפחה
    FRIEND = "friend"              # חבר


@dataclass
class ActionOutcome:
    """Record of an action taken and its outcome.

    Episodic memory: What happened when we did X?
    """
    action_type: str              # reply, forward, archive, approve
    email_id: str
    timestamp: datetime
    success: bool

    # What was done
    action_details: str = ""      # "שלחתי אישור"

    # What happened after
    outcome: str = ""             # "דני אישר קבלה"
    response_time_hours: float | None = None

    # Learning
    was_correct_action: bool | None = None  # User feedback
    notes: str = ""


@dataclass
class ThreadSummary:
    """Summary of an email thread for episodic memory.

    Instead of storing full threads, we summarize them.
    """
    thread_id: str
    subject: str
    participants: list[str] = field(default_factory=list)

    # Timeline
    started: datetime | None = None
    last_activity: datetime | None = None
    message_count: int = 0

    # Content summary
    summary: str = ""             # LLM-generated summary
    key_points: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    pending_actions: list[str] = field(default_factory=list)

    # Outcome
    status: str = "active"        # active, resolved, waiting, archived
    resolution: str = ""          # How it ended


@dataclass
class InteractionRecord:
    """Single interaction with a sender.

    Episodic memory: What happened in this specific interaction?
    """
    id: str
    sender_email: str
    timestamp: datetime

    # Email details
    email_id: str
    thread_id: str
    subject: str
    direction: str = "incoming"   # incoming, outgoing

    # Classification at time
    priority: str = "P3"
    category: str = "מידע"

    # Action taken
    action: ActionOutcome | None = None

    # Context
    was_urgent: bool = False
    had_deadline: bool = False
    deadline_date: datetime | None = None
    had_attachments: bool = False

    # Learning
    user_response_time_hours: float | None = None
    importance_score: float = 0.5  # 0-1, learned over time


@dataclass
class SenderProfile:
    """Complete profile of an email sender.

    Semantic memory: What do we know about this sender?

    This is the core of Sender Intelligence - understanding
    who the sender is, what they typically want, and how
    to handle their emails.
    """
    # Identity
    email: str                    # Primary key
    name: str = ""
    display_name: str = ""        # How user refers to them

    # Relationship
    relationship_type: RelationshipType = RelationshipType.NEW
    role: str = ""                # "רואה החשבון שלי"
    organization: str = ""        # "משרד רו"ח כהן"

    # Contact history
    first_contact: datetime | None = None
    last_contact: datetime | None = None
    total_interactions: int = 0

    # Patterns (learned over time)
    typical_topics: list[str] = field(default_factory=list)
    typical_priority: str = "P3"  # Most common priority
    typical_category: str = "מידע"
    typical_urgency: float = 0.3  # 0-1 scale

    # Timing patterns
    avg_response_expected_hours: float = 48.0  # How fast they expect reply
    user_avg_response_hours: float = 24.0      # How fast user usually replies
    best_contact_time: str = ""                # "בוקר", "ערב"

    # Communication style
    preferred_tone: str = "professional"  # formal, professional, friendly
    language: str = "hebrew"              # hebrew, english, mixed
    uses_formal_greeting: bool = True

    # Special handling
    is_vip: bool = False
    requires_immediate_attention: bool = False
    auto_archive: bool = False            # Always low priority

    # Notes (user-added or LLM-learned)
    notes: str = ""               # "תמיד שואל על חשבוניות בסוף חודש"

    # Recent activity
    recent_threads: list[str] = field(default_factory=list)  # Thread IDs
    pending_from_them: int = 0    # Emails waiting for user
    pending_to_them: int = 0      # Emails waiting for them

    # Summarization
    relationship_summary: str = ""  # LLM-generated: "דני הוא רו"ח שלי מ-2020..."
    last_summary_update: datetime | None = None

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def get_context_for_llm(self) -> str:
        """Generate context string for LLM prompts.

        Returns:
            Context about this sender for LLM to use
        """
        parts = []

        # Identity
        if self.role:
            parts.append(f"{self.name} הוא {self.role}")
        elif self.organization:
            parts.append(f"{self.name} מ-{self.organization}")
        else:
            parts.append(f"שולח: {self.name or self.email}")

        # Relationship
        rel_map = {
            RelationshipType.NEW: "איש קשר חדש",
            RelationshipType.OCCASIONAL: "איש קשר מזדמן",
            RelationshipType.RECURRING: "איש קשר חוזר",
            RelationshipType.FREQUENT: "איש קשר תכוף",
            RelationshipType.VIP: "איש קשר חשוב",
        }
        if self.relationship_type in rel_map:
            parts.append(f"({rel_map[self.relationship_type]}, {self.total_interactions} אינטראקציות)")

        # Patterns
        if self.typical_topics:
            topics = ", ".join(self.typical_topics[:3])
            parts.append(f"נושאים טיפוסיים: {topics}")

        # Special notes
        if self.notes:
            parts.append(f"הערות: {self.notes}")

        # Pending
        if self.pending_from_them > 0:
            parts.append(f"ממתינים לך: {self.pending_from_them} מיילים")

        return ". ".join(parts)

    def should_prioritize(self) -> bool:
        """Check if emails from this sender should be prioritized."""
        return (
            self.is_vip or
            self.requires_immediate_attention or
            self.relationship_type in [RelationshipType.VIP, RelationshipType.GOVERNMENT, RelationshipType.BANK] or
            self.typical_urgency > 0.7
        )

    def get_relationship_badge(self) -> str:
        """Get emoji badge for relationship type."""
        badges = {
            RelationshipType.NEW: "🆕",
            RelationshipType.OCCASIONAL: "👤",
            RelationshipType.RECURRING: "🔄",
            RelationshipType.FREQUENT: "⭐",
            RelationshipType.VIP: "👑",
            RelationshipType.GOVERNMENT: "🏛️",
            RelationshipType.BANK: "🏦",
            RelationshipType.ACCOUNTANT: "📊",
            RelationshipType.LAWYER: "⚖️",
            RelationshipType.FAMILY: "👨‍👩‍👧",
            RelationshipType.FRIEND: "🤝",
        }
        return badges.get(self.relationship_type, "👤")


@dataclass
class ConversationContext:
    """Context for Telegram conversation with user.

    Tracks the current conversation state for interactive
    follow-up questions and actions.
    """
    # Session
    user_id: str
    chat_id: str
    started_at: datetime
    last_message_at: datetime

    # Current focus
    current_email_id: str | None = None
    current_thread_id: str | None = None
    current_sender: str | None = None

    # Conversation state
    awaiting_response: bool = False
    awaiting_action: str | None = None  # "confirm_send", "select_email", etc.
    pending_action_data: dict[str, Any] = field(default_factory=dict)

    # Recent messages (short-term memory)
    recent_messages: list[dict] = field(default_factory=list)  # Last 30 messages

    # What user asked about
    discussed_emails: list[str] = field(default_factory=list)
    discussed_senders: list[str] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        """Add message to conversation history."""
        self.recent_messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep only last 30 messages
        if len(self.recent_messages) > 30:
            self.recent_messages = self.recent_messages[-30:]
        self.last_message_at = datetime.now()

    def get_messages_for_llm(self) -> list[dict]:
        """Get messages in format suitable for LLM."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.recent_messages
        ]
