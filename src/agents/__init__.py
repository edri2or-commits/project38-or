"""Agents module - Autonomous AI agents for project38-or.

This module contains specialized agents that run autonomously:
- EmailAgent: Daily email scanning, classification, and Telegram delivery
- WebResearcher: Investigates external websites based on email context
- DraftGenerator: Creates intelligent email reply drafts
- EmailHistoryLookup: Finds past conversations with senders
- FormExtractor: Extracts form fields and pre-fills with user data
- DeadlineTracker: Tracks deadlines and sends proactive reminders
- UserPreferences: Learns from user actions and stores preferences
- TaskIntegration: Creates and manages tasks from emails

ADR-014: Smart Email Agent with Telegram Integration
"""

from src.agents.deadline_tracker import (
    Deadline,
    DeadlineStatus,
    DeadlineTracker,
    DeadlineUrgency,
)
from src.agents.draft_generator import (
    DraftGenerator,
    DraftReply,
    ReplyType,
    ToneType,
)
from src.agents.email_agent import (
    CalendarEvent,
    DailySummary,
    EmailAgent,
    EmailCategory,
    EmailItem,
    Priority,
)
from src.agents.email_history import (
    EmailHistoryLookup,
    RelationshipType,
    SenderHistory,
)
from src.agents.form_extractor import (
    ExtractedForm,
    FormExtractor,
    FormField,
    FormFieldType,
)
from src.agents.task_integration import (
    TaskIntegration,
    TaskItem,
    TaskPriority,
    TaskSource,
    TaskStatus,
)
from src.agents.user_preferences import (
    ActionType,
    UserPreferences,
)
from src.agents.web_researcher import (
    ResearchResult,
    WebResearcher,
)

__all__ = [
    # Email Agent (Phase 1)
    "EmailAgent",
    "EmailItem",
    "EmailCategory",
    "Priority",
    "DailySummary",
    "CalendarEvent",
    # Web Researcher (Phase 2)
    "WebResearcher",
    "ResearchResult",
    # Draft Generator (Phase 2)
    "DraftGenerator",
    "DraftReply",
    "ReplyType",
    "ToneType",
    # Email History (Phase 2)
    "EmailHistoryLookup",
    "SenderHistory",
    "RelationshipType",
    # Form Extractor (Phase 3)
    "FormExtractor",
    "ExtractedForm",
    "FormField",
    "FormFieldType",
    # Deadline Tracker (Phase 3)
    "DeadlineTracker",
    "Deadline",
    "DeadlineStatus",
    "DeadlineUrgency",
    # User Preferences (Phase 3)
    "UserPreferences",
    "ActionType",
    # Task Integration (Phase 3)
    "TaskIntegration",
    "TaskItem",
    "TaskPriority",
    "TaskStatus",
    "TaskSource",
]
