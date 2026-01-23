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

    # Fetched data
    raw_emails: list[dict]         # Raw Gmail messages
    calendar_events: list[dict]    # Today's calendar

    # Processed data
    emails: list[EmailItem]        # Classified emails
    system_emails_count: int       # Filtered system notifications

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

    # Metadata
    run_id: str
    start_time: float
    duration_ms: int
    errors: list[str]


def create_initial_state(
    user_id: str = "default",
    hours_lookback: int = 24,
) -> EmailState:
    """Create initial state for the graph.

    Args:
        user_id: User identifier
        hours_lookback: Hours to look back for emails

    Returns:
        Initial EmailState
    """
    import time

    return EmailState(
        user_id=user_id,
        hours_lookback=hours_lookback,
        raw_emails=[],
        calendar_events=[],
        emails=[],
        system_emails_count=0,
        total_count=0,
        p1_count=0,
        p2_count=0,
        p3_count=0,
        p4_count=0,
        telegram_message="",
        telegram_sent=False,
        telegram_error=None,
        run_id=f"smart_email_{int(time.time())}",
        start_time=time.time(),
        duration_ms=0,
        errors=[],
    )
