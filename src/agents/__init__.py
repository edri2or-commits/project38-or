"""Agents module - Autonomous AI agents for project38-or.

This module contains specialized agents that run autonomously:
- EmailAgent: Daily email scanning, classification, and Telegram delivery
- WebResearcher: Investigates external websites based on email context
- DraftGenerator: Creates intelligent email reply drafts
- EmailHistoryLookup: Finds past conversations with senders

ADR-014: Smart Email Agent with Telegram Integration
"""

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
]
