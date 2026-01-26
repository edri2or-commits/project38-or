"""State definitions for Smart Email Agent LangGraph.

Defines the typed state that flows through the LangGraph nodes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TypedDict


class Priority(Enum):
    """Email priority levels."""
    P1 = 1  # דחוף - Urgent, needs attention today
    P2 = 2  # חשוב - Important, needs attention this week
    P3 = 3  # מידע - Informational, nice to know
    P4 = 4  # נמוך - Low, can be ignored/archived


class EmailCategory(Enum):
    """Email categories with Hebrew names."""
    BUREAUCRACY = "בירוקרטיה"      # Government, taxes, official
    FINANCE = "כספים"              # Banks, payments, invoices
    URGENT = "דחוף"                # Deadlines within 48h
    CALENDAR = "יומן"              # Meetings, appointments
    ACTION_REQUIRED = "דורש פעולה"  # Tasks, requests
    INFORMATIONAL = "מידע"         # Newsletters, updates
    PROMOTIONAL = "פרסום"          # Marketing, sales
    PERSONAL = "אישי"              # Friends, family


@dataclass
class ResearchResult:
    """Web research result for an email."""
    email_id: str
    query: str
    findings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    summary: str = ""
    relevant_deadlines: list[str] = field(default_factory=list)
    forms_found: list[str] = field(default_factory=list)


@dataclass
class SenderHistory:
    """History of communication with a sender."""
    sender_email: str
    total_emails: int = 0
    last_contact: str = ""
    common_topics: list[str] = field(default_factory=list)
    previous_threads: list[str] = field(default_factory=list)
    relationship_type: str = ""  # new, recurring, frequent


@dataclass
class DraftReply:
    """Draft reply suggestion for an email."""
    email_id: str
    subject: str
    body: str
    tone: str = "professional"  # professional, friendly, formal
    action_type: str = ""  # reply, forward, schedule_meeting
    confidence: float = 0.0


@dataclass
class VerificationResult:
    """Verification that no emails were missed.

    This proves completeness by comparing Gmail total count
    with actually processed + explicitly skipped counts.
    """
    gmail_total: int = 0           # Total emails returned by Gmail API
    processed_count: int = 0       # Actually classified and processed
    skipped_system: int = 0        # System emails filtered out
    skipped_duplicates: int = 0    # Duplicate emails skipped
    missed_ids: list[str] = field(default_factory=list)  # IDs not processed
    verified: bool = False         # True if gmail_total == processed + skipped

    @property
    def is_complete(self) -> bool:
        """Check if all emails were accounted for."""
        expected = self.processed_count + self.skipped_system + self.skipped_duplicates
        return self.gmail_total == expected and len(self.missed_ids) == 0

    def summary_hebrew(self) -> str:
        """Generate Hebrew summary for Telegram footer."""
        if self.is_complete:
            return f"✅ {self.gmail_total}/{self.gmail_total} מיילים נסרקו (0 פוספסו)"
        else:
            missed = len(self.missed_ids)
            return f"⚠️ {self.processed_count}/{self.gmail_total} מיילים נסרקו ({missed} פוספסו)"


@dataclass
class EmailItem:
    """Single email with classification."""
    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    date: str
    snippet: str
    body: str = ""

    # Classification (filled by classify node)
    category: EmailCategory = EmailCategory.INFORMATIONAL
    priority: Priority = Priority.P3
    priority_reason: str = ""

    # Extracted data
    deadline: str | None = None
    amount: str | None = None
    links: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)

    # AI insights
    ai_summary: str = ""
    ai_action_suggestion: str = ""

    # Phase 2: Research & History (filled by intelligence nodes)
    research: ResearchResult | None = None
    sender_history: SenderHistory | None = None
    draft_reply: DraftReply | None = None


@dataclass
class CalendarEvent:
    """Calendar event for context."""
    id: str
    summary: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)


class EmailState(TypedDict, total=False):
    """LangGraph state for email processing.

    This TypedDict defines the state that flows through all nodes.
    Each node can read and modify this state.
    """
    # Input
    user_id: str
    hours_lookback: int
    enable_research: bool          # Phase 2: Enable web research
    enable_history: bool           # Phase 2: Enable history lookup
    enable_drafts: bool            # Phase 2: Enable draft generation

    # Fetched data
    raw_emails: list[dict]         # Raw Gmail messages
    calendar_events: list[dict]    # Today's calendar

    # Processed data
    emails: list[EmailItem]        # Classified emails
    system_emails_count: int       # Filtered system notifications

    # Phase 2: Research & Intelligence
    research_results: list[ResearchResult]   # Web research findings
    sender_histories: list[SenderHistory]    # Communication history
    draft_replies: list[DraftReply]          # Suggested replies
    research_count: int            # Emails researched
    drafts_count: int              # Drafts generated

    # Counts
    total_count: int
    p1_count: int
    p2_count: int
    p3_count: int
    p4_count: int

    # Output
    telegram_message: str          # Formatted message
    telegram_sent: bool
    telegram_error: str | None

    # Verification (Phase 4: Proof of Completeness)
    verification: VerificationResult | None
    all_fetched_ids: list[str]     # All email IDs from Gmail API
    all_processed_ids: list[str]   # All email IDs that were processed

    # Metadata
    run_id: str
    start_time: float
    duration_ms: int
    errors: list[str]


def create_initial_state(
    user_id: str = "default",
    hours_lookback: int = 24,
    enable_research: bool = True,
    enable_history: bool = True,
    enable_drafts: bool = True,
) -> EmailState:
    """Create initial state for the graph.

    Args:
        user_id: User identifier
        hours_lookback: Hours to look back for emails
        enable_research: Enable web research for P1/P2 emails
        enable_history: Enable sender history lookup
        enable_drafts: Enable draft reply generation

    Returns:
        Initial EmailState
    """
    import time

    return EmailState(
        user_id=user_id,
        hours_lookback=hours_lookback,
        enable_research=enable_research,
        enable_history=enable_history,
        enable_drafts=enable_drafts,
        raw_emails=[],
        calendar_events=[],
        emails=[],
        system_emails_count=0,
        research_results=[],
        sender_histories=[],
        draft_replies=[],
        research_count=0,
        drafts_count=0,
        total_count=0,
        p1_count=0,
        p2_count=0,
        p3_count=0,
        p4_count=0,
        telegram_message="",
        telegram_sent=False,
        telegram_error=None,
        verification=None,
        all_fetched_ids=[],
        all_processed_ids=[],
        run_id=f"smart_email_{int(time.time())}",
        start_time=time.time(),
        duration_ms=0,
        errors=[],
    )
